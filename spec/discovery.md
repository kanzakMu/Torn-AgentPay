# Discovery Specification

Published JSON Schema files for the manifest, seller profile, signature envelope, and related objects live under `spec/schemas/`.

## Goal

Provide a machine-readable seller service manifest for:

- AI agents
- buyer SDKs
- APIs
- MCP integrations

## Well-Known Endpoint

Every seller gateway should expose:

```text
/.well-known/aimipay.json
```

## Required Top-Level Fields

```json
{
  "schema_version": "aimipay.manifest.v1",
  "version": "v1",
  "kind": "aimipay-merchant",
  "transport": "http+aimipay",
  "service_name": "Example Service",
  "service_description": "Pay-per-use AI service",
  "primary_chain": {},
  "seller_profile": {},
  "seller_profile_signature": {},
  "manifest_signature": {},
  "routes": [],
  "plans": [],
  "endpoints": {}
}
```

## Signed Seller Metadata

The public manifest can carry two optional but recommended attestations:

- `seller_profile_signature`
- `manifest_signature`

Both use the same signature envelope schema:

```json
{
  "schema_version": "aimipay.signature-envelope.v1",
  "algorithm": "secp256k1-keccak256-recoverable",
  "payload_kind": "seller_profile",
  "signer_address": "TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW",
  "digest": "0x...",
  "signed_at": 1710000000,
  "signature": "0x..."
}
```

`seller_profile` should be wallet-bound and machine-readable:

```json
{
  "schema_version": "aimipay.seller-profile.v1",
  "seller_address": "TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW",
  "display_name": "Research Copilot",
  "service_name": "Research Copilot",
  "service_description": "Pay-per-use AI service",
  "service_url": "https://seller.example",
  "network": "nile",
  "chain_id": 3448148188,
  "proof_methods": ["wallet_signature"],
  "metadata": {}
}
```

Buyers should verify:

- `seller_profile_signature` against `seller_profile`
- `manifest_signature` against the manifest body with `manifest_signature` omitted
- recovered signer address matches `primary_chain.seller_address`

## `primary_chain`

Required fields:

- `chain`
- `channel_scheme`
- `network`
- `seller_address`
- `contract_address`
- `asset_address`
- `asset_symbol`
- `asset_decimals`

Default values for this repository:

- `chain = tron`
- `channel_scheme = tron-contract`
- `asset_symbol = USDT`
- `asset_decimals = 6`

## `routes`

Each paid route should describe:

- `path`
- `method`
- `price_atomic`
- optional `description`

## `plans`

Subscription metadata may include:

- `plan_id`
- `name`
- `amount_atomic`
- `billing_interval`
- optional `description`
- optional `subscribe_path`
- optional `features`

## `endpoints`

Current minimum endpoint set:

- `discover`
- `management`
- `open_channel`
- `payment_status_template`
