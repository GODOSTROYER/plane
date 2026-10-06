#!/usr/bin/env python3
"""Prepare a NEW worktree/branch on the user's fork. Never push or switch an existing checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from changes import apply_changes

ROOT = Path(__file__).resolve().parents[1]
BASE = "7466675e471efe1c96b122615f7a0d30c9b2eb05"
TARGET = "apps/api/plane/utils/paginator.py"
EXPECTED_BLOB = "2082041f1ac641ade4aa87eb9f0d9c581233e333"
FORK = "GODOSTROYER/plane"
BRANCH = "perf/pagination-count-evaluation"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True)


def valid_origin(url: str) -> bool:
    return url.rstrip("/").removesuffix(".git") in {
        f"https://github.com/{FORK}", f"git@github.com:{FORK}", f"ssh://git@github.com/{FORK}"
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="An existing clone whose origin is GODOSTROYER/plane")
    parser.add_argument("--worktree", type=Path, required=True, help="A new, non-existing path")
    args = parser.parse_args()
    repo, worktree = args.repo.resolve(), args.worktree.resolve()
    origin = git(repo, "remote", "get-url", "--push", "origin").stdout.decode().strip()
    if not valid_origin(origin):
        raise SystemExit("Refusing: origin's push URL is not the user's Plane fork")
    if worktree.exists():
        raise SystemExit("Refusing to reuse an existing worktree path")
    if git(repo, "show-ref", "--verify", f"refs/heads/{BRANCH}", check=False).returncode == 0:
        raise SystemExit("Refusing to overwrite an existing local branch")
    remote = git(repo, "ls-remote", "--heads", "origin", BRANCH).stdout.strip()
    if remote:
        raise SystemExit("Refusing to overwrite an existing remote branch")
    # Read the fork base without moving an existing branch or contacting upstream.
    git(repo, "fetch", "--no-tags", "origin", "preview")
    live_base = git(repo, "rev-parse", "FETCH_HEAD").stdout.decode().strip()
    if live_base != BASE:
        raise SystemExit(f"Fork preview moved to {live_base}. Re-audit/rebase before preparing this patch.")
    original = git(repo, "show", f"{BASE}:{TARGET}").stdout
    # This is the actual Git object, not the offline method snapshot.
    original_blob = git(repo, "rev-parse", f"{BASE}:{TARGET}").stdout.decode().strip()
    computed = hashlib.sha1(b"blob " + str(len(original)).encode() + b"\0" + original).hexdigest()
    if original_blob != EXPECTED_BLOB:
        raise SystemExit("Reviewed paginator blob differs: re-audit before making changes")
    if computed != original_blob:
        raise SystemExit("Git object integrity check failed")
    updated = apply_changes(original.decode("utf-8")).encode("utf-8")
    tests = sorted((ROOT / "candidate").rglob("*.py"))
    paths = [TARGET] + [str(path.relative_to(ROOT / "candidate")).replace("\\", "/") for path in tests]
    # Do not replace tests introduced upstream under the same name.
    for path in paths[1:]:
        if git(repo, "cat-file", "-e", f"{BASE}:{path}", check=False).returncode == 0:
            raise SystemExit(f"New test path already exists upstream: {path}")
    git(repo, "worktree", "add", "-b", BRANCH, str(worktree), BASE)
    (worktree / TARGET).write_bytes(updated)
    for source in tests:
        destination = worktree / source.relative_to(ROOT / "candidate")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    git(worktree, "add", "--intent-to-add", "--", *paths)
    git(worktree, "diff", "--check")
    manifest = {
        "base": BASE, "source_blob": original_blob, "branch": BRANCH,
        "fork": FORK, "worktree": str(worktree), "published": False,
        "files": {path: hashlib.sha256((worktree / path).read_bytes()).hexdigest() for path in paths},
    }
    output = ROOT / "evidence" / "agent-prepared.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "evidence" / "agent-prepared.diff").write_bytes(git(worktree, "diff", "--", *paths).stdout)
    print(f"Prepared {BRANCH} in {worktree}")
    print("Existing checkouts and PRs were not changed. No commit, push or PR was created.")
    print(f"Next: validate this worktree. Manifest: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"Preparation stopped: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr.decode(errors="replace"), file=sys.stderr)
        raise SystemExit(1)
