# Buyer Funding Checklist

Use this checklist after AimiPay creates a buyer wallet for an agent.

## Local Demo

- `local_smoke` does not require live Tron funding
- run:
  `powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1`

## Nile or Live Tron

1. Confirm the buyer wallet exists
   - `python -m ops_tools.wallet_setup --force-create`
2. Check current funding guidance
   - `python -m ops_tools.wallet_funding`
3. Make sure the wallet has:
   - TRX for gas
   - USDT for payments
4. If you are on a testnet, use the configured faucet from your env file
5. Re-run:
   - `python -m ops_tools.install_doctor`
   - `python -m ops_tools.wallet_funding`

## Recommended Minimums

- `AIMIPAY_MIN_TRX_BALANCE_SUN`
  Default: `1000000`
- `AIMIPAY_MIN_TOKEN_BALANCE_ATOMIC`
  Default: `1000000`

Adjust these thresholds in `python/.env.local` or `python/target.env` when your deployment needs more headroom.
