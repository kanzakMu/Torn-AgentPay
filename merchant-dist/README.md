# Torn-AgentPay Merchant Install Kit

This directory is the merchant-facing install layer for websites, SaaS apps, and API products that want Torn-AgentPay-style programmable receipts.

It is intentionally closer to a Stripe-style starter kit than a raw gateway code dump.

## What Is Included

- `website/aimipay.checkout.js`
  A lightweight starter script merchants can embed on a marketing site or dashboard page.
- `website/embed.checkout.html`
  A drop-in HTML example showing the script in use.
- `saas/EMBED_GUIDE.md`
  A SaaS-oriented integration guide for apps that want a managed install surface.

## Merchant Bootstrap

Use the merchant-side bootstrap flow first:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
```

Then start the local merchant runtime:

```powershell
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

Once the runtime is up, open the merchant install dashboard:

- `http://127.0.0.1:8000/aimipay/install`
- check the "Resolved network profile" section to verify the runtime-selected network, chain RPC, contract, token, and settlement backend before exposing the merchant publicly

The merchant bootstrap creates:

- `python/.env.merchant.local`
- `merchant-dist/website/.generated/merchant.public.json`

## Merchant Doctor

Validate the merchant install before exposing it to a site or SaaS shell:

```powershell
.venv\Scripts\python.exe -m ops_tools.merchant_doctor
```

## Website Starter

The quickest website path is:

1. start the merchant runtime
2. copy `website/aimipay.checkout.js`
3. copy the markup from `website/embed.checkout.html`
4. point `data-merchant-base-url` at your public merchant base URL

## Important Scope Note

This starter kit is the merchant install and presentation layer.

It helps merchants expose:

- manifest and discovery endpoints
- pricing and paid capability metadata
- a website-friendly "Pay with Torn-AgentPay" surface
- a dashboard-style install page at `/aimipay/install`

It does not replace the buyer-side agent payment flow. The actual purchase still happens through the buyer/agent lifecycle.
