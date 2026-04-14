from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_config_file(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    raw_text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        data = json.loads(raw_text)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(raw_text)
    else:
        raise ValueError("Config file must use .json, .yaml, or .yml extension.")

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a top-level object.")
    return data