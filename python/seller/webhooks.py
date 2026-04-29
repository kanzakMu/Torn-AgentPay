from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .gateway import GatewayRuntime


@dataclass(slots=True)
class WebhookDeliveryWorker:
    runtime: GatewayRuntime
    http_client: httpx.Client | None = None
    timeout_s: float = 5.0

    def deliver_pending(self, *, limit: int = 100) -> dict:
        client = self.http_client or httpx.Client(timeout=self.timeout_s)
        results: list[dict] = []
        for event in self.runtime.webhook_outbox[: max(0, limit)]:
            deliveries = event.setdefault("delivery_attempts", [])
            for target in event.get("delivery", {}).get("targets", []):
                try:
                    response = client.post(target, json=event)
                    ok = 200 <= response.status_code < 300
                    deliveries.append(
                        {
                            "target": target,
                            "status_code": response.status_code,
                            "ok": ok,
                            "attempted_at": int(time.time()),
                        }
                    )
                    results.append({"event_id": event.get("event_id"), "target": target, "ok": ok})
                except Exception as exc:
                    deliveries.append(
                        {
                            "target": target,
                            "ok": False,
                            "error": exc.__class__.__name__,
                            "attempted_at": int(time.time()),
                        }
                    )
                    results.append({"event_id": event.get("event_id"), "target": target, "ok": False})
        return {
            "schema_version": "aimipay.webhook-delivery-report.v1",
            "delivered_at": int(time.time()),
            "attempt_count": len(results),
            "results": results,
        }
