const { loadArtifact, createTronWeb } = require("./io");

async function main() {
  const fullHost = process.env.FULL_HOST || "https://nile.trongrid.io";
  const privateKey = process.env.PRIVATE_KEY;
  if (!privateKey) {
    throw new Error("missing PRIVATE_KEY");
  }

  const tronWeb = createTronWeb({ fullHost, privateKey });
  const artifact = loadArtifact("AimiMicropayChannel.sol", "AimiMicropayChannel");

  const instance = await tronWeb.contract().new({
    abi: artifact.abi,
    bytecode: artifact.bytecode.replace(/^0x/, ""),
    feeLimit: Number(process.env.FEE_LIMIT || 2_000_000_000),
    userFeePercentage: Number(process.env.USER_FEE_PERCENTAGE || 100),
    originEnergyLimit: Number(process.env.ORIGIN_ENERGY_LIMIT || 10_000_000),
  });

  process.stdout.write(
    `${JSON.stringify({
      full_host: fullHost,
      contract_address: instance.address,
      owner_address: tronWeb.defaultAddress.base58,
    })}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
