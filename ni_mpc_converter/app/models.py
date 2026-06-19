from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SampleCandidate:
    source_rel: str
    source_abs: Path
    display_name: str
    role: str
    source_index: int


@dataclass(frozen=True)
class PadAssignment:
    pad_index: int
    sample: SampleCandidate


@dataclass(frozen=True)
class RenderedSample:
    display_name: str
    output_filename: str
    output_path: Path
    role: str
    frame_count: int


@dataclass
class KitConversionResult:
    kit_name: str
    source_file: str
    source_type: str
    source_path: str
    pad_profile: str
    pad_limit: int
    output_xtd: str
    assigned_pad_count: int
    copied_sample_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConversionReport:
    source_type: str
    source_root: str
    ni_root: str
    pad_profile: str
    output_root: str
    template_xtd: str
    scanned_kits: int
    converted_kits: int
    skipped_kits: int
    kit_results: list[KitConversionResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
