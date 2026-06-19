from __future__ import annotations

import unittest
from pathlib import Path

from ni_mpc_converter.app.classifier import (
    ROLE_KICK,
    ROLE_OTHER,
    ROLE_PERC,
    ROLE_SNARE,
    classify_sample,
)
from ni_mpc_converter.app.mapper import PAD_PROFILE_CUSTOM, PAD_PROFILE_DARKCHILD, assign_pads
from ni_mpc_converter.app.models import SampleCandidate


def _candidate(idx: int, role: str, name: str) -> SampleCandidate:
    return SampleCandidate(
        source_rel=name,
        source_abs=Path(f"/tmp/{name}"),
        display_name=Path(name).stem,
        role=role,
        source_index=idx,
    )


class DarkchildMapperTests(unittest.TestCase):
    def test_darkchild_anchor_slots(self) -> None:
        samples = [
            _candidate(0, ROLE_KICK, "kick_01.wav"),
            _candidate(1, ROLE_SNARE, "snare_01.wav"),
            _candidate(2, ROLE_PERC, "perc_01.wav"),
            _candidate(3, ROLE_KICK, "kick_02.wav"),
            _candidate(4, ROLE_SNARE, "snare_02.wav"),
            _candidate(5, ROLE_PERC, "perc_02.wav"),
            _candidate(6, ROLE_KICK, "kick_03.wav"),
            _candidate(7, ROLE_SNARE, "snare_03.wav"),
            _candidate(8, ROLE_PERC, "perc_03.wav"),
            _candidate(9, ROLE_PERC, "perc_04.wav"),
            _candidate(10, ROLE_OTHER, "other_01.wav"),
            _candidate(11, ROLE_OTHER, "other_02.wav"),
        ]
        assignments = assign_pads(
            samples,
            pad_count=16,
            profile=PAD_PROFILE_DARKCHILD,
            random_seed="kit-seed",
        )
        by_pad = {item.pad_index: item.sample.role for item in assignments}
        self.assertEqual(by_pad[0], ROLE_KICK)
        self.assertEqual(by_pad[4], ROLE_KICK)
        self.assertEqual(by_pad[8], ROLE_KICK)
        self.assertEqual(by_pad[1], ROLE_SNARE)
        self.assertEqual(by_pad[5], ROLE_SNARE)
        self.assertEqual(by_pad[9], ROLE_SNARE)
        self.assertEqual(by_pad[2], ROLE_PERC)
        self.assertEqual(by_pad[3], ROLE_PERC)
        self.assertEqual(by_pad[6], ROLE_PERC)
        self.assertEqual(by_pad[7], ROLE_PERC)

    def test_darkchild_shortage_backfills_reserved_slots(self) -> None:
        samples = [
            _candidate(0, ROLE_KICK, "kick_01.wav"),
            _candidate(1, ROLE_OTHER, "other_01.wav"),
            _candidate(2, ROLE_OTHER, "other_02.wav"),
            _candidate(3, ROLE_OTHER, "other_03.wav"),
            _candidate(4, ROLE_OTHER, "other_04.wav"),
            _candidate(5, ROLE_OTHER, "other_05.wav"),
            _candidate(6, ROLE_OTHER, "other_06.wav"),
            _candidate(7, ROLE_OTHER, "other_07.wav"),
            _candidate(8, ROLE_OTHER, "other_08.wav"),
            _candidate(9, ROLE_OTHER, "other_09.wav"),
        ]
        assignments = assign_pads(
            samples,
            pad_count=10,
            profile=PAD_PROFILE_DARKCHILD,
            random_seed="shortage-seed",
        )
        by_pad = {item.pad_index: item.sample.display_name for item in assignments}
        for required_pad in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
            self.assertIn(required_pad, by_pad)

    def test_darkchild_deterministic_random(self) -> None:
        samples = [_candidate(i, ROLE_OTHER, f"other_{i:02d}.wav") for i in range(20)]
        first = assign_pads(
            samples,
            pad_count=16,
            profile=PAD_PROFILE_DARKCHILD,
            random_seed="stable-seed",
        )
        second = assign_pads(
            samples,
            pad_count=16,
            profile=PAD_PROFILE_DARKCHILD,
            random_seed="stable-seed",
        )
        third = assign_pads(
            samples,
            pad_count=16,
            profile=PAD_PROFILE_DARKCHILD,
            random_seed="different-seed",
        )
        first_names = [item.sample.display_name for item in first]
        second_names = [item.sample.display_name for item in second]
        third_names = [item.sample.display_name for item in third]
        self.assertEqual(first_names, second_names)
        self.assertNotEqual(first_names, third_names)

    def test_custom_profile_uses_supplied_anchor_slots(self) -> None:
        samples = [
            _candidate(0, ROLE_KICK, "kick_01.wav"),
            _candidate(1, ROLE_SNARE, "snare_01.wav"),
            _candidate(2, ROLE_PERC, "perc_01.wav"),
            _candidate(3, ROLE_OTHER, "other_01.wav"),
            _candidate(4, ROLE_OTHER, "other_02.wav"),
        ]
        assignments = assign_pads(
            samples,
            pad_count=16,
            profile=PAD_PROFILE_CUSTOM,
            random_seed="custom-seed",
            custom_role_slots={
                ROLE_KICK: [15],
                ROLE_SNARE: [14],
                ROLE_PERC: [13],
            },
        )
        by_pad = {item.pad_index: item.sample.role for item in assignments}
        self.assertEqual(by_pad[15], ROLE_KICK)
        self.assertEqual(by_pad[14], ROLE_SNARE)
        self.assertEqual(by_pad[13], ROLE_PERC)


class ClassifierFallbackTests(unittest.TestCase):
    def test_percz_folder_falls_back_to_perc(self) -> None:
        role = classify_sample(Path("/tmp/1 009.wav"), source_rel="Percz/1 009.wav")
        self.assertEqual(role, ROLE_PERC)

    def test_folder_aliases_for_kick_and_snare(self) -> None:
        self.assertEqual(
            classify_sample(Path("/tmp/001.wav"), source_rel="Kickz/001.wav"),
            ROLE_KICK,
        )
        self.assertEqual(
            classify_sample(Path("/tmp/001.wav"), source_rel="Snz/001.wav"),
            ROLE_SNARE,
        )

    def test_filename_heuristic_still_takes_priority(self) -> None:
        role = classify_sample(Path("/tmp/Snare 01.wav"), source_rel="Kickz/Snare 01.wav")
        self.assertEqual(role, ROLE_SNARE)


if __name__ == "__main__":
    unittest.main()
