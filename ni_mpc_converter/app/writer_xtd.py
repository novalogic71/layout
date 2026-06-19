from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

from .classifier import ROLE_HAT_CLOSED, ROLE_HAT_OPEN
from .models import RenderedSample

PAD_COLOR_BY_ROLE = {
    "kick": 16711680,
    "snare": 16776960,
    "hat_closed": 6238976,
    "hat_open": 6238976,
    "clap": 16776960,
    "rim": 16776960,
    "tom": 2268880,
    "perc": 6238976,
    "fx": 6238976,
    "other": 6238976,
}


def load_xtd_template(template_xtd_path: Path) -> tuple[list[str], dict]:
    with gzip.open(template_xtd_path, "rb") as handle:
        text = handle.read().decode("utf-8", errors="ignore")

    lines = text.splitlines()
    if len(lines) < 6:
        raise ValueError(f"Unexpected XTD template format: {template_xtd_path}")

    header_lines = lines[:5]
    payload = json.loads("\n".join(lines[5:]))
    if "data" not in payload:
        raise ValueError(f"Missing data payload in template: {template_xtd_path}")

    return header_lines, payload


def write_xtd_from_template(
    header_lines: list[str],
    template_payload: dict,
    output_xtd_path: Path,
    kit_name: str,
    rendered_samples: list[RenderedSample],
) -> None:
    payload = copy.deepcopy(template_payload)
    data = payload["data"]
    program = data["program"]

    data["name"] = kit_name
    program["name"] = kit_name

    data["samples"] = [
        {"name": item.display_name, "path": item.output_filename, "loadImpl": 0}
        for item in rendered_samples
    ]

    _rewrite_program_instruments(program, rendered_samples)
    _rewrite_program_pad_colors(program, rendered_samples)

    text = "\n".join(header_lines) + "\n" + json.dumps(payload, indent=4) + "\n"
    output_xtd_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_xtd_path, "wb") as handle:
        handle.write(text.encode("utf-8"))


def _rewrite_program_instruments(program: dict, rendered_samples: list[RenderedSample]) -> None:
    instruments = program["drum"]["instruments"]
    blank = None
    for instrument in instruments:
        first_layer = instrument["layersv"][0]
        if not first_layer.get("sampleFile"):
            blank = instrument
            break
    if blank is None:
        blank = instruments[-1]

    new_instruments = []
    for index in range(128):
        if index < len(rendered_samples):
            sample = rendered_samples[index]
            instrument = copy.deepcopy(blank)
            layer = instrument["layersv"][0]
            layer["sampleName"] = sample.display_name
            layer["sampleFile"] = sample.output_filename
            layer["sliceIndex"] = 128
            layer["sliceInfo"]["Start"] = 0
            layer["sliceInfo"]["End"] = max(sample.frame_count, 0)
            layer["sliceInfo"]["LoopStart"] = 0
            layer["sliceInfo"]["LoopMode"] = 0
            instrument["whichMuteGroup"] = (
                1 if sample.role in (ROLE_HAT_CLOSED, ROLE_HAT_OPEN) else 0
            )
        else:
            instrument = copy.deepcopy(blank)
        new_instruments.append(instrument)

    program["drum"]["instruments"] = new_instruments


def _rewrite_program_pad_colors(program: dict, rendered_samples: list[RenderedSample]) -> None:
    pad_colors = program["programPads"]["pads"]
    for index in range(128):
        color = 0
        if index < len(rendered_samples):
            role = rendered_samples[index].role
            color = PAD_COLOR_BY_ROLE.get(role, PAD_COLOR_BY_ROLE["other"])
        pad_colors[f"value{index}"] = color

