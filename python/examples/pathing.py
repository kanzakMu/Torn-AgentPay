from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_python_paths(*, current_file: str | Path) -> tuple[Path, Path]:
    current_path = Path(current_file).resolve()
    python_dir = current_path.parents[1]
    repository_root = python_dir.parent

    for candidate in (str(repository_root), str(python_dir)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    return repository_root, python_dir
