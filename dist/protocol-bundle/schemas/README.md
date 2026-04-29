# Torn-AgentPay Protocol Schemas

This directory contains the published JSON Schema files for the first public version of the Torn-AgentPay protocol objects.

Included schemas:

- `aimipay.manifest.v1.schema.json`
- `aimipay.seller-profile.v1.schema.json`
- `aimipay.signature-envelope.v1.schema.json`
- `aimipay.offer.v1.schema.json`
- `aimipay.route.v1.schema.json`
- `aimipay.plan.v1.schema.json`
- `aimipay.chain-info.v1.schema.json`

Bundle index:

- `index.json`

Regenerate from source models:

```powershell
.venv\Scripts\python.exe -m ops_tools.export_protocol_schemas
```

Run a conformance check against a live seller:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --seller-url http://127.0.0.1:8000
```

Run a conformance check against exported JSON files:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --manifest-file .\manifest.json --discover-file .\discover.json --attestation-file .\attestation.json
```

See also:

- `spec/PROTOCOL_REFERENCE.md`
- `spec/discovery.md`
- `spec/BUYER_IMPLEMENTER_GUIDE.md`
- `spec/HOST_IMPLEMENTER_GUIDE.md`
- `spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md`
