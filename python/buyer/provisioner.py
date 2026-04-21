from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class OpenChannelProvisionPlan:
    full_host: str
    buyer_private_key: str
    contract_address: str
    seller_address: str
    token_address: str
    deposit_atomic: int
    expires_at: int

    def to_dict(self) -> dict:
        return {
            "full_host": self.full_host,
            "buyer_private_key": self.buyer_private_key,
            "contract_address": self.contract_address,
            "seller_address": self.seller_address,
            "token_address": self.token_address,
            "deposit_atomic": self.deposit_atomic,
            "expires_at": self.expires_at,
        }


@dataclass(slots=True)
class OpenChannelExecution:
    approve_tx_id: str
    open_tx_id: str
    buyer_address: str
    seller_address: str
    token_address: str
    channel_id: str
    contract_address: str
    deposit_atomic: int
    expires_at: int


@dataclass(slots=True)
class TronProvisioner:
    command: tuple[str, ...]
    cwd: str
    extra_env: dict[str, str] | None = None

    def provision(self, plan: OpenChannelProvisionPlan) -> OpenChannelExecution:
        with tempfile.TemporaryDirectory(prefix="aimipay-tron-plan-") as temp_dir:
            plan_file = Path(temp_dir) / "open_channel_plan.json"
            plan_file.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            env = os.environ.copy()
            if self.extra_env:
                env.update(self.extra_env)
            completed = subprocess.run(
                [*self.command, str(plan_file)],
                cwd=self.cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = _parse_json_output(completed.stdout)
        return OpenChannelExecution(
            approve_tx_id=str(payload["approve_tx_id"]),
            open_tx_id=str(payload["open_tx_id"]),
            buyer_address=str(payload["buyer_address"]),
            seller_address=str(payload["seller_address"]),
            token_address=str(payload["token_address"]),
            channel_id=str(payload["channel_id"]),
            contract_address=str(payload["contract_address"]),
            deposit_atomic=int(payload["deposit_atomic"]),
            expires_at=int(payload["expires_at"]),
        )


def build_default_tron_provisioner(*, repository_root: str | os.PathLike[str]) -> TronProvisioner:
    repo = Path(repository_root)
    return TronProvisioner(
        command=("node", "scripts/open_channel_exec.js"),
        cwd=str(repo),
    )


def _parse_json_output(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("provisioner returned no output")
    return json.loads(lines[-1])
