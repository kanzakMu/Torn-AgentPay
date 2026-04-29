# Protocol Reference

This document defines the canonical protocol for `aimipay-tron-v1`.

## Published Schemas

The repository publishes versioned JSON Schema files for the primary protocol objects:

- `spec/schemas/aimipay.manifest.v1.schema.json`
- `spec/schemas/aimipay.seller-profile.v1.schema.json`
- `spec/schemas/aimipay.signature-envelope.v1.schema.json`
- `spec/schemas/aimipay.offer.v1.schema.json`
- `spec/schemas/aimipay.route.v1.schema.json`
- `spec/schemas/aimipay.plan.v1.schema.json`
- `spec/schemas/aimipay.chain-info.v1.schema.json`

They can be regenerated from source models with:

- `python -m ops_tools.export_protocol_schemas`

## Single Source Of Truth

- `channel_id` generation: `scripts/protocol.js::channelIdOf`
- Address normalization: `scripts/protocol.js::normalizeTronAddress`
- `request_digest` generation: `scripts/protocol.js::buildRequestDigest`
- `voucher_digest` generation: `scripts/protocol.js::voucherDigest`
- Signature generation: `scripts/protocol.js::signDigest`
- On-chain verification: `contracts/AimiMicropayChannel.sol`
- Runtime protocol endpoint: `GET /_aimipay/protocol/reference`
- Published protocol schemas: `spec/schemas/index.json`

## Channel ID

- Rule: `keccak256(abi.encodePacked(normalized_buyer, normalized_seller, normalized_token, channel_salt))`
- Address inputs must be normalized to EVM hex address form before hashing.
- `channel_salt` is a 32-byte random value generated for each channel open request and carried through provisioning.
- External adapters should not re-invent this rule from prose alone; prefer the canonical JS implementation or the runtime protocol endpoint.

## Request Digest

- Canonical function: `buildRequestDigest`
- Fields:
  - HTTP method
  - request path
  - `request_deadline`
  - body hash
- Body hash is computed over the raw request body bytes.
- The goal is to bind the payment authorization to a specific request, not to a generic merchant session.

## Voucher Digest

- Canonical function: `voucherDigest`
- Field order:
  1. voucher domain
  2. chain id
  3. contract address
  4. channel id
  5. buyer
  6. seller
  7. token
  8. amount atomic
  9. voucher nonce
  10. expires at
  11. request deadline
  12. request digest
- Encoding must stay aligned with `contracts/AimiMicropayChannel.sol`.

## Signature

- Algorithm: `secp256k1 / ECDSA`
- Signed payload: `voucher_digest`
- Buyer signs the digest; seller submits the claim on-chain.

## Time Semantics

- `expires_at`:
  - channel expiry
  - after this point, the channel cannot be claimed
- `request_deadline`:
  - request authorization expiry
  - gateway rejects expired intents
  - settlement rejects expired execution
  - contract rejects expired claim

## Payment Status Flow

- `pending`: intent exists but is not yet settlement-ready
- `authorized`: intent is created and ready for settlement
- `submitted`: settlement transaction has been submitted
- `settled`: terminal success state after explicit on-chain confirmation or reconciliation
- `failed`: terminal failure that requires inspection, manual recovery, or operator compensation
- `expired`: authorization or channel expired before settlement

## Error Codes

- `request_deadline_expired`: request authorization expired; not safe to retry as-is
- `payment_expired`: channel expired before settlement; not safe to retry as-is
- `settlement_execution_failed`: submission failed before a confirmed chain result; inspect and recover
- `settlement_confirmation_failed`: confirmation step failed unexpectedly; query and reconcile again
- `settlement_confirmation_retry_exhausted`: confirmation retry budget was exhausted; operator review is required
- `settlement_transaction_reverted`: the submitted transaction was observed on chain as failed
- `settlement_tx_missing`: payment entered `submitted` without a usable `tx_id`
- `idempotency_conflict`: same `idempotency_key` was reused with a different payload
- `manual_intervention_required`: an operator explicitly marked the payment as requiring manual handling
- `manual_compensation_recorded`: an operator recorded off-chain compensation for the payment

Stable error contract surfaces:

- HTTP: `detail.error.code / message / retryable / details`
- MCP tool errors: `result.isError = true` plus `structuredContent.error`
- Worker summaries: `logs[*].error`
- Payment records: `error_code / error_message / error_retryable`

## Seller Attestation

- `seller_profile` is the seller identity object embedded in the manifest.
- `seller_profile_signature` signs the canonical `seller_profile` payload.
- `manifest_signature` signs the canonical manifest payload with signatures removed before hashing.
- Both signatures use the `SignatureEnvelope` schema and the same wallet-bound signer address.
- Buyers should verify:
  - the signature envelope structure
  - the payload digest
  - recovered signer address equals `seller_profile.seller_address`
  - manifest signer equals `primary_chain.seller_address`

## Idempotency Rules

- `idempotency_key` must map to exactly one logical payment intent.
- Same key + same payload returns the original payment.
- Same key + different payload returns `idempotency_conflict`.
- External agents should reuse the same key across safe retries of one business operation.

## Recovery Rules

- Recovery queries support:
  - `payment_id`
  - `idempotency_key`
  - `channel_id`
- Reconciliation endpoint:
  - `POST /_aimipay/settlements/reconcile`
- Operator action endpoint:
  - `POST /_aimipay/ops/payments/{payment_id}/action`
- Recommended lifecycle:
  - after timeout during creation: query by `idempotency_key`
  - after timeout during submission: query by `payment_id`
  - after a `submitted` response: poll payment status or trigger reconciliation until `settled` or `failed`
  - after process restart: list pending payments, then recover one by one
  - after retry exhaustion or customer-impacting failure: use operator action to mark manual failure, compensation, or verified settlement
