# Torn-AgentPay Reference Buyer

This directory is a minimal reference buyer package for Torn-AgentPay.

It is meant for third-party implementers who want the smallest runnable buyer-side example without starting from the full buyer runtime surface.

## Included Files

- `reference-buyer.manifest.json`
  Package metadata and expected runtime behavior.
- `minimal-buyer-reference.py`
  Runnable reference buyer flow.

## What It Demonstrates

- fetch seller manifest
- fetch seller discovery document
- discover offers
- prepare purchase
- submit purchase
- confirm purchase

## Quick Start

```powershell
.venv\Scripts\python.exe minimal-buyer-reference.py
```

## Notes

- This package is intentionally minimal and deterministic.
- It is a reference implementation, not a production buyer SDK.
- For a more complete integration surface, see `spec/BUYER_IMPLEMENTER_GUIDE.md`.
