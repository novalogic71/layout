from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from .audio import copy_or_normalize_wav, wav_frame_count
from .classifier import classify_sample
from .mapper import PAD_PROFILE_DEFAULT, assign_pads
from .models import (
    ConversionReport,
    KitConversionResult,
    RenderedSample,
    SampleCandidate,
)
from .parser_maschine import extract_sample_paths, resolve_sample_path
from .scanner import find_maschine_kits, slugify_kit_name
from .writer_xtd import load_xtd_template, write_xtd_from_template

SOURCE_TYPE_NI = "ni"
SOURCE_TYPE_CUSTOM = "custom"
NI_PAD_LIMIT = 32
CUSTOM_PAD_LIMIT = 32


def convert_library(
    ni_root: Path,
    output_root: Path,
    template_xtd: Path,
    pad_profile: str = PAD_PROFILE_DEFAULT,
    custom_pad_map: dict[str, list[int]] | None = None,
    kit_filters: list[str] | None = None,
    limit: int | None = None,
    normalize_audio: bool = True,
    dry_run: bool = False,
) -> ConversionReport:
    kits = find_maschine_kits(ni_root)
    filtered = _filter_kits(kits, kit_filters)
    if limit is not None:
        filtered = filtered[:limit]

    header_lines, template_payload = load_xtd_template(template_xtd)
    report = _new_report(
        source_type=SOURCE_TYPE_NI,
        source_root=ni_root,
        pad_profile=pad_profile,
        output_root=output_root,
        template_xtd=template_xtd,
        scanned_kits=len(filtered),
    )

    for mxgrp_path in filtered:
        results = _convert_single_ni_kit(
            ni_root=ni_root,
            output_root=output_root,
            mxgrp_path=mxgrp_path,
            header_lines=header_lines,
            template_payload=template_payload,
            normalize_audio=normalize_audio,
            dry_run=dry_run,
        )
        _append_results(report, results)

    return report


def convert_custom_library(
    samples_root: Path,
    output_root: Path,
    template_xtd: Path,
    grouping: str = "per-folder",
    pad_profile: str = PAD_PROFILE_DEFAULT,
    custom_pad_map: dict[str, list[int]] | None = None,
    kit_filters: list[str] | None = None,
    limit: int | None = None,
    normalize_audio: bool = True,
    dry_run: bool = False,
) -> ConversionReport:
    discovered = _discover_custom_kits(samples_root, grouping=grouping)
    filtered = _filter_named_entries(discovered, kit_filters)
    if limit is not None:
        filtered = filtered[:limit]

    header_lines, template_payload = load_xtd_template(template_xtd)
    report = _new_report(
        source_type=SOURCE_TYPE_CUSTOM,
        source_root=samples_root,
        pad_profile=pad_profile,
        output_root=output_root,
        template_xtd=template_xtd,
        scanned_kits=len(filtered),
    )

    for kit_name, source_path, wav_files in filtered:
        results = _convert_samples_kit(
            output_root=output_root,
            kit_name=kit_name,
            source_path=source_path,
            wav_files=wav_files,
            header_lines=header_lines,
            template_payload=template_payload,
            normalize_audio=normalize_audio,
            dry_run=dry_run,
            source_type=SOURCE_TYPE_CUSTOM,
            pad_limit=CUSTOM_PAD_LIMIT,
            pad_profile=pad_profile,
            custom_pad_map=custom_pad_map,
        )
        _append_results(report, results)

    return report


def write_report(report: ConversionReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_type": report.source_type,
        "source_root": report.source_root,
        "ni_root": report.ni_root,
        "pad_profile": report.pad_profile,
        "output_root": report.output_root,
        "template_xtd": report.template_xtd,
        "scanned_kits": report.scanned_kits,
        "converted_kits": report.converted_kits,
        "skipped_kits": report.skipped_kits,
        "warnings": report.warnings,
        "kit_results": [
            {
                "kit_name": result.kit_name,
                "source_file": result.source_file,
                "source_type": result.source_type,
                "source_path": result.source_path,
                "pad_profile": result.pad_profile,
                "pad_limit": result.pad_limit,
                "output_xtd": result.output_xtd,
                "assigned_pad_count": result.assigned_pad_count,
                "copied_sample_count": result.copied_sample_count,
                "warnings": result.warnings,
            }
            for result in report.kit_results
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _new_report(
    source_type: str,
    source_root: Path,
    pad_profile: str,
    output_root: Path,
    template_xtd: Path,
    scanned_kits: int,
) -> ConversionReport:
    return ConversionReport(
        source_type=source_type,
        source_root=str(source_root),
        ni_root=str(source_root),
        pad_profile=pad_profile,
        output_root=str(output_root),
        template_xtd=str(template_xtd),
        scanned_kits=scanned_kits,
        converted_kits=0,
        skipped_kits=0,
    )


def _append_results(report: ConversionReport, results: list[KitConversionResult]) -> None:
    if not results:
        report.skipped_kits += 1
        return
    report.converted_kits += len(results)
    report.kit_results.extend(results)
    for result in results:
        report.warnings.extend(result.warnings)


def _filter_kits(kits: list[Path], kit_filters: list[str] | None) -> list[Path]:
    if not kit_filters:
        return kits
    lowered = [item.lower() for item in kit_filters]
    selected = []
    for kit in kits:
        name = kit.stem.lower()
        if any(token in name for token in lowered):
            selected.append(kit)
    return selected


def _filter_named_entries(
    entries: list[tuple[str, Path, list[Path]]],
    kit_filters: list[str] | None,
) -> list[tuple[str, Path, list[Path]]]:
    if not kit_filters:
        return entries
    lowered = [item.lower() for item in kit_filters]
    selected = []
    for kit_name, source_path, wav_files in entries:
        name = kit_name.lower()
        if any(token in name for token in lowered):
            selected.append((kit_name, source_path, wav_files))
    return selected


def _convert_single_ni_kit(
    ni_root: Path,
    output_root: Path,
    mxgrp_path: Path,
    header_lines: list[str],
    template_payload: dict,
    normalize_audio: bool,
    dry_run: bool,
) -> list[KitConversionResult]:
    kit_name = slugify_kit_name(mxgrp_path.stem)
    warnings: list[str] = []

    extracted = extract_sample_paths(mxgrp_path)
    if not extracted:
        return []

    candidates = _build_candidates_from_relative_paths(ni_root, extracted, warnings)
    if not candidates:
        warnings.append(f"No resolved WAV files for kit: {kit_name}")
        return []

    return _render_kit_series(
        output_root=output_root,
        base_kit_name=kit_name,
        source_path=mxgrp_path,
        source_type=SOURCE_TYPE_NI,
        pad_limit=NI_PAD_LIMIT,
        pad_profile=PAD_PROFILE_DEFAULT,
        custom_pad_map=None,
        remaining_mode="priority",
        random_seed_base=None,
        candidates=candidates,
        header_lines=header_lines,
        template_payload=template_payload,
        normalize_audio=normalize_audio,
        dry_run=dry_run,
        warnings=warnings,
    )


def _convert_samples_kit(
    output_root: Path,
    kit_name: str,
    source_path: Path,
    wav_files: list[Path],
    header_lines: list[str],
    template_payload: dict,
    normalize_audio: bool,
    dry_run: bool,
    source_type: str,
    pad_limit: int,
    pad_profile: str = PAD_PROFILE_DEFAULT,
    custom_pad_map: dict[str, list[int]] | None = None,
    remaining_mode: str = "balanced",
) -> list[KitConversionResult]:
    if not wav_files:
        return []

    warnings: list[str] = []
    candidates = _build_candidates_from_files(source_path, wav_files)
    if not candidates:
        warnings.append(f"No valid WAV files for kit: {kit_name}")
        return []

    return _render_kit_series(
        output_root=output_root,
        base_kit_name=kit_name,
        source_path=source_path,
        source_type=source_type,
        pad_limit=pad_limit,
        pad_profile=pad_profile,
        custom_pad_map=custom_pad_map,
        remaining_mode=remaining_mode,
        random_seed_base=f"{source_path.resolve()}::{kit_name}",
        candidates=candidates,
        header_lines=header_lines,
        template_payload=template_payload,
        normalize_audio=normalize_audio,
        dry_run=dry_run,
        warnings=warnings,
    )


def _render_kit_series(
    output_root: Path,
    base_kit_name: str,
    source_path: Path,
    source_type: str,
    pad_limit: int,
    pad_profile: str,
    custom_pad_map: dict[str, list[int]] | None,
    remaining_mode: str,
    random_seed_base: str | None,
    candidates: list[SampleCandidate],
    header_lines: list[str],
    template_payload: dict,
    normalize_audio: bool,
    dry_run: bool,
    warnings: list[str],
) -> list[KitConversionResult]:
    remaining = list(candidates)
    results: list[KitConversionResult] = []
    part_number = 1

    while remaining:
        assignments = assign_pads(
            remaining,
            pad_count=pad_limit,
            remaining_mode=remaining_mode,
            profile=pad_profile,
            random_seed=_build_part_seed(random_seed_base, part_number),
            custom_role_slots=custom_pad_map,
        )
        if not assignments:
            break

        kit_name = base_kit_name if part_number == 1 else f"{base_kit_name}__{part_number}"
        part_warnings: list[str] = warnings[:] if part_number == 1 else []

        result = _render_single_kit_from_assignments(
            output_root=output_root,
            kit_name=kit_name,
            source_path=source_path,
            source_type=source_type,
            pad_profile=pad_profile,
            pad_limit=pad_limit,
            assignments=assignments,
            header_lines=header_lines,
            template_payload=template_payload,
            normalize_audio=normalize_audio,
            dry_run=dry_run,
            warnings=part_warnings,
        )
        if result is not None:
            results.append(result)

        selected_samples = {item.sample for item in assignments}
        next_remaining = [sample for sample in remaining if sample not in selected_samples]
        if len(next_remaining) == len(remaining):
            break
        remaining = next_remaining
        part_number += 1

    if len(results) > 1:
        results[0].warnings.append(
            f"Kit '{base_kit_name}' required {len(results)} kit files because pad limit is {pad_limit}."
        )

    return results


def _render_single_kit_from_assignments(
    output_root: Path,
    kit_name: str,
    source_path: Path,
    source_type: str,
    pad_profile: str,
    pad_limit: int,
    assignments,
    header_lines: list[str],
    template_payload: dict,
    normalize_audio: bool,
    dry_run: bool,
    warnings: list[str],
) -> KitConversionResult | None:
    if not assignments:
        return None

    output_xtd_path = output_root / f"{kit_name}.xtd"
    track_data_dir = output_root / f"{kit_name}_[TrackData]"
    if not dry_run and (output_xtd_path.exists() or track_data_dir.exists()):
        warnings.append(
            f"Skipped '{kit_name}' because output already exists: {output_xtd_path} or {track_data_dir}"
        )
        return None

    rendered_samples: list[RenderedSample] = []
    used_output_names: set[str] = set()
    for assignment in assignments:
        source = assignment.sample.source_abs
        unique_name = _make_unique_filename(source.name, used_output_names)
        used_output_names.add(unique_name)
        out_path = track_data_dir / unique_name

        if not dry_run:
            ok, warning = copy_or_normalize_wav(
                source_path=source,
                output_path=out_path,
                normalize_audio=normalize_audio,
            )
            if warning:
                warnings.append(warning)
            if not ok:
                warnings.append(f"Audio normalization fallback used for: {source.name}")

        frame_count = wav_frame_count(source)
        rendered_samples.append(
            RenderedSample(
                display_name=source.stem,
                output_filename=unique_name,
                output_path=out_path,
                role=assignment.sample.role,
                frame_count=frame_count,
            )
        )

    if not dry_run:
        write_xtd_from_template(
            header_lines=header_lines,
            template_payload=template_payload,
            output_xtd_path=output_xtd_path,
            kit_name=kit_name,
            rendered_samples=rendered_samples,
        )

    return KitConversionResult(
        kit_name=kit_name,
        source_file=str(source_path),
        source_type=source_type,
        source_path=str(source_path),
        pad_profile=pad_profile,
        pad_limit=pad_limit,
        output_xtd=str(output_xtd_path),
        assigned_pad_count=len(rendered_samples),
        copied_sample_count=len(rendered_samples),
        warnings=warnings,
    )


def _build_candidates_from_relative_paths(
    base_root: Path,
    sample_paths: list[str],
    warnings: list[str],
) -> list[SampleCandidate]:
    deduped: OrderedDict[str, SampleCandidate] = OrderedDict()
    for idx, rel_path in enumerate(sample_paths):
        resolved = resolve_sample_path(base_root, rel_path)
        if resolved is None or not resolved.exists():
            warnings.append(f"Missing sample referenced by kit: {rel_path}")
            continue
        key = str(resolved.resolve())
        if key in deduped:
            continue
        deduped[key] = SampleCandidate(
            source_rel=rel_path,
            source_abs=resolved,
            display_name=resolved.stem,
            role=classify_sample(resolved),
            source_index=idx,
        )
    return list(deduped.values())


def _build_candidates_from_files(base_root: Path, wav_files: list[Path]) -> list[SampleCandidate]:
    deduped: OrderedDict[str, SampleCandidate] = OrderedDict()
    for idx, wav_path in enumerate(wav_files):
        if not wav_path.exists() or not wav_path.is_file():
            continue
        # Keep custom kit behavior path-based so distinct files/symlinks are preserved.
        key = str(wav_path.absolute())
        if key in deduped:
            continue
        try:
            rel = wav_path.relative_to(base_root)
            source_rel = rel.as_posix()
        except ValueError:
            source_rel = wav_path.name
        deduped[key] = SampleCandidate(
            source_rel=source_rel,
            source_abs=wav_path,
            display_name=wav_path.stem,
            role=classify_sample(wav_path, source_rel=source_rel),
            source_index=idx,
        )
    return list(deduped.values())


def _discover_custom_kits(
    samples_root: Path,
    grouping: str = "per-folder",
) -> list[tuple[str, Path, list[Path]]]:
    if grouping == "single-kit":
        wav_files = _collect_wavs_interleaved_by_top_folder(samples_root)
        if not wav_files:
            return []
        return [(slugify_kit_name(samples_root.name), samples_root, wav_files)]

    entries: list[tuple[str, Path, list[Path]]] = []
    used_names: set[str] = set()

    for child in sorted(samples_root.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        wav_files = _collect_wavs(child, recursive=True)
        if not wav_files:
            continue
        kit_name = slugify_kit_name(child.name)
        entries.append((kit_name, child, wav_files))
        used_names.add(kit_name)

    root_wavs = _collect_wavs(samples_root, recursive=False)
    if root_wavs:
        root_kit_name = slugify_kit_name(samples_root.name)
        if root_kit_name in used_names:
            root_kit_name = f"{root_kit_name}__root"
        entries.append((root_kit_name, samples_root, root_wavs))

    return entries


def _collect_wavs(path: Path, recursive: bool) -> list[Path]:
    if recursive:
        files = [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() == ".wav"]
    else:
        files = [item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".wav"]
    return sorted(files, key=lambda item: str(item).lower())


def _collect_wavs_interleaved_by_top_folder(path: Path) -> list[Path]:
    wavs = [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() == ".wav"]
    if not wavs:
        return []

    rel_parts = [wav.relative_to(path).parts for wav in wavs]
    first_level_names = {parts[0] for parts in rel_parts if len(parts) > 1}
    bucket_level = 1 if len(first_level_names) == 1 else 0

    buckets: dict[str, list[Path]] = {}
    for wav in sorted(wavs, key=lambda item: str(item).lower()):
        parts = wav.relative_to(path).parts
        if len(parts) <= bucket_level + 1:
            bucket = "__root__"
        else:
            bucket = parts[bucket_level]
        buckets.setdefault(bucket, []).append(wav)

    ordered: list[Path] = []
    keys = sorted(buckets.keys())
    while True:
        moved = False
        for key in keys:
            bucket = buckets[key]
            if not bucket:
                continue
            ordered.append(bucket.pop(0))
            moved = True
        if not moved:
            break
    return ordered


def _make_unique_filename(name: str, used: set[str]) -> str:
    if name not in used:
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix or ".wav"
    index = 2
    while True:
        candidate = f"{stem}_{index}{suffix}"
        if candidate not in used:
            return candidate
        index += 1


def _build_part_seed(base_seed: str | None, part_number: int) -> str | None:
    if base_seed is None:
        return None
    return f"{base_seed}::part={part_number}"
