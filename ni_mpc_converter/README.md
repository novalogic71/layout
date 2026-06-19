# NI to MPC Converter (v1)

Converts:

- Native Instruments Maschine kit files (`.mxgrp`)
- Custom raw sample folders (`.wav`)

into MPC-style track kits (`.xtd`) using a real MPC `.xtd` template from your library.

## What v1 does

- Scans `Groups/Kits/*.mxgrp` in a Maschine expansion.
- Scans custom sample roots and creates kits from sample folders.
- Extracts referenced sample paths from binary `.mxgrp` data.
- Classifies sample roles (kick, snare, closed/open hat, clap, etc.).
- Maps NI kits up to 32 pads and custom kits up to 32 pads.
- Copies WAVs into `KitName_[TrackData]/`.
- Writes `KitName.xtd` using your existing MPC `.xtd` schema as a template.
- Outputs a JSON conversion report.

## What v1 does not do yet

- True `.xpm` writing.
- Full Maschine effect-chain translation.
- Full Battery (`.nbkt`) parsing.

## Quick start

From `/Volumes/Data/MPC_Converter`:

Run the local web app:

```bash
python3 -m ni_mpc_converter.app.web
```

Then open `http://127.0.0.1:8765`.

The web UI is a TypeScript frontend served by the Python backend. After installing npm dependencies, rebuild the frontend with:

```bash
npm install
npm run build:web
```

## Local desktop app builds

The desktop build is a local wrapper around the same web app. It starts the Python server on `127.0.0.1`, opens the app in the default browser, and keeps everything running locally on the machine.

Run the desktop launcher from source:

```bash
python3 -m ni_mpc_converter.app.desktop
```

Build a local executable with PyInstaller:

macOS/Linux:

```bash
python3 -m pip install pyinstaller
python3 -m PyInstaller \
  --name MPC-Converter \
  --onefile \
  --clean \
  --add-data "ni_mpc_converter/web:ni_mpc_converter/web" \
  ni_mpc_converter/app/desktop.py
```

Windows PowerShell:

```powershell
python -m pip install pyinstaller
python -m PyInstaller `
  --name MPC-Converter `
  --onefile `
  --clean `
  --add-data "ni_mpc_converter/web;ni_mpc_converter/web" `
  ni_mpc_converter/app/desktop.py
```

The built executable will be in `dist/`.

## GitHub Actions deployment

This repo includes `.github/workflows/build-desktop.yml`.

To build macOS and Windows desktop artifacts:

1. Push the repo to GitHub.
2. Open the GitHub repo.
3. Go to `Actions`.
4. Run `Build Desktop Apps`, or push to the `main` branch.
5. Download the artifacts:
   - `MPC-Converter-macOS`
   - `MPC-Converter-Windows`

Notes:

- GitHub Actions does not include your local MPC packs, NI expansions, or output folders.
- The built app runs locally on the user's computer.
- The user still selects local paths for NI roots, sample roots, MPC root, and output root in the web UI.
- macOS may require approving the downloaded app in System Settings because the build is not signed/notarized yet.

Run the CLI directly:

```bash
python3 -m ni_mpc_converter.app.cli \
  --ni-root "/Volumes/Data/MPC_Converter/Aquarius Earth Library" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x" \
  --limit 3
```

Convert multiple packs by repeating `--ni-root`:

```bash
python3 -m ni_mpc_converter.app.cli \
  --ni-root "/Volumes/Data/MPC_Converter/Aquarius Earth Library" \
  --ni-root "/path/to/Another Expansion" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd_multi" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Convert all packs found under one parent folder:

```bash
python3 -m ni_mpc_converter.app.cli \
  --ni-parent "/Volumes/Data/NI_Expansions" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd_multi" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Notes for multi-pack mode:

- Each pack is written to its own subfolder under `--output-root`.
- Each pack gets its own `conversion-report.json`.
- A top-level `multi-pack-report.json` is generated.

Convert custom sample packs:

```bash
python3 -m ni_mpc_converter.app.cli \
  --samples-root "/path/to/custom_pack" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd_custom" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Convert all custom sample packs under a parent:

```bash
python3 -m ni_mpc_converter.app.cli \
  --samples-parent "/path/to/custom_pack_parent" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd_custom_multi" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Run NI and custom sources together:

```bash
python3 -m ni_mpc_converter.app.cli \
  --ni-root "/Volumes/Data/MPC_Converter/Aquarius Earth Library" \
  --samples-root "/path/to/custom_pack" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd_mixed" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Custom kit rules:

- One kit per immediate subfolder in each custom root.
- One additional root kit from root-level WAV files.
- Subfolder WAV scan is recursive.
- Input format is WAV-only.
- If a kit exceeds pad capacity, additional files are created as `Kit__2`, `Kit__3`, etc.
- Existing output kits are never overwritten; existing targets are skipped.

To merge category folders (for example `Kicks`, `Snares`, `Hats`) into one unique kit per root:

```bash
python3 -m ni_mpc_converter.app.cli \
  --samples-root "/path/to/custom_pack" \
  --samples-grouping single-kit \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd_custom_singlekit" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Use Darkchild-style pad anchors for custom kits (opt-in profile):

```bash
python3 -m ni_mpc_converter.app.cli \
  --samples-root "/Volumes/RAID1_bak/Shared/Jonlick sounds" \
  --samples-grouping per-folder \
  --pad-profile darkchild \
  --output-root "/Volumes/Data/MPC_Converter/out_jonlick_darkchild" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x"
```

Darkchild profile behavior:

- Kicks target pads `01,05,09`.
- Snares target pads `02,06,10`.
- Perc targets pads `03,04,07,08`.
- Remaining pads fill with deterministic-random ordering.
- Folder-name fallback classification is used when filenames are ambiguous (for example `Percz/1 009.wav`).

The web app also includes a `Custom` pad profile. Use it when you want to type your own pad anchors for kicks, snares, percussion, and claps before the remaining pads are filled.

Convert a single kit:

```bash
python3 -m ni_mpc_converter.app.cli \
  --ni-root "/Volumes/Data/MPC_Converter/Aquarius Earth Library" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x" \
  --kit "Mo Money Kit"
```

Disable audio normalization:

```bash
python3 -m ni_mpc_converter.app.cli \
  --ni-root "/Volumes/Data/MPC_Converter/Aquarius Earth Library" \
  --output-root "/Volumes/Data/MPC_Converter/converted_xtd" \
  --mpc-root "/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x" \
  --no-normalize-audio
```
