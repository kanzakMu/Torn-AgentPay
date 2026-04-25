const { expect } = require("chai");
const { ethers } = require("hardhat");

const { buildRequestDigest, cancelDigest, voucherDigest, signDigest } = require("../scripts/protocol");

const HARDHAT_MNEMONIC = "test test test test test test test test test test test junk";
const DEFAULT_CHANNEL_SALT = "0x" + "11".repeat(32);

describe("AimiMicropayChannel", function () {
  async function expectCustomError(txPromise, errorName) {
    try {
      await txPromise;
      expect.fail(`expected custom error ${errorName}`);
    } catch (error) {
      expect(String(error)).to.include(errorName);
    }
  }

  function walletFor(index) {
    return ethers.HDNodeWallet.fromPhrase(
      HARDHAT_MNEMONIC,
      undefined,
      `m/44'/60'/0'/0/${index}`,
    );
  }

  async function deployFixture() {
    const [buyer, seller, other] = await ethers.getSigners();

    const Token = await ethers.getContractFactory("MockUSDT6");
    const token = await Token.deploy(buyer.address, 5_000_000n);
    await token.waitForDeployment();

    const Channel = await ethers.getContractFactory("AimiMicropayChannel");
    const channel = await Channel.deploy();
    await channel.waitForDeployment();

    return { buyer, seller, other, token, channel };
  }

  async function openChannelFixture() {
    const fixture = await deployFixture();
    const { buyer, seller, token, channel } = fixture;
    const totalDeposit = 1_500_000n;
    const expiresAt = BigInt((await ethers.provider.getBlock("latest")).timestamp + 3600);

    await token.connect(buyer).approve(await channel.getAddress(), totalDeposit);
    await channel.connect(buyer).initializeChannel(
      seller.address,
      await token.getAddress(),
      totalDeposit,
      expiresAt,
      DEFAULT_CHANNEL_SALT,
    );

    const channelId = await channel.channelIdOf(buyer.address, seller.address, await token.getAddress(), DEFAULT_CHANNEL_SALT);
    return { ...fixture, channelId, totalDeposit, expiresAt, channelSalt: DEFAULT_CHANNEL_SALT };
  }

  async function buildVoucherPayload({
    buyer,
    seller,
    token,
    channel,
    channelId,
    amountAtomic,
    voucherNonce,
    expiresAt,
    requestDeadline,
    method = "POST",
    path = "/tools/market-data",
    body = '{"query":"market-data"}',
  }) {
    const buyerWallet = walletFor(0);
    const requestDigest = buildRequestDigest({
      method,
      path,
      body: Buffer.from(body, "utf8"),
      requestDeadline: Number(requestDeadline),
    });
    const digest = voucherDigest({
      contractAddress: await channel.getAddress(),
      chainId: (await ethers.provider.getNetwork()).chainId,
      channelId,
      buyer: buyer.address,
      seller: seller.address,
      token: await token.getAddress(),
      amountAtomic,
      nonce: voucherNonce,
      expiresAt,
      requestDeadline,
      requestDigest,
    });
    const buyerSignature = signDigest(buyerWallet.privateKey, digest);
    return { requestDigest, buyerSignature };
  }

  it("initializes a payment channel and escrows the deposit", async function () {
    const { buyer, seller, token, channel, channelId, totalDeposit, expiresAt } = await openChannelFixture();
    const state = await channel.paymentChannels(channelId);

    expect(state.buyer).to.equal(buyer.address);
    expect(state.seller).to.equal(seller.address);
    expect(state.token).to.equal(await token.getAddress());
    expect(state.totalDeposit).to.equal(totalDeposit);
    expect(state.nonce).to.equal(0n);
    expect(state.expiresAt).to.equal(expiresAt);
    expect(state.isActive).to.equal(true);
    expect(await token.balanceOf(await channel.getAddress())).to.equal(totalDeposit);
  });

  it("claims payment with a buyer-signed voucher and closes the channel", async function () {
    const { buyer, seller, token, channel, channelId, totalDeposit, expiresAt } = await openChannelFixture();
    const requestDeadline = BigInt((await ethers.provider.getBlock("latest")).timestamp + 120);
    const claimAmount = 900_000n;
    const voucherNonce = 1n;
    const { requestDigest, buyerSignature } = await buildVoucherPayload({
      buyer,
      seller,
      token,
      channel,
      channelId,
      amountAtomic: claimAmount,
      voucherNonce,
      expiresAt,
      requestDeadline,
    });

    await channel.connect(seller).claimPayment(
      channelId,
      claimAmount,
      voucherNonce,
      expiresAt,
      requestDeadline,
      requestDigest,
      buyerSignature,
    );

    expect(await token.balanceOf(seller.address)).to.equal(claimAmount);
    expect(await token.balanceOf(buyer.address)).to.equal(5_000_000n - totalDeposit + (totalDeposit - claimAmount));

    const state = await channel.paymentChannels(channelId);
    expect(state.isActive).to.equal(false);
    expect(state.totalDeposit).to.equal(0n);
    expect(state.nonce).to.equal(voucherNonce);
  });

  it("rejects a voucher signed by the wrong buyer", async function () {
    const { buyer, seller, token, channel, channelId, expiresAt } = await openChannelFixture();
    const wrongWallet = walletFor(2);
    const requestDeadline = BigInt((await ethers.provider.getBlock("latest")).timestamp + 120);
    const claimAmount = 900_000n;
    const voucherNonce = 1n;
    const requestDigest = buildRequestDigest({
      method: "POST",
      path: "/tools/market-data",
      body: Buffer.from('{"query":"market-data"}', "utf8"),
      requestDeadline: Number(requestDeadline),
    });
    const digest = voucherDigest({
      contractAddress: await channel.getAddress(),
      chainId: (await ethers.provider.getNetwork()).chainId,
      channelId,
      buyer: buyer.address,
      seller: seller.address,
      token: await token.getAddress(),
      amountAtomic: claimAmount,
      nonce: voucherNonce,
      expiresAt,
      requestDeadline,
      requestDigest,
    });
    const invalidSignature = signDigest(wrongWallet.privateKey, digest);

    await expectCustomError(
      channel.connect(seller).claimPayment(
        channelId,
        claimAmount,
        voucherNonce,
        expiresAt,
        requestDeadline,
        requestDigest,
        invalidSignature,
      ),
      "InvalidVoucherSigner",
    );
  });

  it("rejects nonce replay on a claimed channel", async function () {
    const { buyer, seller, token, channel, channelId, expiresAt } = await openChannelFixture();
    const requestDeadline = BigInt((await ethers.provider.getBlock("latest")).timestamp + 120);
    const claimAmount = 900_000n;
    const voucherNonce = 1n;
    const { requestDigest, buyerSignature } = await buildVoucherPayload({
      buyer,
      seller,
      token,
      channel,
      channelId,
      amountAtomic: claimAmount,
      voucherNonce,
      expiresAt,
      requestDeadline,
    });

    await channel.connect(seller).claimPayment(
      channelId,
      claimAmount,
      voucherNonce,
      expiresAt,
      requestDeadline,
      requestDigest,
      buyerSignature,
    );

    await expectCustomError(
      channel.connect(seller).claimPayment(
        channelId,
        claimAmount,
        voucherNonce,
        expiresAt,
        requestDeadline,
        requestDigest,
        buyerSignature,
      ),
      "ChannelInactive",
    );
  });

  it("rejects claims that exceed the escrowed deposit", async function () {
    const { buyer, seller, token, channel, channelId, totalDeposit, expiresAt } = await openChannelFixture();
    const requestDeadline = BigInt((await ethers.provider.getBlock("latest")).timestamp + 120);
    const claimAmount = totalDeposit + 1n;
    const voucherNonce = 1n;
    const { requestDigest, buyerSignature } = await buildVoucherPayload({
      buyer,
      seller,
      token,
      channel,
      channelId,
      amountAtomic: claimAmount,
      voucherNonce,
      expiresAt,
      requestDeadline,
    });

    await expectCustomError(
      channel.connect(seller).claimPayment(
        channelId,
        claimAmount,
        voucherNonce,
        expiresAt,
        requestDeadline,
        requestDigest,
        buyerSignature,
      ),
      "ClaimExceedsDeposit",
    );
  });

  it("rejects vouchers after the request deadline has expired", async function () {
    const { buyer, seller, token, channel, channelId, expiresAt } = await openChannelFixture();
    const currentTimestamp = (await ethers.provider.getBlock("latest")).timestamp;
    const requestDeadline = BigInt(currentTimestamp + 2);
    const claimAmount = 900_000n;
    const voucherNonce = 1n;
    const { requestDigest, buyerSignature } = await buildVoucherPayload({
      buyer,
      seller,
      token,
      channel,
      channelId,
      amountAtomic: claimAmount,
      voucherNonce,
      expiresAt,
      requestDeadline,
    });

    await ethers.provider.send("evm_increaseTime", [3]);
    await ethers.provider.send("evm_mine");

    await expectCustomError(
      channel.connect(seller).claimPayment(
        channelId,
        claimAmount,
        voucherNonce,
        expiresAt,
        requestDeadline,
        requestDigest,
        buyerSignature,
      ),
      "RequestDeadlineExpired",
    );
  });

  it("closes an expired channel and refunds the buyer", async function () {
    const { buyer, seller, token, channel } = await deployFixture();
    const totalDeposit = 1_200_000n;
    const now = (await ethers.provider.getBlock("latest")).timestamp;
    const expiresAt = BigInt(now + 3);

    await token.connect(buyer).approve(await channel.getAddress(), totalDeposit);
    await channel.connect(buyer).initializeChannel(
      seller.address,
      await token.getAddress(),
      totalDeposit,
      expiresAt,
      DEFAULT_CHANNEL_SALT,
    );
    const channelId = await channel.channelIdOf(buyer.address, seller.address, await token.getAddress(), DEFAULT_CHANNEL_SALT);

    await ethers.provider.send("evm_increaseTime", [5]);
    await ethers.provider.send("evm_mine");

    await channel.connect(buyer).closeChannel(channelId);

    expect(await token.balanceOf(buyer.address)).to.equal(5_000_000n);
    const state = await channel.paymentChannels(channelId);
    expect(state.isActive).to.equal(false);
    expect(state.totalDeposit).to.equal(0n);
  });

  it("cancels an active channel early with buyer and seller signatures", async function () {
    const { buyer, seller, token, channel, channelId, totalDeposit, expiresAt } = await openChannelFixture();
    const buyerWallet = walletFor(0);
    const sellerWallet = walletFor(1);
    const digest = cancelDigest({
      contractAddress: await channel.getAddress(),
      chainId: (await ethers.provider.getNetwork()).chainId,
      channelId,
      buyer: buyer.address,
      seller: seller.address,
      token: await token.getAddress(),
      totalDeposit,
      expiresAt,
    });
    const buyerSignature = signDigest(buyerWallet.privateKey, digest);
    const sellerSignature = signDigest(sellerWallet.privateKey, digest);

    await channel.connect(seller).cancelChannel(channelId, buyerSignature, sellerSignature);

    expect(await token.balanceOf(buyer.address)).to.equal(5_000_000n);
    const state = await channel.paymentChannels(channelId);
    expect(state.isActive).to.equal(false);
    expect(state.totalDeposit).to.equal(0n);
  });

  it("does not let a voucher from one channel salt claim a later channel", async function () {
    const { buyer, seller, token, channel } = await deployFixture();
    const totalDeposit = 1_500_000n;
    const expiresAt = BigInt((await ethers.provider.getBlock("latest")).timestamp + 3600);
    const firstSalt = "0x" + "aa".repeat(32);
    const secondSalt = "0x" + "bb".repeat(32);

    await token.connect(buyer).approve(await channel.getAddress(), totalDeposit);
    await channel.connect(buyer).initializeChannel(seller.address, await token.getAddress(), totalDeposit, expiresAt, firstSalt);
    const firstChannelId = await channel.channelIdOf(buyer.address, seller.address, await token.getAddress(), firstSalt);
    const requestDeadline = BigInt((await ethers.provider.getBlock("latest")).timestamp + 120);
    const claimAmount = 900_000n;
    const { requestDigest, buyerSignature } = await buildVoucherPayload({
      buyer,
      seller,
      token,
      channel,
      channelId: firstChannelId,
      amountAtomic: claimAmount,
      voucherNonce: 1n,
      expiresAt,
      requestDeadline,
    });

    await channel.connect(seller).cancelChannel(
      firstChannelId,
      signDigest(walletFor(0).privateKey, cancelDigest({
        contractAddress: await channel.getAddress(),
        chainId: (await ethers.provider.getNetwork()).chainId,
        channelId: firstChannelId,
        buyer: buyer.address,
        seller: seller.address,
        token: await token.getAddress(),
        totalDeposit,
        expiresAt,
      })),
      signDigest(walletFor(1).privateKey, cancelDigest({
        contractAddress: await channel.getAddress(),
        chainId: (await ethers.provider.getNetwork()).chainId,
        channelId: firstChannelId,
        buyer: buyer.address,
        seller: seller.address,
        token: await token.getAddress(),
        totalDeposit,
        expiresAt,
      })),
    );

    await token.connect(buyer).approve(await channel.getAddress(), totalDeposit);
    await channel.connect(buyer).initializeChannel(seller.address, await token.getAddress(), totalDeposit, expiresAt, secondSalt);
    const secondChannelId = await channel.channelIdOf(buyer.address, seller.address, await token.getAddress(), secondSalt);

    await expectCustomError(
      channel.connect(seller).claimPayment(
        secondChannelId,
        claimAmount,
        1n,
        expiresAt,
        requestDeadline,
        requestDigest,
        buyerSignature,
      ),
      "InvalidVoucherSigner",
    );
  });

  it("rejects opening two active channels with the same salt", async function () {
    const { buyer, seller, token, channel } = await deployFixture();
    const totalDeposit = 1_500_000n;
    const expiresAt = BigInt((await ethers.provider.getBlock("latest")).timestamp + 3600);
    const salt = "0x" + "44".repeat(32);

    await token.connect(buyer).approve(await channel.getAddress(), totalDeposit * 2n);
    await channel.connect(buyer).initializeChannel(seller.address, await token.getAddress(), totalDeposit, expiresAt, salt);

    await expectCustomError(
      channel.connect(buyer).initializeChannel(seller.address, await token.getAddress(), totalDeposit, expiresAt, salt),
      "ChannelAlreadyActive",
    );
  });

  it("preserves token supply across claim and refund flows", async function () {
    const { buyer, seller, token, channel } = await deployFixture();
    const totalSupply = await token.totalSupply();
    const totalDeposit = 1_500_000n;
    const expiresAt = BigInt((await ethers.provider.getBlock("latest")).timestamp + 3600);
    const salt = "0x" + "55".repeat(32);
    const claimAmount = 700_000n;
    const requestDeadline = BigInt((await ethers.provider.getBlock("latest")).timestamp + 120);

    await token.connect(buyer).approve(await channel.getAddress(), totalDeposit);
    await channel.connect(buyer).initializeChannel(seller.address, await token.getAddress(), totalDeposit, expiresAt, salt);
    const channelId = await channel.channelIdOf(buyer.address, seller.address, await token.getAddress(), salt);
    const { requestDigest, buyerSignature } = await buildVoucherPayload({
      buyer,
      seller,
      token,
      channel,
      channelId,
      amountAtomic: claimAmount,
      voucherNonce: 1n,
      expiresAt,
      requestDeadline,
    });

    await channel.connect(seller).claimPayment(
      channelId,
      claimAmount,
      1n,
      expiresAt,
      requestDeadline,
      requestDigest,
      buyerSignature,
    );

    const combined = (
      await token.balanceOf(buyer.address)
    ) + (await token.balanceOf(seller.address)) + (await token.balanceOf(await channel.getAddress()));
    expect(combined).to.equal(totalSupply);
    expect(await token.balanceOf(await channel.getAddress())).to.equal(0n);
  });
});
