const { TronWeb } = require("tronweb");

const { loadArtifact, loadPlan, createTronWeb } = require("./io");
const { channelIdOf } = require("./protocol");

async function main() {
  const plan = loadPlan();
  const fullHost = plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io";
  const buyerPrivateKey = plan.buyer_private_key || process.env.PRIVATE_KEY;
  if (!buyerPrivateKey) throw new Error("missing buyer_private_key");

  const tronWeb = createTronWeb({ fullHost, privateKey: buyerPrivateKey });
  const artifact = loadArtifact("AimiMicropayChannel.sol", "AimiMicropayChannel");
  const contract = await tronWeb.contract(artifact.abi, plan.contract_address);

  const buyerAddress = plan.buyer_address || TronWeb.address.fromPrivateKey(buyerPrivateKey);
  const channelId =
    plan.channel_id ||
    channelIdOf({
      buyer: buyerAddress,
      seller: plan.seller_address,
      token: plan.token_address,
      fullHost,
    });

  const txId = await contract.closeChannel(channelId).send();

  return {
    tx_id: txId,
    channel_id: channelId,
    buyer_address: buyerAddress,
    seller_address: plan.seller_address,
    token_address: plan.token_address,
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
