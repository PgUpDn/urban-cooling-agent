from __future__ import annotations

from pathlib import Path
from typing import Dict, List


_SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg"}
_DATA_SUFFIXES = {".csv", ".json", ".npz"}
_LOG_SUFFIXES = {".txt", ".md", ".log"}


def collect_coupled_outputs(output_dir: Path | str) -> Dict[str, List[str]]:
    """
    Crawl the coupled solver output directory and bucket every generated file.

    Returns a manifest that groups screenshots, VTK files, tabular data, logs,
    and exposes the flattened list via the ``all_files`` key so downstream
    agents can reference every artifact produced by coupled_UrGen_v1.
    """
    manifest: Dict[str, List[str]] = {
        "screenshots": [],
        "vtk_files": [],
        "data_files": [],
        "log_files": [],
        "other_files": [],
        "all_files": [],
    }

    base_path = Path(output_dir).expanduser().resolve()
    if not base_path.exists():
        return manifest

    for path in sorted(base_path.rglob("*")):
        if not path.is_file():
            continue

        file_str = str(path)
        manifest["all_files"].append(file_str)

        suffix = path.suffix.lower()
        if suffix in _SCREENSHOT_SUFFIXES:
            manifest["screenshots"].append(file_str)
        elif suffix == ".vtk":
            manifest["vtk_files"].append(file_str)
        elif suffix in _DATA_SUFFIXES:
            manifest["data_files"].append(file_str)
        elif suffix in _LOG_SUFFIXES:
            manifest["log_files"].append(file_str)
        else:
            manifest["other_files"].append(file_str)

    return manifest


__all__ = ["collect_coupled_outputs"]

