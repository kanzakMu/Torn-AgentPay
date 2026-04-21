# AimiPay SaaS Embed Guide

This guide is for SaaS products that want to install AimiPay more like a Stripe plugin than a backend-only gateway.

## Intended Shape

Your SaaS product keeps its existing app shell.

AimiPay adds:

- merchant manifest and discovery endpoints
- a programmable payments runtime
- a website/dashboard starter widget
- a health and install surface for operators

## Recommended Install Flow

1. Run:
   `powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1`
2. Review:
   `python/.env.merchant.local`
3. Start:
   `powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1`
4. Validate:
   `python -m ops_tools.merchant_doctor`
5. Embed:
   `merchant-dist/website/aimipay.checkout.js`

## SaaS UI Placement Ideas

- billing settings page
- integrations marketplace entry
- usage-based tools catalog
- "pay with AimiPay" surface inside a capability dashboard

## Public URLs To Expose

- `/.well-known/aimipay.json`
- `/_aimipay/discover`
- `/_aimipay/protocol/reference`
- `/_aimipay/ops/health`

## Good First Experience

Treat the first merchant install page like an integration tile:

- short value statement
- status badge
- manifest/discover links
- health link
- next step to enable a paid route
