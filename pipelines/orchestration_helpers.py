"""Shared helpers for pipeline orchestration entrypoints."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Iterable, Optional

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def parse_pipeline_args(args: list[str], usage: str) -> Optional[tuple[str, bool]]:
    """Parse common pipeline arguments and return input folder + browser flag."""
    if not args or args[0].startswith("--"):
        print(usage)
        return None

    screenshots_dir = args[0]
    open_browser = "--no-browser" not in args
    return screenshots_dir, open_browser


def list_image_files(screenshots_dir: str | Path) -> list[Path]:
    """Return supported screenshot files in deterministic order."""
    screenshots_path = Path(screenshots_dir)
    return sorted(p for p in screenshots_path.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


def reset_directory(path: Path) -> None:
    """Delete and recreate one directory."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def reset_directories(paths: Iterable[Path]) -> None:
    """Delete and recreate all provided directories."""
    for path in paths:
        reset_directory(path)


def to_artifact_token(value: str) -> str:
    """Convert a logical name into a stable, user-friendly snake_case token."""
    token = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return token or "screen"


def write_json_timestamped(output_dir: Path, prefix: str, logical_name: str, payload_json: str) -> Path:
    """Write a JSON artifact using a timestamped file name."""
    timestamp = int(time.time())
    out_path = output_dir / f"{prefix}_{to_artifact_token(logical_name)}_{timestamp}.json"
    out_path.write_text(payload_json, encoding="utf-8")
    return out_path


def write_text_timestamped(output_dir: Path, prefix: str, logical_name: str, content: str) -> Path:
    """Write a text artifact using a timestamped file name."""
    timestamp = int(time.time())
    out_path = output_dir / f"{prefix}_{to_artifact_token(logical_name)}_{timestamp}.txt"
    out_path.write_text(content, encoding="utf-8")
    return out_path
