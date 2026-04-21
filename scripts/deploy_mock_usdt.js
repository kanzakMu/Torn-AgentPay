const { loadArtifact, createTronWeb } = require("./io");

async function main() {
  const fullHost = process.env.FULL_HOST || "https://nile.trongrid.io";
  const privateKey = process.env.PRIVATE_KEY;
  if (!privateKey) {
    throw new Error("missing PRIVATE_KEY");
  }

  const tronWeb = createTronWeb({ fullHost, privateKey });
  const artifact = loadArtifact("MockUSDT6.sol", "MockUSDT6");
  const initialSupply = String(process.env.INITIAL_SUPPLY || "1000000000000");

  const instance = await tronWeb.contract().new({
    abi: artifact.abi,
    bytecode: artifact.bytecode.replace(/^0x/, ""),
    feeLimit: Number(process.env.FEE_LIMIT || 2_000_000_000),
    userFeePercentage: Number(process.env.USER_FEE_PERCENTAGE || 100),
    originEnergyLimit: Number(process.env.ORIGIN_ENERGY_LIMIT || 10_000_000),
    parameters: [tronWeb.defaultAddress.base58, initialSupply],
  });

  process.stdout.write(
    `${JSON.stringify({
      full_host: fullHost,
      token_address: instance.address,
      initial_holder: tronWeb.defaultAddress.base58,
      initial_supply: initialSupply,
    })}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
