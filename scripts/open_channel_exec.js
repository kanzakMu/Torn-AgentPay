const { loadArtifact, loadPlan, createTronWeb, TRC20_ABI } = require("./io");

async function main() {
  const plan = loadPlan();
  const tronWeb = createTronWeb({
    fullHost: plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io",
    privateKey: plan.buyer_private_key || process.env.PRIVATE_KEY,
  });
  const artifact = loadArtifact("AimiMicropayChannel.sol", "AimiMicropayChannel");
  const depositAtomic = String(plan.deposit_atomic);
  const expiresAt = Number(plan.expires_at);

  const tokenContract = await tronWeb.contract(TRC20_ABI, plan.token_address);
  const channelContract = await tronWeb.contract(artifact.abi, plan.contract_address);

  const approveTx = await tokenContract.approve(plan.contract_address, depositAtomic).send();
  const initTx = await channelContract
    .initializeChannel(plan.seller_address, plan.token_address, depositAtomic, expiresAt)
    .send();

  const buyerAddress = tronWeb.defaultAddress.base58;
  const channelId = await channelContract.channelIdOf(buyerAddress, plan.seller_address, plan.token_address).call();
  return {
    approve_tx_id: approveTx,
    open_tx_id: initTx,
    buyer_address: buyerAddress,
    seller_address: plan.seller_address,
    token_address: plan.token_address,
    channel_id: channelId,
    contract_address: plan.contract_address,
    deposit_atomic: depositAtomic,
    expires_at: expiresAt,
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
