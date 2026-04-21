const crypto = require("crypto");
const { ethers } = require("ethers");
const { TronWeb } = require("tronweb");

const VOUCHER_DOMAIN = ethers.id("AIMICROPAY_V1");
const CANCEL_DOMAIN = ethers.id("AIMICROPAY_CANCEL_V1");

function tronWebInstance(fullHost) {
  return new TronWeb({ fullHost });
}

function normalizeTronAddress(value, fullHost) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error("address is required");
  }

  const input = value.trim();
  if (input.startsWith("0x") && input.length === 42) {
    return ethers.getAddress(input);
  }

  const hex = tronWebInstance(fullHost).address.toHex(input);
  if (typeof hex !== "string" || hex.length !== 42 || !hex.startsWith("41")) {
    throw new Error(`invalid Tron address: ${value}`);
  }
  return ethers.getAddress(`0x${hex.slice(2)}`);
}

function channelIdOf({ buyer, seller, token, fullHost }) {
  return ethers.solidityPackedKeccak256(
    ["address", "address", "address"],
    [
      normalizeTronAddress(buyer, fullHost),
      normalizeTronAddress(seller, fullHost),
      normalizeTronAddress(token, fullHost),
    ],
  );
}

function buildRequestDigest({ method, path, body, requestDeadline }) {
  const normalizedMethod = method.toUpperCase().trim();
  if (!normalizedMethod) {
    throw new Error("method is required");
  }
  if (!path.startsWith("/")) {
    throw new Error("path must start with '/'");
  }

  const methodBytes = Buffer.from(normalizedMethod, "ascii");
  const pathBytes = Buffer.from(path, "utf8");
  const bodyBytes = Buffer.isBuffer(body) ? body : Buffer.from(body || "", "utf8");
  const bodyHash = crypto.createHash("sha256").update(bodyBytes).digest();
  const payload = Buffer.concat([
    Buffer.from([methodBytes.length & 0xff, methodBytes.length >> 8]),
    methodBytes,
    Buffer.from([pathBytes.length & 0xff, pathBytes.length >> 8]),
    pathBytes,
    ethers.toBeArray(ethers.toTwos(BigInt(requestDeadline), 64)),
    bodyHash,
  ]);
  return `0x${crypto.createHash("sha256").update(payload).digest("hex")}`;
}

function voucherDigest({
  contractAddress,
  chainId,
  channelId,
  buyer,
  seller,
  token,
  amountAtomic,
  nonce,
  expiresAt,
  requestDeadline,
  requestDigest,
  fullHost,
}) {
  return ethers.keccak256(
    ethers.AbiCoder.defaultAbiCoder().encode(
      [
        "bytes32",
        "uint256",
        "address",
        "bytes32",
        "address",
        "address",
        "address",
        "uint256",
        "uint64",
        "uint64",
        "uint64",
        "bytes32",
      ],
      [
        VOUCHER_DOMAIN,
        BigInt(chainId),
        normalizeTronAddress(contractAddress, fullHost),
        channelId,
        normalizeTronAddress(buyer, fullHost),
        normalizeTronAddress(seller, fullHost),
        normalizeTronAddress(token, fullHost),
        BigInt(amountAtomic),
        BigInt(nonce),
        BigInt(expiresAt),
        BigInt(requestDeadline),
        requestDigest,
      ],
    ),
  );
}

function cancelDigest({
  contractAddress,
  chainId,
  channelId,
  buyer,
  seller,
  token,
  totalDeposit,
  expiresAt,
  fullHost,
}) {
  return ethers.keccak256(
    ethers.AbiCoder.defaultAbiCoder().encode(
      [
        "bytes32",
        "uint256",
        "address",
        "bytes32",
        "address",
        "address",
        "address",
        "uint256",
        "uint64",
      ],
      [
        CANCEL_DOMAIN,
        BigInt(chainId),
        normalizeTronAddress(contractAddress, fullHost),
        channelId,
        normalizeTronAddress(buyer, fullHost),
        normalizeTronAddress(seller, fullHost),
        normalizeTronAddress(token, fullHost),
        BigInt(totalDeposit),
        BigInt(expiresAt),
      ],
    ),
  );
}

function signDigest(privateKey, digest) {
  const wallet = new ethers.Wallet(privateKey.startsWith("0x") ? privateKey : `0x${privateKey}`);
  const signature = wallet.signingKey.sign(digest);
  return ethers.Signature.from(signature).serialized;
}

module.exports = {
  buildRequestDigest,
  cancelDigest,
  channelIdOf,
  normalizeTronAddress,
  signDigest,
  tronWebInstance,
  voucherDigest,
};
