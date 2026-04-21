# Nile Launch Checklist

This checklist is the final staging gate before opening Tron Nile traffic.

## 1. Freeze Testnet Inputs

- copy [`python/target.nile.env.example`](./target.nile.env.example) into a private env file
- confirm the Nile seller address, seller private key, contract address, and token address are final
- confirm `AIMIPAY_SETTLEMENT_BACKEND=claim_script` and `AIMIPAY_CHAIN_ID=3448148188`

## 2. Fund Both Sides

- fund the seller wallet with TRX for gas
- fund the buyer wallet with TRX plus testnet USDT
- keep the faucet and funding guide nearby:
  - [Nile faucet](https://nileex.io/join/getJoinPage)
  - [TRON testnet token guide](https://developers.tron.network/docs/getting-testnet-tokens)

## 3. Run Preflight

- load the Nile env file
- run `python -m ops_tools.preflight_check --env-file ./python/target.nile.env --strict`
- if SQLite is in use, rerun with backup and snapshot outputs enabled
- do not proceed until every check is green

## 4. Dry Run Storage Safety

- export a fresh SQLite backup
- export a JSON snapshot
- import the snapshot into a scratch database and confirm counts match
- keep those artifacts available for rollback

## 5. Controlled Nile Traffic

- start with one operator-owned buyer wallet
- run a single route purchase end to end
- confirm:
  - payment intent reaches `authorized`
  - execute submits a real Nile transaction
  - reconcile moves `submitted` to `settled` or terminal `failed`
  - metrics and ops health stay green

## 6. Watch the Right Metrics

- `settlement_executed_total`
- `settlement_confirmed_total`
- `settlement_execution_failed_total`
- `settlement_confirmation_retry_exhausted_total`
- `worker_errors_total`
- `unfinished_payments`

If failures rise faster than confirmed settlements, pause rollout and inspect the seller wallet, RPC reachability, and chain addresses before retrying.
