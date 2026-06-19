from __future__ import annotations

import hashlib
import random

from .classifier import (
    ROLE_CLAP,
    ROLE_FX,
    ROLE_HAT_CLOSED,
    ROLE_HAT_OPEN,
    ROLE_KICK,
    ROLE_OTHER,
    ROLE_PERC,
    ROLE_RIM,
    ROLE_SNARE,
    ROLE_TOM,
)
from .models import PadAssignment, SampleCandidate

PAD_PROFILE_DEFAULT = "default"
PAD_PROFILE_DARKCHILD = "darkchild"
PAD_PROFILE_CUSTOM = "custom"

DEFAULT_CUSTOM_ROLE_SLOTS = {
    ROLE_KICK: [0, 4, 8],
    ROLE_SNARE: [1, 5, 9],
    ROLE_PERC: [2, 3, 6, 7],
    ROLE_CLAP: [12, 13, 14, 15],
}

PRIMARY_SLOT_RULES = [
    [ROLE_KICK],
    [ROLE_SNARE],
    [ROLE_HAT_CLOSED],
    [ROLE_HAT_OPEN],
    [ROLE_CLAP],
    [ROLE_RIM, ROLE_PERC],
    [ROLE_TOM, ROLE_PERC],
    [ROLE_FX, ROLE_PERC, ROLE_OTHER],
]

ROLE_PRIORITY = {
    ROLE_KICK: 0,
    ROLE_SNARE: 1,
    ROLE_HAT_CLOSED: 2,
    ROLE_HAT_OPEN: 3,
    ROLE_CLAP: 4,
    ROLE_RIM: 5,
    ROLE_TOM: 6,
    ROLE_PERC: 7,
    ROLE_FX: 8,
    ROLE_OTHER: 9,
}


def assign_pads(
    samples: list[SampleCandidate],
    pad_count: int = 16,
    remaining_mode: str = "priority",
    profile: str = PAD_PROFILE_DEFAULT,
    random_seed: str | None = None,
    custom_role_slots: dict[str, list[int]] | None = None,
) -> list[PadAssignment]:
    if not samples:
        return []

    if profile == PAD_PROFILE_DARKCHILD:
        return _assign_pads_anchored(
            samples,
            pad_count=pad_count,
            random_seed=random_seed,
            role_slots={
                ROLE_KICK: [0, 4, 8],
                ROLE_SNARE: [1, 5, 9],
                ROLE_PERC: [2, 3, 6, 7],
            },
        )

    if profile == PAD_PROFILE_CUSTOM:
        return _assign_pads_anchored(
            samples,
            pad_count=pad_count,
            random_seed=random_seed,
            role_slots=custom_role_slots or DEFAULT_CUSTOM_ROLE_SLOTS,
        )

    return _assign_pads_default(samples, pad_count=pad_count, remaining_mode=remaining_mode)


def _assign_pads_default(
    samples: list[SampleCandidate],
    pad_count: int,
    remaining_mode: str,
) -> list[PadAssignment]:
    used_indices: set[int] = set()
    assignments: list[PadAssignment] = []
    used_pad_indices: set[int] = set()

    for slot, accepted_roles in enumerate(PRIMARY_SLOT_RULES):
        if slot >= pad_count:
            break
        chosen_index = _find_first_index(samples, used_indices, accepted_roles)
        if chosen_index is None:
            continue
        used_indices.add(chosen_index)
        assignments.append(PadAssignment(pad_index=slot, sample=samples[chosen_index]))
        used_pad_indices.add(slot)

    remaining = [
        sample
        for idx, sample in enumerate(samples)
        if idx not in used_indices
    ]
    if remaining_mode == "balanced":
        remaining = _balanced_by_role(remaining)
    else:
        remaining.sort(key=lambda sample: (ROLE_PRIORITY.get(sample.role, 99), sample.source_index))

    for sample in remaining:
        next_pad = _next_free_pad(used_pad_indices, pad_count)
        if next_pad is None:
            break
        assignments.append(PadAssignment(pad_index=next_pad, sample=sample))
        used_pad_indices.add(next_pad)

    # Keep deterministic pad order.
    assignments.sort(key=lambda item: item.pad_index)
    return assignments[:pad_count]


def _assign_pads_anchored(
    samples: list[SampleCandidate],
    pad_count: int,
    random_seed: str | None,
    role_slots: dict[str, list[int]],
) -> list[PadAssignment]:
    used_indices: set[int] = set()
    used_pad_indices: set[int] = set()
    assignments: list[PadAssignment] = []
    missing_reserved_slots: list[int] = []

    for role, slots in role_slots.items():
        role_indices = _find_indices_for_role(samples, used_indices, role)
        for slot in [slot for slot in slots if 0 <= slot < pad_count and slot not in used_pad_indices]:
            if role_indices:
                sample_index = role_indices.pop(0)
                used_indices.add(sample_index)
                used_pad_indices.add(slot)
                assignments.append(PadAssignment(pad_index=slot, sample=samples[sample_index]))
                continue
            missing_reserved_slots.append(slot)

    remaining = [
        sample
        for idx, sample in enumerate(samples)
        if idx not in used_indices
    ]
    remaining = _deterministic_shuffle(remaining, random_seed=random_seed)

    for slot in missing_reserved_slots:
        if not remaining:
            break
        assignments.append(PadAssignment(pad_index=slot, sample=remaining.pop(0)))
        used_pad_indices.add(slot)

    for slot in range(pad_count):
        if slot in used_pad_indices:
            continue
        if not remaining:
            break
        assignments.append(PadAssignment(pad_index=slot, sample=remaining.pop(0)))
        used_pad_indices.add(slot)

    assignments.sort(key=lambda item: item.pad_index)
    return assignments[:pad_count]


def _find_first_index(
    samples: list[SampleCandidate],
    used_indices: set[int],
    accepted_roles: list[str],
) -> int | None:
    for idx, sample in enumerate(samples):
        if idx in used_indices:
            continue
        if sample.role in accepted_roles:
            return idx
    return None


def _find_indices_for_role(
    samples: list[SampleCandidate],
    used_indices: set[int],
    role: str,
) -> list[int]:
    indices: list[int] = []
    for idx, sample in enumerate(samples):
        if idx in used_indices:
            continue
        if sample.role != role:
            continue
        indices.append(idx)
    return indices


def _next_free_pad(used_pad_indices: set[int], pad_count: int) -> int | None:
    for idx in range(pad_count):
        if idx not in used_pad_indices:
            return idx
    return None


def _balanced_by_role(samples: list[SampleCandidate]) -> list[SampleCandidate]:
    role_order = [
        ROLE_KICK,
        ROLE_SNARE,
        ROLE_HAT_CLOSED,
        ROLE_HAT_OPEN,
        ROLE_CLAP,
        ROLE_RIM,
        ROLE_TOM,
        ROLE_PERC,
        ROLE_FX,
        ROLE_OTHER,
    ]
    buckets: dict[str, list[SampleCandidate]] = {role: [] for role in role_order}
    for sample in sorted(samples, key=lambda item: item.source_index):
        role = sample.role if sample.role in buckets else ROLE_OTHER
        buckets[role].append(sample)

    ordered: list[SampleCandidate] = []
    while True:
        moved = False
        for role in role_order:
            bucket = buckets[role]
            if not bucket:
                continue
            ordered.append(bucket.pop(0))
            moved = True
        if not moved:
            break
    return ordered


def _deterministic_shuffle(samples: list[SampleCandidate], random_seed: str | None) -> list[SampleCandidate]:
    if len(samples) <= 1:
        return list(samples)

    if random_seed is None:
        random_seed = "default"
    digest = hashlib.sha256(random_seed.encode("utf-8")).hexdigest()
    seed = int(digest[:16], 16)
    rng = random.Random(seed)
    shuffled = list(samples)
    rng.shuffle(shuffled)
    return shuffled
