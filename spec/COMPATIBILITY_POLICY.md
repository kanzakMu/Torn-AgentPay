# Compatibility Policy

This document describes the compatibility expectations for the first public Torn-AgentPay protocol release artifacts.

## Version Line

The current public line is:

- `aimipay.manifest.v1`
- `aimipay.seller-profile.v1`
- `aimipay.signature-envelope.v1`
- `aimipay.offer.v1`
- `torn-agentpay.release-artifacts.v1`

## Stable Compatibility Expectations

Within a given `v1` line:

- published schema filenames are stable
- required manifest field names are stable
- seller profile signing rules are stable
- signature envelope structure is stable
- discover-to-manifest consistency rules are stable
- seller node package manifest structure is stable

## Allowed Non-Breaking Evolution

The following changes are allowed without introducing `v2`:

- new optional fields
- new documentation
- new release helper scripts
- new conformance checks that tighten diagnostics but do not invalidate already valid `v1` payloads

## Breaking Changes

The following require a new major schema line:

- removing required fields
- renaming stable fields
- changing canonical signing payload semantics
- changing signature envelope meaning
- changing required discover/manifest linkage rules

## Compatibility Layers

Some runtime and environment names still use `merchant` for legacy compatibility:

- `bootstrap_merchant.ps1`
- `run_merchant_stack.ps1`
- `.env.merchant.example`
- `merchant.public.json`

These names are retained for operational continuity, but the public product language is seller-first.

## Recommended Third-Party Policy

Third-party implementations should:

- pin to the published `v1` schemas
- treat unknown optional fields as ignorable
- fail closed on invalid signatures
- surface schema version mismatches explicitly
