# Conformance Checklist

Use this checklist when validating a Torn-AgentPay-compatible seller implementation.

## Manifest

- `/.well-known/aimipay.json` is reachable
- `schema_version` is `aimipay.manifest.v1`
- `primary_chain` is present
- `routes` is present
- `plans` is present
- `endpoints` is present

## Seller Identity

- `seller_profile` is present
- `seller_profile_signature` is present when signed mode is advertised
- `manifest_signature` is present when signed mode is advertised
- recovered signer matches `seller_profile.seller_address`
- manifest signer matches `primary_chain.seller_address`

## Discovery

- `/_aimipay/discover` is reachable
- discover `seller` matches manifest `primary_chain.seller_address`
- discover `contract_address` matches manifest `primary_chain.contract_address`
- discover `token_address` matches manifest `primary_chain.asset_address`

## Purchase Surface

- seller exposes payment-intent creation
- seller exposes settlement execute
- seller exposes settlement reconcile
- seller exposes payment status
- offline purchase fixture includes `prepare_purchase`
- offline purchase fixture includes `submit_purchase`
- offline purchase fixture includes `confirm_purchase`

## Seller Node Packaging

- seller node bundle contains `seller-node.manifest.json`
- seller node bundle contains bootstrap script
- seller node bundle contains runtime start script
- seller node bundle contains env template

## Tooling

- `python -m ops_tools.conformance_check --seller-url ...` succeeds for live validation
- `python -m ops_tools.conformance_check --manifest-file ... --discover-file ... --purchase-file ...` succeeds for offline validation
- `python -m ops_tools.export_conformance_fixtures --output-dir ...` produces manifest, discover, attestation, and purchase fixtures
- `powershell -ExecutionPolicy Bypass -File python/build_release_artifacts.ps1` produces protocol and seller-node artifacts

## Host Integration

- host can launch `agent_entrypoints.aimipay_mcp_stdio`
- host can surface `aimipay/startupCard` or `aimipay/startupOnboarding`
- host exposes `prepare_purchase`, `submit_purchase`, and `confirm_purchase`
