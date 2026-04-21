from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MANAGED_NETWORK_KEYS = (
    "AIMIPAY_FULL_HOST",
    "AIMIPAY_SETTLEMENT_BACKEND",
    "AIMIPAY_CHAIN_ID",
    "AIMIPAY_CONTRACT_ADDRESS",
    "AIMIPAY_TOKEN_ADDRESS",
    "AIMIPAY_NETWORK_NAME",
    "AIMIPAY_FAUCET_URL",
    "AIMIPAY_FUNDING_GUIDE_URL",
    "AIMIPAY_MIN_TRX_BALANCE_SUN",
    "AIMIPAY_MIN_TOKEN_BALANCE_ATOMIC",
)


def resolve_full_host_for_network(
    *,
    network_name: str | None = None,
    profile_name: str | None = None,
    repository_root: str | Path | None = None,
) -> str | None:
    profiles = load_network_profiles(repository_root)
    if profile_name:
        profile = profiles.get(profile_name)
        if profile is not None:
            return _non_empty(profile.get("env", {}).get("AIMIPAY_FULL_HOST"))
    if network_name:
        normalized = network_name.strip().lower()
        for key, profile in profiles.items():
            if key.lower() == normalized:
                return _non_empty(profile.get("env", {}).get("AIMIPAY_FULL_HOST"))
            profile_network_name = str(profile.get("env", {}).get("AIMIPAY_NETWORK_NAME", "")).strip().lower()
            if profile_network_name == normalized:
                return _non_empty(profile.get("env", {}).get("AIMIPAY_FULL_HOST"))
    return None


def load_network_profiles(repository_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    config_path = root / "python" / "network_profiles.json"
    if not config_path.exists():
        config_path = Path(__file__).resolve().parents[1] / "network_profiles.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return payload["profiles"]


def get_network_profile(profile_name: str, *, repository_root: str | Path | None = None) -> dict[str, Any]:
    profiles = load_network_profiles(repository_root)
    try:
        return profiles[profile_name]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown network profile '{profile_name}'. Available: {available}.") from exc


def parse_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env_file(path: str | Path, values: dict[str, str]) -> None:
    env_path = Path(path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in values.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_network_profile_to_values(
    values: dict[str, str],
    *,
    profile_name: str,
    repository_root: str | Path | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    profile = get_network_profile(profile_name, repository_root=repository_root)
    updated = dict(values)
    updated["AIMIPAY_NETWORK_PROFILE"] = profile_name
    for key, value in profile.get("env", {}).items():
        if value != "":
            updated[key] = str(value)
    return updated, profile


def _non_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
