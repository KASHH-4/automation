"""Minimal adapter for loading company data from clean_data.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _candidate_paths() -> list[Path]:
    root = Path(__file__).resolve().parent
    return [
        root / "clean_data.json",
        root / "RAG_Module" / "RAG" / "rag_module" / "data" / "clean_data.json",
    ]


def _resolve_clean_data_path() -> Path:
    for path in _candidate_paths():
        if path.exists() and path.is_file():
            return path

    checked = "\n".join(str(path) for path in _candidate_paths())
    raise FileNotFoundError(
        "Company data file 'clean_data.json' was not found. "
        "Run your ingestion notebook exports first, then ensure the file exists at one of:\n"
        f"{checked}"
    )


def load_company_data() -> Dict[str, Any]:
    """Load and return structured company data from clean_data.json."""

    clean_data_path = _resolve_clean_data_path()

    try:
        with clean_data_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Company data file is not valid JSON: {clean_data_path} ({exc})"
        ) from exc

    if isinstance(data, dict):
        return data

    return {
        "records": data,
        "source_file": str(clean_data_path),
    }
