const { loadPlan } = require("./io");
const { buildRequestDigest, signDigest, voucherDigest } = require("./protocol");

async function main() {
  const plan = loadPlan();
  if (!plan.buyer_private_key) {
    throw new Error("missing buyer_private_key");
  }
  if (!plan.chain_id) {
    throw new Error("missing chain_id");
  }

  const requestDeadline = Number(plan.request_deadline);
  const requestDigest =
    plan.request_digest ||
    buildRequestDigest({
      method: plan.method || "POST",
      path: plan.path || "/",
      body: plan.body || "",
      requestDeadline,
    });
  const digest = voucherDigest({
    contractAddress: plan.contract_address,
    chainId: BigInt(plan.chain_id),
    channelId: plan.channel_id,
    buyer: plan.buyer_address,
    seller: plan.seller_address,
    token: plan.token_address,
    amountAtomic: BigInt(plan.amount_atomic),
    nonce: BigInt(plan.voucher_nonce),
    expiresAt: BigInt(plan.expires_at),
    requestDeadline: BigInt(requestDeadline),
    requestDigest,
    fullHost: plan.full_host || "http://127.0.0.1",
  });
  const signature = signDigest(plan.buyer_private_key, digest);

  return {
    request_digest: requestDigest,
    voucher_digest: digest,
    buyer_signature: signature,
  };
}

if (require.main === module) {
  main()
    .then((payload) => {
      process.stdout.write(`${JSON.stringify(payload)}\n`);
    })
    .catch((error) => {
      process.stderr.write(`${error.stack || error}\n`);
      process.exit(1);
    });
}

module.exports = {
  main,
};
