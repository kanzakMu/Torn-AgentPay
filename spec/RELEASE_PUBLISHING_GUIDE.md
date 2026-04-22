# Release Publishing Guide

This guide explains how to build, validate, and publish Torn-AgentPay release artifacts for third-party consumers.

## What Gets Published

The release artifact flow currently produces:

- `protocol-schemas/`
- `protocol-bundle/`
- `seller-node/`
- `reference-buyer/`
- `conformance-fixtures/`
- `RELEASE_NOTES.md`
- `release-manifest.json`
- `release-report.json`

## Build The Release Artifacts

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File python/build_release_artifacts.ps1
```

Or specify an explicit output directory:

```powershell
powershell -ExecutionPolicy Bypass -File python/build_release_artifacts.ps1 -OutputDir .\dist
```

## Validate The Release Artifacts

After building, run:

```powershell
.venv\Scripts\python.exe -m ops_tools.validate_release_artifacts --dist-dir .\dist
```

Validation checks for:

- top-level release metadata files
- published schema files
- protocol bundle documents
- seller node package files
- reference buyer package files
- offline conformance fixtures

## Validate The Protocol Bundle

For a live seller:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --seller-url http://127.0.0.1:8000
```

For offline files:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --manifest-file .\dist\conformance-fixtures\manifest.json --discover-file .\dist\conformance-fixtures\discover.json --attestation-file .\dist\conformance-fixtures\attestation.json --purchase-file .\dist\conformance-fixtures\purchase.json
```

## Publish Through GitHub Actions

The repository includes:

- `.github/workflows/build-release-artifacts.yml`

It runs on:

- pushes to `main`
- manual workflow dispatch

The workflow:

1. installs Python and Node dependencies
2. runs the targeted test suite
3. builds release artifacts into `dist/`
4. validates `dist/`
5. uploads the `dist` directory as a workflow artifact

## Recommended Release Procedure

1. ensure the working tree is clean
2. run the targeted local tests
3. build release artifacts locally
4. validate release artifacts locally
5. commit and push to `main`
6. confirm the GitHub Actions workflow succeeds
7. download the uploaded `dist` artifact if needed for external distribution

## What To Hand To Third Parties

For protocol implementers:

- `dist/protocol-schemas/`
- `dist/protocol-bundle/`
- `dist/conformance-fixtures/`

For seller operators:

- `dist/seller-node/`

For buyer-side reference implementations:

- `dist/reference-buyer/`

## Related References

- `spec/COMPATIBILITY_POLICY.md`
- `spec/CONFORMANCE_CHECKLIST.md`
- `spec/BUYER_IMPLEMENTER_GUIDE.md`
- `spec/HOST_IMPLEMENTER_GUIDE.md`
- `spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md`
