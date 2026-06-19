from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .convert import convert_custom_library, convert_library, write_report
from .mapper import PAD_PROFILE_CUSTOM, PAD_PROFILE_DARKCHILD, PAD_PROFILE_DEFAULT
from .scanner import find_template_xtd

SOURCE_TYPE_NI = "ni"
SOURCE_TYPE_CUSTOM = "custom"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert NI kits and custom WAV folders to MPC-style .xtd kits."
    )
    parser.add_argument(
        "--ni-root",
        action="append",
        default=[],
        type=Path,
        help=(
            "Path to a Native Instruments expansion root "
            "(contains Groups/Kits or Groups with .mxgrp files, Samples, etc.). Can be repeated."
        ),
    )
    parser.add_argument(
        "--ni-parent",
        action="append",
        default=[],
        type=Path,
        help=(
            "Parent directory containing multiple NI expansion roots. "
            "Each direct child with Groups/Kits or Groups/*.mxgrp is included."
        ),
    )
    parser.add_argument(
        "--samples-root",
        action="append",
        default=[],
        type=Path,
        help=(
            "Path to a custom sample pack root. "
            "Valid when at least one WAV file exists in root or descendants. Can be repeated."
        ),
    )
    parser.add_argument(
        "--samples-parent",
        action="append",
        default=[],
        type=Path,
        help=(
            "Parent directory containing multiple custom sample pack roots. "
            "Each direct child with WAV content is included."
        ),
    )
    parser.add_argument(
        "--samples-grouping",
        choices=("per-folder", "single-kit"),
        default="per-folder",
        help=(
            "Custom sample grouping mode: "
            "'per-folder' creates one kit per immediate folder, "
            "'single-kit' merges the entire samples root into one kit."
        ),
    )
    parser.add_argument(
        "--pad-profile",
        choices=(PAD_PROFILE_DEFAULT, PAD_PROFILE_DARKCHILD, PAD_PROFILE_CUSTOM),
        default=PAD_PROFILE_DEFAULT,
        help=(
            "Pad assignment profile for custom sample conversion. "
            "'default' keeps existing mapping behavior; "
            "'darkchild' applies fixed kick/snare/perc anchor pads; "
            "'custom' applies editable-style anchors with deterministic random fill."
        ),
    )
    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help="Output folder for converted .xtd kits and _[TrackData] folders.",
    )
    parser.add_argument(
        "--template-xtd",
        type=Path,
        default=None,
        help="Reference .xtd file used as schema template.",
    )
    parser.add_argument(
        "--mpc-root",
        type=Path,
        default=None,
        help="If --template-xtd is omitted, find first .xtd under this folder.",
    )
    parser.add_argument(
        "--kit",
        action="append",
        default=None,
        help="Filter kit names (substring match). Can be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of kits to convert after filtering.",
    )
    parser.add_argument(
        "--no-normalize-audio",
        action="store_true",
        help="Skip sample-rate normalization and copy source WAVs as-is.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and map kits but do not write output files.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help=(
            "Optional report file path. For single-source runs this is the source report path; "
            "for multi-source runs this is the aggregate report path."
        ),
    )
    parser.add_argument(
        "--flat-output",
        action="store_true",
        help="For multiple sources, write all output into --output-root without source subfolders.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    sources = _resolve_sources(
        ni_roots=args.ni_root,
        ni_parents=args.ni_parent,
        sample_roots=args.samples_root,
        sample_parents=args.samples_parent,
    )
    if not sources:
        print(
            "ERROR: No valid sources found. "
            "Provide --ni-root/--ni-parent and/or --samples-root/--samples-parent.",
            file=sys.stderr,
        )
        return 2

    template_xtd = _resolve_template_xtd(args.template_xtd, args.mpc_root)
    if template_xtd is None:
        print(
            "ERROR: Could not resolve template .xtd. "
            "Provide --template-xtd or --mpc-root with at least one .xtd file.",
            file=sys.stderr,
        )
        return 2

    if len(sources) == 1:
        source_type, source_root = sources[0]
        return _run_single_source(args, template_xtd, source_type, source_root)
    return _run_multi_sources(args, template_xtd, sources)


def _run_single_source(
    args: argparse.Namespace,
    template_xtd: Path,
    source_type: str,
    source_root: Path,
) -> int:
    report_path = args.report or (args.output_root / "conversion-report.json")
    report = _convert_for_source(
        source_type=source_type,
        source_root=source_root,
        output_root=args.output_root,
        template_xtd=template_xtd,
        samples_grouping=args.samples_grouping,
        pad_profile=args.pad_profile,
        kit_filters=args.kit,
        limit=args.limit,
        normalize_audio=not args.no_normalize_audio,
        dry_run=args.dry_run,
    )
    write_report(report, report_path)

    print(f"Source Type: {source_type}")
    print(f"Source Root: {source_root}")
    print(f"Pad profile: {report.pad_profile}")
    print(f"Template XTD: {template_xtd}")
    print(f"Scanned kits: {report.scanned_kits}")
    print(f"Converted kits: {report.converted_kits}")
    print(f"Skipped kits: {report.skipped_kits}")
    print(f"Report: {report_path}")
    if report.warnings:
        print(f"Warnings: {len(report.warnings)}")
        for warning in report.warnings[:20]:
            print(f"- {warning}")
        if len(report.warnings) > 20:
            print(f"... {len(report.warnings) - 20} more warnings in report")
    return 0


def _run_multi_sources(
    args: argparse.Namespace,
    template_xtd: Path,
    sources: list[tuple[str, Path]],
) -> int:
    created_subdirs: set[str] = set()
    per_source: list[dict] = []
    total_scanned = 0
    total_converted = 0
    total_skipped = 0
    total_warnings = 0

    for source_type, source_root in sources:
        if args.flat_output:
            output_dir = args.output_root
        else:
            base_subdir = _safe_subdir_name(f"{source_type}_{source_root.name}")
            subdir = _unique_subdir_name(base_subdir, created_subdirs)
            created_subdirs.add(subdir)
            output_dir = args.output_root / subdir

        report = _convert_for_source(
            source_type=source_type,
            source_root=source_root,
            output_root=output_dir,
            template_xtd=template_xtd,
            samples_grouping=args.samples_grouping,
            pad_profile=args.pad_profile,
            kit_filters=args.kit,
            limit=args.limit,
            normalize_audio=not args.no_normalize_audio,
            dry_run=args.dry_run,
        )
        report_path = output_dir / "conversion-report.json"
        write_report(report, report_path)

        total_scanned += report.scanned_kits
        total_converted += report.converted_kits
        total_skipped += report.skipped_kits
        total_warnings += len(report.warnings)

        per_source.append(
            {
                "source_type": source_type,
                "source_root": str(source_root),
                "pad_profile": report.pad_profile,
                "output_root": str(output_dir),
                "report": str(report_path),
                "scanned_kits": report.scanned_kits,
                "converted_kits": report.converted_kits,
                "skipped_kits": report.skipped_kits,
                "warning_count": len(report.warnings),
            }
        )

        print(
            f"[{source_type}:{source_root.name}] scanned={report.scanned_kits} "
            f"converted={report.converted_kits} skipped={report.skipped_kits} "
            f"warnings={len(report.warnings)} output={output_dir}"
        )

    aggregate_report = {
        "template_xtd": str(template_xtd),
        "pack_count": len(sources),
        "source_count": len(sources),
        "total_scanned_kits": total_scanned,
        "total_converted_kits": total_converted,
        "total_skipped_kits": total_skipped,
        "total_warnings": total_warnings,
        "packs": per_source,
        "sources": per_source,
    }
    aggregate_path = args.report or (args.output_root / "multi-pack-report.json")
    aggregate_path.parent.mkdir(parents=True, exist_ok=True)
    aggregate_path.write_text(json.dumps(aggregate_report, indent=2), encoding="utf-8")

    print(f"Template XTD: {template_xtd}")
    print(f"Pad profile: {args.pad_profile}")
    print(f"Sources processed: {len(sources)}")
    print(f"Total scanned kits: {total_scanned}")
    print(f"Total converted kits: {total_converted}")
    print(f"Total skipped kits: {total_skipped}")
    print(f"Aggregate report: {aggregate_path}")
    return 0


def _convert_for_source(
    source_type: str,
    source_root: Path,
    output_root: Path,
    template_xtd: Path,
    samples_grouping: str,
    pad_profile: str,
    kit_filters: list[str] | None,
    limit: int | None,
    normalize_audio: bool,
    dry_run: bool,
    custom_pad_map: dict[str, list[int]] | None = None,
):
    if source_type == SOURCE_TYPE_NI:
        return convert_library(
            ni_root=source_root,
            output_root=output_root,
            template_xtd=template_xtd,
            pad_profile=PAD_PROFILE_DEFAULT,
            kit_filters=kit_filters,
            limit=limit,
            normalize_audio=normalize_audio,
            dry_run=dry_run,
        )
    return convert_custom_library(
        samples_root=source_root,
        output_root=output_root,
        template_xtd=template_xtd,
        grouping=samples_grouping,
        pad_profile=pad_profile,
        custom_pad_map=custom_pad_map,
        kit_filters=kit_filters,
        limit=limit,
        normalize_audio=normalize_audio,
        dry_run=dry_run,
    )


def _resolve_sources(
    ni_roots: list[Path],
    ni_parents: list[Path],
    sample_roots: list[Path],
    sample_parents: list[Path],
) -> list[tuple[str, Path]]:
    resolved: list[tuple[str, Path]] = []
    seen: set[str] = set()

    for root in _resolve_ni_roots(ni_roots, ni_parents):
        key = f"{SOURCE_TYPE_NI}:{root.resolve()}"
        if key in seen:
            continue
        seen.add(key)
        resolved.append((SOURCE_TYPE_NI, root))

    for root in _resolve_sample_roots(sample_roots, sample_parents):
        key = f"{SOURCE_TYPE_CUSTOM}:{root.resolve()}"
        if key in seen:
            continue
        seen.add(key)
        resolved.append((SOURCE_TYPE_CUSTOM, root))

    return resolved


def _resolve_ni_roots(explicit_roots: list[Path], parent_roots: list[Path]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()

    for root in explicit_roots:
        if not _is_expansion_root(root):
            continue
        key = str(root.resolve())
        if key in seen:
            continue
        seen.add(key)
        resolved.append(root)

    for parent in parent_roots:
        if not parent.exists() or not parent.is_dir():
            continue
        if _is_expansion_root(parent):
            key = str(parent.resolve())
            if key not in seen:
                seen.add(key)
                resolved.append(parent)
        for child in sorted(parent.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir():
                continue
            if not _is_expansion_root(child):
                continue
            key = str(child.resolve())
            if key in seen:
                continue
            seen.add(key)
            resolved.append(child)

    return resolved


def _resolve_sample_roots(explicit_roots: list[Path], parent_roots: list[Path]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()

    for root in explicit_roots:
        if not _is_custom_samples_root(root):
            continue
        key = str(root.resolve())
        if key in seen:
            continue
        seen.add(key)
        resolved.append(root)

    for parent in parent_roots:
        if not parent.exists() or not parent.is_dir():
            continue
        for child in sorted(parent.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir():
                continue
            if not _is_custom_samples_root(child):
                continue
            key = str(child.resolve())
            if key in seen:
                continue
            seen.add(key)
            resolved.append(child)

    return resolved


def _is_expansion_root(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    groups_dir = path / "Groups"
    if not groups_dir.exists() or not groups_dir.is_dir():
        return False
    if (groups_dir / "Kits").exists():
        return True
    return any(item.is_file() and item.suffix.lower() == ".mxgrp" for item in groups_dir.iterdir())


def _is_custom_samples_root(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    for entry in path.rglob("*"):
        if entry.is_file() and entry.suffix.lower() == ".wav":
            return True
    return False


def _safe_subdir_name(name: str) -> str:
    cleaned = "".join(char if (char.isalnum() or char in ("-", "_")) else "_" for char in name)
    cleaned = cleaned.strip("_")
    return cleaned or "Pack"


def _unique_subdir_name(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    index = 2
    while True:
        candidate = f"{base}_{index}"
        if candidate not in used:
            return candidate
        index += 1


def _resolve_template_xtd(template_xtd: Path | None, mpc_root: Path | None) -> Path | None:
    if template_xtd is not None:
        return template_xtd if template_xtd.exists() else None
    if mpc_root is None or not mpc_root.exists():
        return None
    return find_template_xtd(mpc_root)


if __name__ == "__main__":
    raise SystemExit(main())
