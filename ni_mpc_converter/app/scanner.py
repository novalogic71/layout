from __future__ import annotations

from pathlib import Path


def find_maschine_kits(ni_root: Path) -> list[Path]:
    kit_paths: list[Path] = []
    groups_dir = ni_root / "Groups"
    kits_dir = groups_dir / "Kits"
    if kits_dir.exists():
        kit_paths.extend(kits_dir.glob("*.mxgrp"))
    if groups_dir.exists():
        kit_paths.extend(groups_dir.glob("*.mxgrp"))

    deduped = {str(path.resolve()): path for path in kit_paths}
    return sorted(deduped.values(), key=lambda item: str(item).lower())


def find_template_xtd(reference_root: Path) -> Path | None:
    xtds = sorted(reference_root.rglob("*.xtd"))
    return xtds[0] if xtds else None


def slugify_kit_name(name: str) -> str:
    allowed = []
    for char in name.strip():
        if char.isalnum() or char in (" ", "-", "_"):
            allowed.append(char)
        else:
            allowed.append("_")
    slug = "".join(allowed).strip()
    return slug or "ConvertedKit"
