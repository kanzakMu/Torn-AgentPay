const fs = require("fs");
const path = require("path");

const { TronWeb } = require("tronweb");

const TRC20_ABI = [
  {
    inputs: [
      { internalType: "address", name: "spender", type: "address" },
      { internalType: "uint256", name: "amount", type: "uint256" },
    ],
    name: "approve",
    outputs: [{ internalType: "bool", name: "", type: "bool" }],
    stateMutability: "nonpayable",
    type: "function",
  },
  {
    inputs: [{ internalType: "address", name: "account", type: "address" }],
    name: "balanceOf",
    outputs: [{ internalType: "uint256", name: "", type: "uint256" }],
    stateMutability: "view",
    type: "function",
  },
];

function projectRoot() {
  return path.resolve(__dirname, "..");
}

function artifactPath(contractFile, contractName) {
  return path.join(projectRoot(), "artifacts", "contracts", contractFile, `${contractName}.json`);
}

function loadArtifact(contractFile, contractName) {
  return JSON.parse(fs.readFileSync(artifactPath(contractFile, contractName), "utf8"));
}

function loadPlan() {
  const planFile = process.env.AIMICROPAY_PLAN_FILE || process.argv[2];
  if (!planFile) {
    throw new Error("missing AIMICROPAY_PLAN_FILE");
  }
  return JSON.parse(fs.readFileSync(planFile, "utf8"));
}

function createTronWeb({ fullHost, privateKey }) {
  const options = { fullHost };
  if (privateKey) {
    options.privateKey = String(privateKey).replace(/^0x/i, "");
  }
  if (process.env.TRON_PRO_API_KEY) {
    options.headers = { "TRON-PRO-API-KEY": process.env.TRON_PRO_API_KEY };
  }
  return new TronWeb(options);
}

module.exports = {
  TRC20_ABI,
  createTronWeb,
  loadArtifact,
  loadPlan,
};
