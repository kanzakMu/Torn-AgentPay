# Python Examples

These examples show the intended low-code integration shape for both sides:

- seller / merchant app: `merchant_app.py`
- buyer / agent runtime: `agent_runtime_demo.py`
- local orchestrated demo: `local_end_to_end_demo.py`
- off-chain stress drill: `offchain_stress_drill.py`
- env template: `.env.example`
- PowerShell launcher: `run_local_demo.ps1`
- sample project template: `../sample_project/`

## 1. Install Python dependencies

```bash
pip install -r python/requirements.txt
```

## 2. Start the merchant demo

Merchant bootstrap first, if you want the seller-side install files and website starter assets prepared:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
```

From the repository root:

```bash
python -m uvicorn python.examples.merchant_app:app --host 127.0.0.1 --port 8000
```

Optional environment variables:

```bash
set AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron
set AIMIPAY_FULL_HOST=http://127.0.0.1:9090
set AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key
set AIMIPAY_SETTLEMENT_BACKEND=claim_script
```

The merchant demo exposes:

- `/.well-known/aimipay.json`
- `/_aimipay/discover`
- `/_aimipay/channels/open`
- `/_aimipay/payments`
- `/_aimipay/settlements/execute`
- `/_aimipay/settlements/reconcile`
- `/_aimipay/ops/health`
- `/_aimipay/ops/payments/{payment_id}/action`
- `/aimipay/install`

Merchant website/SaaS starter kit:

- [merchant-dist/README.md](/E:/trade/aimicropay-tron/merchant-dist/README.md)
- [EMBED_GUIDE.md](/E:/trade/aimicropay-tron/merchant-dist/saas/EMBED_GUIDE.md)
- [embed.checkout.html](/E:/trade/aimicropay-tron/merchant-dist/website/embed.checkout.html)

## 3. Run the agent runtime demo

In another terminal:

```bash
set AIMIPAY_MERCHANT_URLS=http://127.0.0.1:8000
set AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron
python python/examples/agent_runtime_demo.py
```

This demo will:

1. build the agent payments runtime
2. discover merchant capability offers
3. estimate task budget
4. select an offer
5. attempt to pay for the task

## 4. Notes

- `claim_script` requires real buyer authorization fields and a runnable claim backend
- `local_smoke` is easier for local integration experiments because buyer authorization can be skipped
- buyer-side `AIMIPAY_FULL_HOST` is optional when the merchant already exposes usable network metadata through manifest/discover
- `GET /_aimipay/ops/health` should be green before controlled traffic is sent to the merchant demo
- The example values are intentionally simple and should be replaced with real addresses, keys, and deployment outputs before any non-local use

## 5. One-Command Local Demo

This example starts the merchant demo with `local_smoke`, waits for health, and runs the buyer side purchase flow:

```bash
set AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron
python python/examples/local_end_to_end_demo.py
```

PowerShell shortcut:

```powershell
./python/examples/run_local_demo.ps1
```

Environment template:

```bash
copy python/examples/.env.example .env.local
```

This path uses:

- a local merchant app started via `uvicorn`
- a local demo buyer runtime
- the seller `local_smoke` settlement backend
- Hardhat default buyer/seller addresses for the local claim path

## 6. Off-Chain Stress Drill

Run a synthetic SQLite-backed worker drill:

```bash
python python/examples/offchain_stress_drill.py
```

This drill exercises:

- multi-worker execution and reconciliation
- retryable execution failures
- temporary confirmation failures
- terminal on-chain-style confirmation failures
