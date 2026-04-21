const { TronWeb } = require("tronweb");

const { loadArtifact, loadPlan, createTronWeb } = require("./io");
const { buildRequestDigest, channelIdOf, signDigest, voucherDigest } = require("./protocol");

function parseChainId(value) {
  if (value === undefined || value === null || value === "") {
    throw new Error("missing chain_id");
  }
  return BigInt(value);
}

async function main() {
  const plan = loadPlan();
  const fullHost = plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io";
  const sellerPrivateKey = plan.seller_private_key || process.env.PRIVATE_KEY;
  const buyerPrivateKey = plan.buyer_private_key;
  if (!sellerPrivateKey) throw new Error("missing seller_private_key");
  if (!buyerPrivateKey && !plan.signature) throw new Error("missing buyer_private_key or signature");

  const tronWeb = createTronWeb({ fullHost, privateKey: sellerPrivateKey });
  const artifact = loadArtifact("AimiMicropayChannel.sol", "AimiMicropayChannel");
  const contract = await tronWeb.contract(artifact.abi, plan.contract_address);

  const buyerAddress = plan.buyer_address || TronWeb.address.fromPrivateKey(buyerPrivateKey);
  const sellerAddress = plan.seller_address || tronWeb.defaultAddress.base58;
  const channelId =
    plan.channel_id ||
    channelIdOf({
      buyer: buyerAddress,
      seller: sellerAddress,
      token: plan.token_address,
      fullHost,
    });
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
    chainId: parseChainId(plan.chain_id || process.env.TRON_CHAIN_ID),
    channelId,
    buyer: buyerAddress,
    seller: sellerAddress,
    token: plan.token_address,
    amountAtomic: BigInt(plan.amount_atomic),
    nonce: BigInt(plan.voucher_nonce),
    expiresAt: BigInt(plan.expires_at),
    requestDeadline: BigInt(requestDeadline),
    requestDigest,
    fullHost,
  });
  const buyerSignature = plan.signature || signDigest(buyerPrivateKey, digest);

  const txId = await contract
    .claimPayment(
      channelId,
      String(plan.amount_atomic),
      Number(plan.voucher_nonce),
      Number(plan.expires_at),
      requestDeadline,
      requestDigest,
      buyerSignature,
    )
    .send();

  return {
    tx_id: txId,
    channel_id: channelId,
    buyer_address: buyerAddress,
    seller_address: sellerAddress,
    token_address: plan.token_address,
    amount_atomic: String(plan.amount_atomic),
    voucher_nonce: Number(plan.voucher_nonce),
    request_deadline: requestDeadline,
    request_digest: requestDigest,
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
  parseChainId,
};
