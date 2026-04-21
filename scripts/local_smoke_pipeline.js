const fs = require("fs");
const hre = require("hardhat");
const { ethers } = hre;

const { buildRequestDigest, signDigest, voucherDigest } = require("./protocol");

const HARDHAT_MNEMONIC = process.env.HARDHAT_MNEMONIC || "test test test test test test test test test test test junk";

function loadOptionalPlan() {
  const argPlanFile = process.argv.slice(2).find((value) => value && value !== "--");
  const planFile = process.env.AIMICROPAY_PLAN_FILE || argPlanFile;
  if (!planFile) {
    return null;
  }
  return JSON.parse(fs.readFileSync(planFile, "utf8"));
}

function parseBigInt(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  return BigInt(value);
}

function walletFor(index) {
  return ethers.HDNodeWallet.fromPhrase(
    HARDHAT_MNEMONIC,
    undefined,
    `m/44'/60'/0'/0/${index}`,
  );
}

async function main() {
  const plan = loadOptionalPlan();
  const [buyer, seller] = await ethers.getSigners();
  const buyerWallet = walletFor(0);
  if (buyerWallet.address.toLowerCase() !== buyer.address.toLowerCase()) {
    throw new Error("derived buyer wallet does not match local signer; check HARDHAT_MNEMONIC");
  }
  if (plan?.buyer_address && plan.buyer_address.toLowerCase() !== buyer.address.toLowerCase()) {
    throw new Error("plan buyer_address does not match local hardhat buyer");
  }
  if (plan?.seller_address && plan.seller_address.toLowerCase() !== seller.address.toLowerCase()) {
    throw new Error("plan seller_address does not match local hardhat seller");
  }

  const claimAmount = parseBigInt(plan?.amount_atomic, BigInt(process.env.SMOKE_CLAIM_ATOMIC || "900000"));
  const totalDeposit = parseBigInt(
    plan?.deposit_atomic,
    parseBigInt(process.env.SMOKE_DEPOSIT_ATOMIC, claimAmount + 600_000n),
  );
  if (claimAmount > totalDeposit) {
    throw new Error("claim amount cannot exceed local smoke deposit");
  }
  const requestMethod = plan?.method || process.env.SMOKE_REQUEST_METHOD || "POST";
  const requestPath = plan?.path || process.env.SMOKE_REQUEST_PATH || "/tools/research";
  const requestBody = plan?.body || process.env.SMOKE_REQUEST_BODY || '{"topic":"tron"}';
  const ttlSeconds = Number(process.env.SMOKE_TTL_S || "3600");
  const requestTtlSeconds = Number(process.env.SMOKE_REQUEST_TTL_S || "120");

  const Token = await ethers.getContractFactory("MockUSDT6");
  const token = await Token.deploy(buyer.address, 5_000_000n);
  await token.waitForDeployment();

  const Channel = await ethers.getContractFactory("AimiMicropayChannel");
  const channel = await Channel.deploy();
  await channel.waitForDeployment();

  const latestBlock = await ethers.provider.getBlock("latest");
  const expiresAt = parseBigInt(plan?.expires_at, BigInt(latestBlock.timestamp + ttlSeconds));
  const requestDeadline = parseBigInt(plan?.request_deadline, BigInt(latestBlock.timestamp + requestTtlSeconds));

  const approveTx = await token.connect(buyer).approve(await channel.getAddress(), totalDeposit);
  await approveTx.wait();

  const openTx = await channel.connect(buyer).initializeChannel(
    seller.address,
    await token.getAddress(),
    totalDeposit,
    expiresAt,
  );
  await openTx.wait();

  const channelId = await channel.channelIdOf(buyer.address, seller.address, await token.getAddress());
  const chainId = (await ethers.provider.getNetwork()).chainId;
  const requestDigest =
    plan?.request_digest ||
    buildRequestDigest({
      method: requestMethod,
      path: requestPath,
      body: requestBody,
      requestDeadline: Number(requestDeadline),
    });
  const voucherNonce = parseBigInt(plan?.voucher_nonce, 1n);
  const digest = voucherDigest({
    contractAddress: await channel.getAddress(),
    chainId,
    channelId,
    buyer: buyer.address,
    seller: seller.address,
    token: await token.getAddress(),
    amountAtomic: claimAmount,
    nonce: voucherNonce,
    expiresAt,
    requestDeadline,
    requestDigest,
    fullHost: "http://127.0.0.1",
  });
  const buyerSignature = plan?.signature || signDigest(buyerWallet.privateKey, digest);

  const claimTx = await channel.connect(seller).claimPayment(
    channelId,
    claimAmount,
    voucherNonce,
    expiresAt,
    requestDeadline,
    requestDigest,
    buyerSignature,
  );
  await claimTx.wait();

  const channelState = await channel.paymentChannels(channelId);
  const sellerBalance = await token.balanceOf(seller.address);
  const buyerBalance = await token.balanceOf(buyer.address);

  if (plan) {
    return {
      tx_id: claimTx.hash,
      channel_id: channelId,
      buyer_address: buyer.address,
      seller_address: seller.address,
      token_address: await token.getAddress(),
      amount_atomic: claimAmount.toString(),
      voucher_nonce: Number(voucherNonce),
      request_deadline: Number(requestDeadline),
      request_digest: requestDigest,
      contract_address: await channel.getAddress(),
      approve_tx_id: approveTx.hash,
      open_tx_id: openTx.hash,
    };
  }

  return {
    network: hre.network.name,
    chain_id: Number(chainId),
    buyer_address: buyer.address,
    seller_address: seller.address,
    token_address: await token.getAddress(),
    contract_address: await channel.getAddress(),
    channel_id: channelId,
    total_deposit_atomic: totalDeposit.toString(),
    claim_amount_atomic: claimAmount.toString(),
    request_method: requestMethod,
    request_path: requestPath,
    request_body: requestBody,
    request_deadline: Number(requestDeadline),
    request_digest: requestDigest,
    approve_tx_id: approveTx.hash,
    open_tx_id: openTx.hash,
    claim_tx_id: claimTx.hash,
    seller_balance_atomic: sellerBalance.toString(),
    buyer_balance_atomic: buyerBalance.toString(),
    channel_active: channelState.isActive,
    channel_nonce: Number(channelState.nonce),
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
  HARDHAT_MNEMONIC,
  main,
  walletFor,
};
