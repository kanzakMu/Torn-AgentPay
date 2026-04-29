# Hosted Gateway Deployment

This guide turns the hosted MVP into a runnable service for demos, pilots, and internal testing.

## Run Locally

```bash
PYTHONPATH=python uvicorn python.examples.hosted_gateway_app:app --host 0.0.0.0 --port 8000
```

Open:

- `GET /_aimipay/hosted/merchants`
- `GET /_aimipay/marketplace/capabilities`
- `GET /merchants/research/.well-known/aimipay.json`
- `GET /merchants/coding/_aimipay/registry/capabilities`

Protected merchant summaries:

```bash
curl -H "X-AimiPay-Merchant-Key: research-secret" \
  http://localhost:8000/_aimipay/hosted/merchants/research/admin-summary
```

## Persist Merchant Registry

Set:

```bash
AIMIPAY_HOSTED_SQLITE_PATH=python/.docker-local/hosted-merchants.db
```

The app uses `SqliteHostedGatewayRegistry` when the variable is present.

## Merchant API Keys

Default demo keys:

- `research-secret`
- `coding-secret`

Override them:

```bash
AIMIPAY_RESEARCH_MERCHANT_KEY=...
AIMIPAY_CODING_MERCHANT_KEY=...
```

## Production Checklist

Before public deployment:

- Replace demo keys and addresses.
- Set admin tokens for each merchant gateway.
- Store hosted registry in managed Postgres or a durable SQLite volume.
- Put TLS and rate limiting in front of the service.
- Configure webhook delivery workers.
- Run `npm run preflight:security`.
- Run `PYTHONPATH=python python -m ops_tools.ai_host_smoke --json`.

## What This Is Not Yet

This hosted app is a deployment-shaped MVP. It is not yet a full hosted SaaS control plane. The next production layer should add tenant CRUD APIs, API key rotation, webhook delivery queues, hosted settlement workers, and organization billing.
