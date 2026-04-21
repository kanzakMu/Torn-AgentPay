from __future__ import annotations

from pathlib import Path


def load_env_file(env_file: str | Path, *, override: bool = False) -> None:
    path = Path(env_file)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in __import__("os").environ):
            __import__("os").environ[key] = value


def load_default_example_env(*, start_dir: str | Path | None = None) -> None:
    if start_dir is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_dir)
    candidates = [
        start_path / ".env.merchant.local",
        start_path / ".env.local",
        Path(__file__).resolve().parent / ".env.merchant.local",
        Path(__file__).resolve().parent / ".env.local",
        Path(__file__).resolve().parent / ".env.example",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_env_file(candidate)
