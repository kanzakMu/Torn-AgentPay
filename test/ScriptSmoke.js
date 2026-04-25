const { expect } = require("chai");

function patchExports(modulePath, overrides) {
  const target = require(modulePath);
  const originals = {};
  for (const [key, value] of Object.entries(overrides)) {
    originals[key] = target[key];
    target[key] = value;
  }
  return () => {
    for (const [key, value] of Object.entries(originals)) {
      target[key] = value;
    }
  };
}

describe("script smoke tests", function () {
  afterEach(function () {
    delete require.cache[require.resolve("../scripts/open_channel_exec")];
    delete require.cache[require.resolve("../scripts/claim_payment_exec")];
  });

  it("open_channel_exec emits the expected payload shape", async function () {
    const plan = {
      full_host: "http://tron.local",
      buyer_private_key: "buyer_pk",
      seller_address: "TRX_SELLER",
      token_address: "TRX_USDT",
      contract_address: "TRX_CONTRACT",
      deposit_atomic: 1_000_000,
      expires_at: 1_700_000_100,
      channel_salt: "0x" + "11".repeat(32),
    };

    const restoreIo = patchExports(require.resolve("../scripts/io"), {
      loadPlan: () => plan,
      loadArtifact: () => ({ abi: ["channel_abi"] }),
      createTronWeb: () => ({
        defaultAddress: { base58: "TRX_BUYER" },
        contract: async (_abi, address) => {
          if (address === plan.token_address) {
            return {
              approve: (contractAddress, amount) => ({
                send: async () => {
                  expect(contractAddress).to.equal(plan.contract_address);
                  expect(amount).to.equal(String(plan.deposit_atomic));
                  return "approve_tx_1";
                },
              }),
            };
          }
          return {
            initializeChannel: (seller, token, amount, expiresAt, channelSalt) => ({
              send: async () => {
                expect(seller).to.equal(plan.seller_address);
                expect(token).to.equal(plan.token_address);
                expect(amount).to.equal(String(plan.deposit_atomic));
                expect(expiresAt).to.equal(plan.expires_at);
                expect(channelSalt).to.equal(plan.channel_salt);
                return "open_tx_1";
              },
            }),
            channelIdOf: (buyer, seller, token, channelSalt) => ({
              call: async () => {
                expect(buyer).to.equal("TRX_BUYER");
                expect(seller).to.equal(plan.seller_address);
                expect(token).to.equal(plan.token_address);
                expect(channelSalt).to.equal(plan.channel_salt);
                return "channel_1";
              },
            }),
          };
        },
      }),
    });

    try {
      const script = require("../scripts/open_channel_exec");
      const payload = await script.main();
      expect(payload).to.deep.equal({
        approve_tx_id: "approve_tx_1",
        open_tx_id: "open_tx_1",
        buyer_address: "TRX_BUYER",
        seller_address: "TRX_SELLER",
        token_address: "TRX_USDT",
        channel_id: "channel_1",
        channel_salt: plan.channel_salt,
        contract_address: "TRX_CONTRACT",
        deposit_atomic: "1000000",
        expires_at: 1_700_000_100,
      });
    } finally {
      restoreIo();
    }
  });

  it("claim_payment_exec emits the expected payload shape", async function () {
    const plan = {
      full_host: "http://tron.local",
      seller_private_key: "seller_pk",
      buyer_address: "TRX_BUYER",
      seller_address: "TRX_SELLER",
      contract_address: "TRX_CONTRACT",
      token_address: "TRX_USDT",
      channel_id: "channel_1",
      amount_atomic: 250000,
      voucher_nonce: 7,
      expires_at: 1_700_000_500,
      request_deadline: 1_700_000_100,
      request_digest: "0xdigest_1",
      signature: "0xsig_1",
      chain_id: 728126428,
    };

    const restoreIo = patchExports(require.resolve("../scripts/io"), {
      loadPlan: () => plan,
      loadArtifact: () => ({ abi: ["channel_abi"] }),
      createTronWeb: () => ({
        defaultAddress: { base58: "TRX_SELLER" },
        contract: async () => ({
          claimPayment: (
            channelId,
            amountAtomic,
            voucherNonce,
            expiresAt,
            requestDeadline,
            requestDigest,
            buyerSignature,
          ) => ({
            send: async () => {
              expect(channelId).to.equal("channel_1");
              expect(amountAtomic).to.equal("250000");
              expect(voucherNonce).to.equal(7);
              expect(expiresAt).to.equal(1_700_000_500);
              expect(requestDeadline).to.equal(1_700_000_100);
              expect(requestDigest).to.equal("0xdigest_1");
              expect(buyerSignature).to.equal("0xsig_1");
              return "claim_tx_1";
            },
          }),
        }),
      }),
    });
    const restoreProtocol = patchExports(require.resolve("../scripts/protocol"), {
      buildRequestDigest: () => {
        throw new Error("unexpected request digest build");
      },
      channelIdOf: () => {
        throw new Error("unexpected channel id build");
      },
      voucherDigest: () => "0xvoucher_1",
      signDigest: () => {
        throw new Error("unexpected signature build");
      },
    });

    try {
      const script = require("../scripts/claim_payment_exec");
      const payload = await script.main();
      expect(payload).to.deep.equal({
        tx_id: "claim_tx_1",
        channel_id: "channel_1",
        buyer_address: "TRX_BUYER",
        seller_address: "TRX_SELLER",
        token_address: "TRX_USDT",
        amount_atomic: "250000",
        voucher_nonce: 7,
        request_deadline: 1_700_000_100,
        request_digest: "0xdigest_1",
      });
    } finally {
      restoreProtocol();
      restoreIo();
    }
  });
});
