# Third-Party Implementer Guide

This guide is for teams that want to implement Torn-AgentPay protocol objects or validate an independent seller runtime without depending on Torn-AgentPay's Python runtime.

## What You Need To Implement

At minimum, a compatible seller implementation should expose:

- `/.well-known/aimipay.json`
- `/_aimipay/discover`
- `/_aimipay/protocol/reference`

The published manifest should conform to:

- `spec/schemas/aimipay.manifest.v1.schema.json`
- `spec/schemas/aimipay.seller-profile.v1.schema.json`
- `spec/schemas/aimipay.signature-envelope.v1.schema.json`

If you expose priced capabilities, your offer-like objects should be representable with:

- `spec/schemas/aimipay.offer.v1.schema.json`

Supporting references:

- `spec/PROTOCOL_REFERENCE.md`
- `spec/discovery.md`
- `spec/BUYER_IMPLEMENTER_GUIDE.md`
- `spec/COMPATIBILITY_POLICY.md`
- `spec/CONFORMANCE_CHECKLIST.md`

## Recommended Implementation Order

1. Publish a valid manifest
2. Publish a valid discover document
3. Add seller profile signing
4. Add manifest signing
5. Verify that discover and manifest agree on seller, token, contract, and chain
6. Implement purchase flow endpoints

## Signed Seller Metadata

A signed seller implementation should:

1. build a canonical `seller_profile` object
2. sign that payload with the seller wallet
3. embed the resulting `seller_profile_signature`
4. build the full manifest
5. remove signatures from the manifest payload before hashing
6. sign the manifest payload with the same seller wallet
7. embed `manifest_signature`

Buyer implementations should verify:

- payload digest
- signature envelope shape
- recovered signer address
- signer equality with `seller_profile.seller_address`
- signer equality with `primary_chain.seller_address`

## Conformance Workflow

### Live seller runtime

Validate a running seller:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --seller-url http://127.0.0.1:8000
```

### Offline validation

If you have exported JSON files from another implementation:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --manifest-file .\manifest.json --discover-file .\discover.json --attestation-file .\attestation.json --purchase-file .\purchase.json
```

Export a full offline fixture set from the reference implementation:

```powershell
.venv\Scripts\python.exe -m ops_tools.export_conformance_fixtures --output-dir .\fixtures
```

Minimal runnable seller example:

```powershell
.venv\Scripts\python.exe -m uvicorn python.examples.minimal_seller_app:app --host 127.0.0.1 --port 8000
```

## Release Artifacts

Generate the protocol distribution artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File python/build_release_artifacts.ps1
```

This produces:

- `dist/protocol-schemas/`
- `dist/protocol-bundle/`
- `dist/seller-node/`

## Compatibility Notes

- The current public schemas are first-version artifacts and should be treated as `v1` protocol references.
- Some runtime env names still use `merchant` for compatibility, even though the public role language is now seller-first.
- The higher-level purchase abstraction is available, but low-level payment lifecycle calls remain part of the runtime.
