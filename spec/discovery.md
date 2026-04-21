# Discovery Specification

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
  "version": "v1",
  "kind": "aimipay-merchant",
  "transport": "http+aimipay",
  "service_name": "Example Service",
  "service_description": "Pay-per-use AI service",
  "primary_chain": {},
  "routes": [],
  "plans": [],
  "endpoints": {}
}
```

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
