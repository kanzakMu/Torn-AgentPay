const { loadPlan, createTronWeb } = require("./io");

function normalizeFailureMessage(payload) {
  if (!payload) {
    return null;
  }
  return payload.resMessage || payload.result || payload.contractResult || null;
}

async function main(plan = loadPlan()) {
  const fullHost = plan.full_host || process.env.FULL_HOST || "https://nile.trongrid.io";
  const txId = plan.tx_id;
  if (!txId) {
    throw new Error("missing tx_id");
  }

  const tronWeb = createTronWeb({ fullHost });
  const txInfo = await tronWeb.trx.getTransactionInfo(txId);
  if (txInfo && Object.keys(txInfo).length > 0) {
    const receipt = txInfo.receipt || {};
    const receiptResult = receipt.result || txInfo.result || "SUCCESS";
    if (receiptResult !== "SUCCESS") {
      return {
        tx_id: txId,
        status: "failed",
        confirmed: false,
        block_number: txInfo.blockNumber || null,
        block_timestamp: txInfo.blockTimeStamp || null,
        error_message: normalizeFailureMessage(txInfo) || `transaction failed with result ${receiptResult}`,
      };
    }
    return {
      tx_id: txId,
      status: "confirmed",
      confirmed: true,
      block_number: txInfo.blockNumber || null,
      block_timestamp: txInfo.blockTimeStamp || null,
      error_message: null,
    };
  }

  const tx = await tronWeb.trx.getTransaction(txId);
  if (tx && Object.keys(tx).length > 0) {
    const ret = Array.isArray(tx.ret) ? tx.ret[0] : null;
    const contractRet = ret ? ret.contractRet : null;
    if (contractRet && contractRet !== "SUCCESS") {
      return {
        tx_id: txId,
        status: "failed",
        confirmed: false,
        block_number: tx.blockNumber || null,
        block_timestamp: tx.raw_data ? tx.raw_data.timestamp || null : null,
        error_message: `transaction failed with contract result ${contractRet}`,
      };
    }
    return {
      tx_id: txId,
      status: "pending",
      confirmed: false,
      block_number: tx.blockNumber || null,
      block_timestamp: tx.raw_data ? tx.raw_data.timestamp || null : null,
      error_message: null,
    };
  }

  return {
    tx_id: txId,
    status: "pending",
    confirmed: false,
    block_number: null,
    block_timestamp: null,
    error_message: null,
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
