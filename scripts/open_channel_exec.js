const { ethers } = require("ethers");

const { loadArtifact, loadPlan, createTronWeb, TRC20_ABI } = require("./io");
const { channelIdOf } = require("./protocol");

async function main() {
  const plan = loadPlan();
  const tronWeb = createTronWeb({
    fullHost: plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io",
    privateKey: plan.buyer_private_key || process.env.PRIVATE_KEY,
  });
  const artifact = loadArtifact("AimiMicropayChannel.sol", "AimiMicropayChannel");
  const depositAtomic = String(plan.deposit_atomic);
  const expiresAt = Number(plan.expires_at);
  const channelSalt = plan.channel_salt || ethers.hexlify(ethers.randomBytes(32));

  const tokenContract = await tronWeb.contract(TRC20_ABI, plan.token_address);
  const channelContract = await tronWeb.contract(artifact.abi, plan.contract_address);
  const feeLimit = Number(plan.fee_limit || process.env.FEE_LIMIT || 2_000_000_000);

  const approveTx = await tokenContract.approve(plan.contract_address, depositAtomic).send({ feeLimit });
  await waitForConfirmedTransaction(tronWeb, approveTx, {
    attempts: Number(plan.confirmation_attempts || process.env.AIMIPAY_MAX_CONFIRMATION_ATTEMPTS || 12),
    delayMs: Number(plan.confirmation_delay_ms || process.env.AIMIPAY_CONFIRMATION_DELAY_MS || 3000),
  });
  const initTx = await channelContract
    .initializeChannel(plan.seller_address, plan.token_address, depositAtomic, expiresAt, channelSalt)
    .send({ feeLimit });
  await waitForConfirmedTransaction(tronWeb, initTx, {
    attempts: Number(plan.confirmation_attempts || process.env.AIMIPAY_MAX_CONFIRMATION_ATTEMPTS || 12),
    delayMs: Number(plan.confirmation_delay_ms || process.env.AIMIPAY_CONFIRMATION_DELAY_MS || 3000),
  });

  const buyerAddress = tronWeb.defaultAddress.base58;
  const channelId = await resolveChannelId({
    channelContract,
    buyerAddress,
    sellerAddress: plan.seller_address,
    tokenAddress: plan.token_address,
    channelSalt,
    fullHost: plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io",
  });
  return {
    approve_tx_id: approveTx,
    open_tx_id: initTx,
    buyer_address: buyerAddress,
    seller_address: plan.seller_address,
    token_address: plan.token_address,
    channel_id: channelId,
    channel_salt: channelSalt,
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

async function waitForConfirmedTransaction(tronWeb, txId, { attempts, delayMs }) {
  if (!tronWeb.trx || typeof tronWeb.trx.getTransactionInfo !== "function") {
    return null;
  }
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const info = await tronWeb.trx.getTransactionInfo(txId);
    if (info && Object.keys(info).length > 0) {
      const receipt = info.receipt || {};
      const result = receipt.result || info.result || "SUCCESS";
      if (result !== "SUCCESS") {
        throw new Error(`transaction ${txId} failed with result ${result}`);
      }
      return info;
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  throw new Error(`transaction ${txId} was not confirmed after ${attempts} attempts`);
}

async function resolveChannelId({ channelContract, buyerAddress, sellerAddress, tokenAddress, channelSalt, fullHost }) {
  try {
    if (typeof channelContract.channelIdOf === "function") {
      return await channelContract.channelIdOf(buyerAddress, sellerAddress, tokenAddress, channelSalt).call();
    }
  } catch (_error) {
    // Some older Nile deployments or RPC constant-call paths may reject the pure helper.
  }
  return channelIdOf({
    buyer: buyerAddress,
    seller: sellerAddress,
    token: tokenAddress,
    channelSalt,
    fullHost,
  });
}
