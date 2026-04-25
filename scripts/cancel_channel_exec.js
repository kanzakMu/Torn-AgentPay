const { TronWeb } = require("tronweb");

const { loadArtifact, loadPlan, createTronWeb } = require("./io");
const { cancelDigest, channelIdOf, signDigest } = require("./protocol");

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
  if (!buyerPrivateKey) throw new Error("missing buyer_private_key");

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
      channelSalt: plan.channel_salt,
      fullHost,
    });
  const digest = cancelDigest({
    contractAddress: plan.contract_address,
    chainId: parseChainId(plan.chain_id || process.env.TRON_CHAIN_ID),
    channelId,
    buyer: buyerAddress,
    seller: sellerAddress,
    token: plan.token_address,
    totalDeposit: BigInt(plan.total_deposit_atomic),
    expiresAt: BigInt(plan.expires_at),
    fullHost,
  });
  const buyerSignature = plan.buyer_signature || signDigest(buyerPrivateKey, digest);
  const sellerSignature = plan.seller_signature || signDigest(sellerPrivateKey, digest);

  const txId = await contract.cancelChannel(channelId, buyerSignature, sellerSignature).send();

  return {
    tx_id: txId,
    channel_id: channelId,
    channel_salt: plan.channel_salt,
    buyer_address: buyerAddress,
    seller_address: sellerAddress,
    token_address: plan.token_address,
    total_deposit_atomic: String(plan.total_deposit_atomic),
    expires_at: Number(plan.expires_at),
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
