from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from .gateway import GatewayRuntime
from .x402_compat import build_x402_payment_response, decode_x402_payment


class FacilitatorVerifyRequest(BaseModel):
    payment: str
    resource: str | None = None
    amount_atomic: int | None = None


class FacilitatorSettleRequest(BaseModel):
    payment: str


@dataclass(slots=True)
class AimiPayFacilitator:
    gateway: GatewayRuntime

    def verify(self, payload: FacilitatorVerifyRequest) -> dict:
        decoded = decode_x402_payment(payload.payment)
        payment_id = decoded.get("payment_id") or decoded.get("paymentId")
        if not payment_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "payment_id_required"})
        record = self.gateway.get_payment(str(payment_id))
        if record is None:
            return {"schema_version": "aimipay.facilitator-verify.v1", "valid": False, "reason": "payment_not_found"}
        if payload.amount_atomic is not None and record.amount_atomic < payload.amount_atomic:
            return {"schema_version": "aimipay.facilitator-verify.v1", "valid": False, "reason": "amount_insufficient"}
        if record.status != "settled":
            return {
                "schema_version": "aimipay.facilitator-verify.v1",
                "valid": False,
                "reason": "payment_not_settled",
                "payment_status": record.status,
            }
        return {
            "schema_version": "aimipay.facilitator-verify.v1",
            "valid": True,
            "payment_id": record.payment_id,
            "payment_status": record.status,
            "amount_atomic": record.amount_atomic,
            "verified_at": int(time.time()),
        }

    def settle(self, payload: FacilitatorSettleRequest) -> dict:
        decoded = decode_x402_payment(payload.payment)
        payment_id = decoded.get("payment_id") or decoded.get("paymentId")
        if not payment_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "payment_id_required"})
        if self.gateway.settlement_service is not None:
            records = self.gateway.execute_settlements(payment_id=str(payment_id))
            record = records[0]
        else:
            record = self.gateway.get_payment(str(payment_id))
            if record is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "payment_not_found"})
        return {
            "schema_version": "aimipay.facilitator-settle.v1",
            "payment": build_x402_payment_response(
                payment_id=record.payment_id,
                success=record.status in {"submitted", "settled"},
                tx_id=record.tx_id,
                network=self.gateway.config.network,
                extra={"status": record.status},
            ),
        }


def install_facilitator(app: FastAPI, gateway: GatewayRuntime) -> AimiPayFacilitator:
    facilitator = AimiPayFacilitator(gateway=gateway)

    @app.post("/_aimipay/facilitator/verify")
    async def verify(payload: FacilitatorVerifyRequest) -> dict:
        return facilitator.verify(payload)

    @app.post("/_aimipay/facilitator/settle")
    async def settle(payload: FacilitatorSettleRequest) -> dict:
        return facilitator.settle(payload)

    app.state.aimipay_facilitator = facilitator
    return facilitator
