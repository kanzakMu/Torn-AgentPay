const fs = require("fs");

const { TRC20_ABI, createTronWeb, loadPlan } = require("./io");

async function main() {
  const plan = loadPlan();
  if (!plan.full_host) {
    throw new Error("missing full_host");
  }
  if (!plan.buyer_address) {
    throw new Error("missing buyer_address");
  }

  const tronWeb = createTronWeb({ fullHost: plan.full_host });
  const result = {
    full_host: plan.full_host,
    buyer_address: plan.buyer_address,
    token_address: plan.token_address || null,
    trx_balance_sun: null,
    token_balance_atomic: null,
    token_probe_status: "skipped",
  };

  const trxBalance = await tronWeb.trx.getBalance(plan.buyer_address);
  result.trx_balance_sun = String(trxBalance);

  if (plan.token_address && !String(plan.token_address).startsWith("TRX_")) {
    const tokenContract = await tronWeb.contract(TRC20_ABI, plan.token_address);
    const tokenBalance = await tokenContract.balanceOf(plan.buyer_address).call();
    result.token_balance_atomic = String(tokenBalance);
    result.token_probe_status = "ok";
  }

  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exit(1);
});
