#!/usr/bin/env python3
"""Export the actual reviewed Git blob without shell encoding conversions."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess

from prepare_branch import BASE, EXPECTED_BLOB, TARGET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = subprocess.run(['git', '-C', str(args.repo), 'show', f'{BASE}:{TARGET}'],
                          check=True, capture_output=True).stdout
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != EXPECTED_BLOB:
        raise SystemExit('Unexpected Git blob: re-audit before using this baseline')
    if args.output.exists():
        raise SystemExit('Refusing to overwrite an existing baseline export')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f'Exported verified blob {blob} to {args.output}')


if __name__ == '__main__':
    main()
