# Native Instruments to MPC Converter App Outline

## Goal

Build a desktop or command-line application that converts sample-based Native Instruments / Maschine expansion content into Akai MPC drum programs that can load on MPC hardware or MPC desktop software.[cite:21][cite:18]

The practical output target is an MPC drum program stored as an `.xpm` file plus referenced `.wav` samples organized in a predictable folder structure.[cite:21][cite:18]

## Product Scope

The first release should focus on converting **sample-based drum kits**, not full Maschine projects, synth presets, effects chains, or advanced instrument behavior.[cite:18][cite:32]

A realistic v1 should support one kit at a time or batch conversion of multiple kits, generate Bank A pad assignments, create 44.1 kHz WAV output, and apply a basic MPC-friendly pad layout with hi-hat choke support.[cite:18][cite:21]

## Source Library Assumptions

A standard Maschine expansion usually contains folders such as `Groups`, `Projects`, `Samples`, `Sounds`, and `Documentation`.[cite:18]

The app should treat the top-level expansion folder as the input root and scan it for kits, sample references, and group-level metadata that can be transformed into MPC drum programs.[cite:18]

## Target MPC Model

Akai identifies drum programs as MPC program presets and notes that these appear as `.xpm` files in modern MPC workflows.[cite:21]

Kit Maker’s MPC documentation also states that modern MPC hardware uses `.xpm` programs and supports loading those programs as presets after transfer.[cite:18]

## Output Folder Design

A clean intermediate output structure can be:

```text
ExpansionName/
  Programs/
    Kit-01.xpm
    Kit-02.xpm
  Samples/
    Kit-01/
      kick_01.wav
      snare_01.wav
      hat_closed_01.wav
    Kit-02/
      ...
```

Third-party MPC expansion guides describe content layouts built around `Programs` for `.xpm` files and `Samples` for WAV assets before optional packaging into installer-style expansions.[cite:25][cite:28]

## Major Components

### 1. Input Scanner

Detect whether the source is an official Maschine expansion, a loose drum sample pack, or a pre-grouped kit folder.[cite:18]

The scanner should validate that expected subfolders exist and reject unsupported inputs early with clear error messages.[cite:18]

### 2. Source Parser

Parse kits, groups, sample references, names, and any source pad ordering that can be preserved during conversion.[cite:18][cite:32]

If the source metadata is weak, the parser should still extract enough information for a fallback filename-based classification pass.[cite:18]

### 3. Sample Classifier

The classifier should infer sound roles from names such as kick, snare, clap, rim, closed hat, open hat, tom, percussion, and FX.[cite:18]

This layer is essential for loose sample packs and for any source kit that does not expose a clean pad map.[cite:18]

### 4. Audio Normalizer

Kit Maker’s MPC notes say MPC workflows expect `.wav` files at 44.1 kHz, so the converter should resample and rewrite all referenced audio into a compliant format before program generation.[cite:18]

This stage can be built with FFmpeg, PyAV, or Python audio libraries, but the output contract should stay fixed: WAV at 44,100 Hz, preserving mono or stereo as needed.[cite:18][cite:25]

### 5. Pad Mapper

The mapper should assign sounds to MPC pad slots using either preserved source layout or a smart default layout.[cite:18]

Kit Maker’s documentation indicates that primary sounds such as kicks, snares, and closed hats should receive priority placement, which makes that a strong default design rule.[cite:18]

### 6. Program Writer

Akai support material confirms the `.xpm` format is the modern MPC drum-program target, so the app needs a dedicated writer that serializes the internal kit model into valid `.xpm` output.[cite:21]

Because public documentation does not fully describe the `.xpm` schema in the cited support material, the writer should be developed from reverse-engineering saved MPC program files.[cite:21]

### 7. Optional Packager

If expansion-style distribution is needed later, the app can add packaging support for a full MPC expansion workflow after the raw `.xpm` + sample output is working.[cite:25][cite:28]

This should be considered a post-v1 feature unless installer creation is a hard requirement.[cite:25][cite:28]

## Internal Data Model

The internal model should represent programs, banks, pads, and sample layers separately so the app is not tightly coupled to one source format.[cite:21]

Chicken Systems’ MPC format notes say an MPC-R `.xpm` program can contain up to 128 pads across 8 banks and can assign up to 4 mono or stereo samples per pad, so the model should be future-proofed for those limits even if v1 only writes one bank and one layer per pad.[cite:33]

Suggested internal entities:

- `Program`: name, tempo-optional metadata, banks.
- `Bank`: bank ID such as A through H, 16 pad slots.
- `Pad`: note number, pad index, category, choke group, tuning, gain, playback options.
- `SampleRef`: file path, start, end, loop info, gain, tuning, channel mode.
- `ConversionJob`: source path, output path, policy options, logs, validation results.

## Mapping Rules

The app should support two mapping modes: **preserve source layout** and **smart inferred layout**.[cite:18]

A useful default pad order places core sounds first, such as kick, snare, closed hat, open hat, clap, rim, toms, percussion, and FX, while automatically assigning open and closed hi-hats to the same choke group.[cite:18]

Example v1 pad strategy:

- Pad 1: Kick 1
- Pad 2: Snare 1
- Pad 3: Closed Hat 1
- Pad 4: Open Hat 1
- Pad 5: Clap
- Pad 6: Rim / Perc 1
- Pad 7: Tom / Perc 2
- Pad 8: FX 1
- Pads 9–16: alternates, extra percussion, layers, and variations

## Reverse-Engineering Plan

The highest-risk technical area is generating valid `.xpm` files, because the public material cited here confirms the format but does not fully document its schema.[cite:21]

A safe reverse-engineering workflow is to create small test drum programs in MPC software, save multiple controlled variants, and compare the saved files to learn which fields map to pad assignments, choke groups, tuning, bank count, and sample references.[cite:21]

Recommended fixture set:

- A one-sample, one-pad program.
- A 16-pad Bank A program.
- A hi-hat choke example.
- A tuned sample example.
- A two-bank example.
- A layered pad example if supported in the target save path.[cite:33]

## Suggested Python Project Structure

```text
ni_mpc_converter/
  app/
    cli.py
    config.py
    models.py
    scanner.py
    parser_maschine.py
    classifier.py
    mapper.py
    audio.py
    writer_xpm.py
    validate.py
    package_mpc.py
  tests/
    fixtures/
    test_scanner.py
    test_classifier.py
    test_mapper.py
    test_writer_xpm.py
  docs/
    reverse_engineering_notes.md
  pyproject.toml
  README.md
```

This structure separates source-specific parsing from MPC-specific writing, which makes it easier to add new source formats later.[cite:18][cite:21]

## Suggested Build Phases

### Phase 1: Research and Fixtures

- Collect real Maschine expansion folder examples.[cite:18]
- Save multiple minimal MPC drum programs as `.xpm` fixtures.[cite:21]
- Document observed `.xpm` differences across controlled edits.[cite:21]

### Phase 2: Intermediate JSON Pipeline

Before writing `.xpm`, build a stable internal JSON representation of a converted kit that includes pads, samples, choke groups, and normalized paths.[cite:21][cite:18]

This de-risks the project by validating scanner, parser, classifier, and mapper logic independently from the file-format writer.[cite:21]

### Phase 3: Audio Prep

Implement WAV normalization to 44.1 kHz and verify converted files load cleanly in MPC workflows.[cite:18][cite:25]

### Phase 4: XPM Writer

Implement a minimal `.xpm` writer that supports one bank, one sample layer per pad, and no advanced pad modulation.[cite:21]

Use MPC software or hardware as the validation loop for every generated file.[cite:21]

### Phase 5: UX Layer

Add CLI flags or a small desktop GUI for source path, output path, naming rules, mapping mode, batch conversion, and dry-run validation.[cite:18]

### Phase 6: Packaging and Polish

Add optional expansion packaging, artwork support, logs, progress reporting, error summaries, and template presets for common mapping styles.[cite:25][cite:28]

## Validation Strategy

Every conversion should produce a machine-readable validation report and a human-readable summary stating:

- Which kits were found.
- Which samples were referenced.
- Which files were converted to 44.1 kHz WAV.[cite:18]
- Which pads were assigned.
- Which choke groups were added.[cite:18]
- Whether the output `.xpm` loaded successfully in MPC software or hardware.[cite:21]
- Which source elements were skipped because they were not sample-based.[cite:18]

## Technical Risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| `.xpm` schema is not fully documented | Invalid writer output may not load on MPC | Reverse-engineer real saved files and build fixture-based tests.[cite:21] |
| Maschine content may include non-sample instruments | Not all source material can become a drum kit | Restrict v1 to sample-based kits and report skipped items clearly.[cite:18][cite:32] |
| Sample-rate mismatches | MPC workflows expect 44.1 kHz WAV for this use case | Normalize all output audio in a dedicated prep stage.[cite:18][cite:25] |
| Weak source metadata | Loose packs may not define pad roles | Add filename-based classification and user-overridable mapping rules.[cite:18] |
| Over-scoping v1 | Delays usable release | Start with Bank A, one layer per pad, sample-based kits only.[cite:21][cite:18] |

## Recommended v1 Feature Set

The strongest first milestone is a converter that takes one Maschine expansion or one organized drum-sample folder, classifies the samples, normalizes them, maps them to Bank A, applies hi-hat choke behavior, and writes a loadable MPC drum program.[cite:18][cite:21]

That scope is narrow enough to ship and broad enough to prove the full pipeline before adding multi-bank, multi-layer, keygroup, or full expansion-packaging features.[cite:33][cite:25]

## Suggested Next Tasks

1. Create fixture `.xpm` files in MPC software and diff them.[cite:21]
2. Build the internal JSON schema and unit tests.[cite:21]
3. Implement the audio normalization module for 44.1 kHz WAV output.[cite:18][cite:25]
4. Implement a filename-based drum classifier.[cite:18]
5. Build the v1 Bank A pad mapper with hi-hat choke logic.[cite:18]
6. Implement and test the first `.xpm` writer.[cite:21]
7. Add batch processing and structured logs.[cite:18]
