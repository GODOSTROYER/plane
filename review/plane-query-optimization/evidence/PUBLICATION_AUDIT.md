# Evidence archive publication audit

## Artifact identity

- Archive: plane-evidence-c70e8050e728-linux-validated.zip
- Size: 267,366 bytes
- SHA256: 553d5caf5624f4dbc6f179c92ff8c18fa2d7a21dae3da4dbe7ddef4a3d144e19
- Members scanned: 62, including the checksum manifest
- The archive's own verifier reported 61 verified payload files with SHA256 and ZIP CRC checks.

## Independent content checks

A second read-only scan examined every archive member without extracting or executing it:

- 29 JSON files parsed successfully; 2 XML files parsed successfully; no parse failures.
- No matches for GitHub or common cloud/service tokens, private-key headers, credential-bearing PostgreSQL/Redis/AMQP URLs, personal Windows or POSIX home/workspace paths, or local host environment variables.
- No email addresses, unsafe archive member paths, or other scan flags were found.
- The embedded sanitization manifest documents the filename allowlist, excludes environment files, runtime credentials, database dumps, full source trees and unrelated API responses, and records zero secret assignments, zero credential URLs and zero fixture-email replacements. It records host-path normalization and consistent fixture UUID pseudonymization.

## Limits

These checks reduce the risk of publishing accidental local data but cannot prove that every arbitrary string is harmless. The artifacts contain synthetic benchmark/test data, not production user or customer data. The archive README describes the benchmark scope, sanitization, historical evidence, and reproduction limits.