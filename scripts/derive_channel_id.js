const { loadPlan } = require("./io");
const { channelIdOf } = require("./protocol");

function main(plan = loadPlan()) {
  return {
    channel_id: channelIdOf({
      buyer: plan.buyer_address,
      seller: plan.seller_address,
      token: plan.token_address,
      fullHost: plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io",
    }),
  };
}

if (require.main === module) {
  try {
    process.stdout.write(`${JSON.stringify(main())}\n`);
  } catch (error) {
    process.stderr.write(`${error.stack || error}\n`);
    process.exit(1);
  }
}

module.exports = {
  main,
};
