# Buyer Implementer Guide

This guide is for teams that want to implement Torn-AgentPay buyer behavior, or map Torn-AgentPay purchase flows into an agent runtime without depending on the full Torn-AgentPay Python buyer runtime.

## Buyer Responsibilities

A compatible buyer implementation should be able to:

- fetch the seller manifest
- fetch the seller discover document
- verify signed seller metadata when signatures are present
- evaluate offers and estimate cost
- prepare a purchase session
- submit a purchase intent
- confirm settlement or continue reconciliation

## Required Inputs

A buyer runtime needs:

- a buyer wallet
- a seller base URL
- a payment-capable environment for the target network

The buyer should prefer seller-published metadata over hard-coded local values for:

- seller address
- contract address
- token address
- chain id
- settlement backend

## Recommended Runtime Flow

1. Fetch `/.well-known/aimipay.json`
2. Verify `seller_profile_signature` if present
3. Verify `manifest_signature` if present
4. Fetch `/_aimipay/discover`
5. Compare discover and manifest chain metadata
6. Build offer candidates
7. Estimate budget and choose an offer
8. Prepare a purchase session
9. Submit a purchase intent
10. Confirm or reconcile until terminal settlement

## High-Level Purchase Objects

The reference runtime exposes a higher-level flow with these object stages:

- `prepare_purchase`
- `submit_purchase`
- `confirm_purchase`

Offline fixture exports use the same names in `purchase.json`.

Minimal runnable reference:

```powershell
.venv\Scripts\python.exe python/examples/minimal_buyer_reference.py
```

Reference buyer package:

```powershell
.venv\Scripts\python.exe -m ops_tools.package_reference_buyer --output-dir .\dist\reference-buyer --json
```

## What To Validate

At minimum, a buyer implementation should validate:

- manifest schema version
- seller profile schema version
- signature envelope structure
- recovered signer address
- discover-to-manifest seller match
- discover-to-manifest contract match
- discover-to-manifest token match

## Conformance Workflow

Export reference fixtures:

```powershell
.venv\Scripts\python.exe -m ops_tools.export_conformance_fixtures --output-dir .\fixtures
```

Validate them offline:

```powershell
.venv\Scripts\python.exe -m ops_tools.conformance_check --manifest-file .\fixtures\manifest.json --discover-file .\fixtures\discover.json --attestation-file .\fixtures\attestation.json --purchase-file .\fixtures\purchase.json
```

## Mapping To Host Tooling

If you are integrating with an MCP host or another agent runtime, the common high-level actions are:

- list offers
- estimate budget
- prepare purchase
- submit purchase
- confirm purchase
- recover payment

These actions should be mapped to host-native tools or runtime steps rather than exposing low-level payment internals to the end agent whenever possible.

## Related References

- `spec/AGENT_INTEGRATION_GUIDE.md`
- `spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md`
- `spec/COMPATIBILITY_POLICY.md`
- `spec/CONFORMANCE_CHECKLIST.md`
