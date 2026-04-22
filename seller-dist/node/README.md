# Torn-AgentPay Seller Node

This directory is the self-hosted seller node package for Torn-AgentPay.

It turns the existing seller runtime into a more explicit node distribution: bootstrap, runtime start, public manifest endpoints, and a seller console are all described from the operator point of view.

## Included Files

- `seller-node.manifest.json`
  Package metadata, expected entrypoints, and public endpoints.
- `docker-compose.seller-node.yml`
  Container-first deployment template.
- `.env.seller-node.example`
  Starter environment file for a self-hosted seller node.
- `bootstrap-seller-node.ps1`
  Prepare the Python and Node dependencies and create the local env.
- `run-seller-node.ps1`
  Start the seller node runtime.

## Quick Start

```powershell
powershell -ExecutionPolicy Bypass -File bootstrap-seller-node.ps1
powershell -ExecutionPolicy Bypass -File run-seller-node.ps1
```

Then open:

- `http://127.0.0.1:8000/aimipay/install`
- `http://127.0.0.1:8000/.well-known/aimipay.json`
- `http://127.0.0.1:8000/_aimipay/discover`

## Operational Notes

- The seller node remains self-hosted.
- Signed seller metadata is exposed in the manifest when a valid seller private key is configured.
- The package keeps some `merchant` names in env files and legacy compatibility flags, but the runtime is presented as a seller node.
