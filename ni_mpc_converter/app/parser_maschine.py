from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from urllib.parse import unquote

SAMPLE_PATH_RE = re.compile(r"Samples/[^\x00\r\n]+?\.(?:wav|WAV)")


def extract_sample_paths(mxgrp_path: Path) -> list[str]:
    raw = mxgrp_path.read_bytes()
    decoded = raw.decode("latin1", errors="ignore")
    matches = SAMPLE_PATH_RE.findall(decoded)
    deduped = OrderedDict()
    for match in matches:
        normalized = match.replace("\\", "/")
        deduped[normalized] = None
    return list(deduped.keys())


def _resolve_case_insensitive(parent: Path, child_name: str) -> Path | None:
    if not parent.exists():
        return None
    target = child_name.lower()
    for item in parent.iterdir():
        if item.name.lower() == target:
            return item
    return None


def resolve_sample_path(ni_root: Path, relative_path: str) -> Path | None:
    normalized = unquote(relative_path)
    candidate = ni_root / normalized
    if candidate.exists():
        return candidate

    current = ni_root
    for part in normalized.split("/"):
        resolved = _resolve_case_insensitive(current, part)
        if resolved is None:
            return None
        current = resolved
    return current if current.exists() else None
