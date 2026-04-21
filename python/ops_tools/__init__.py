from __future__ import annotations

__all__ = [
    "backup_sqlite_database",
    "build_gateway_config_from_env",
    "build_merchant_install_report",
    "build_preflight_report",
    "ensure_merchant_install",
    "export_payment_snapshot",
    "import_payment_snapshot",
    "load_payment_snapshot",
]


def __getattr__(name: str):
    if name in {
        "backup_sqlite_database",
        "export_payment_snapshot",
        "import_payment_snapshot",
        "load_payment_snapshot",
    }:
        from .payment_store_tools import (
            backup_sqlite_database,
            export_payment_snapshot,
            import_payment_snapshot,
            load_payment_snapshot,
        )

        return {
            "backup_sqlite_database": backup_sqlite_database,
            "export_payment_snapshot": export_payment_snapshot,
            "import_payment_snapshot": import_payment_snapshot,
            "load_payment_snapshot": load_payment_snapshot,
        }[name]
    if name in {"build_gateway_config_from_env", "build_preflight_report"}:
        from .preflight import build_gateway_config_from_env, build_preflight_report

        return {
            "build_gateway_config_from_env": build_gateway_config_from_env,
            "build_preflight_report": build_preflight_report,
        }[name]
    if name == "build_merchant_install_report":
        from .merchant_doctor import build_merchant_install_report

        return build_merchant_install_report
    if name == "ensure_merchant_install":
        from .merchant_setup import ensure_merchant_install

        return ensure_merchant_install
    raise AttributeError(name)
