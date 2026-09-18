# Security

## Reporting a vulnerability

Please do not open a public issue for a suspected security vulnerability.

Report it privately to the repository owner through GitHub so that credentials, tokens, or other sensitive details are not exposed publicly.

## Secrets

Runtime credentials are expected to be stored in GitHub Actions Secrets and must never be committed to the repository.

The repository intentionally keeps production workflows manual-only while Actions quota is constrained.

## GitHub Actions

Workflow permissions are restricted to the minimum required scope, and production workflows that write state use write access only at the job level.

Third-party GitHub Actions are pinned to immutable commit SHAs.
