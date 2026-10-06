# Baseline reference provenance

The complete `paginator_reference.py` is the original paginator from the fork at
`7466675e471efe1c96b122615f7a0d30c9b2eb05`. Its Git blob is
`2082041f1ac641ade4aa87eb9f0d9c581233e333`. This complete byte-verified reference
replaces the preparation packet's partial excerpt for offline reproduction.
Never overwrite the applied candidate with this baseline file.

Historical `local-validation.json` describes the earlier partial-excerpt run.
Publication reran the 57 offline checks using the complete original source;
`run_offline.py` still extracts only selected classes and installs framework
doubles. It does not import the real Django application or execute PostgreSQL.

`export_baseline.py` independently exports and verifies the same blob from a real
clone for the real-stack benchmark. `verify_offline.py` generates its temporary
combined patch from the reference and candidate test inputs; the branch's real
application/test diff is the canonical complete artifact. No unverified partial
file is installed at a runtime path.
