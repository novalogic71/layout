from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Any

from .cli import (
    SOURCE_TYPE_NI,
    _convert_for_source,
    _resolve_sources,
    _resolve_template_xtd,
    _safe_subdir_name,
    _unique_subdir_name,
)
from .convert import write_report
from .mapper import PAD_PROFILE_CUSTOM, PAD_PROFILE_DARKCHILD, PAD_PROFILE_DEFAULT


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
STATIC_ROOT = WEB_ROOT / "static"


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NI to MPC Converter</title>
  <style>
    :root {
      --bg: #090909;
      --case: #2d2d2b;
      --case-hi: #3a3a37;
      --module: #1b1b1a;
      --module-2: #242424;
      --header: #3a3a3a;
      --ink: #ece8df;
      --muted: #a7a198;
      --dim: #74706a;
      --line: #55524d;
      --shadow: #050505;
      --orange: #ff951f;
      --orange-hi: #ffb15a;
      --orange-deep: #d86100;
      --green: #58c776;
      --red: #ff665f;
      --field: #10100f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 20% 8%, rgba(255,149,31,0.1), transparent 20rem),
        linear-gradient(145deg, #050505 0%, #141414 55%, #060606 100%);
      color: var(--ink);
      font: 14px/1.45 Avenir Next, Avenir, Helvetica Neue, sans-serif;
    }
    .shell {
      min-height: 100vh;
      padding: 1rem;
      display: flex;
      align-items: stretch;
    }
    .machine {
      width: min(1180px, 100%);
      margin: auto;
      border: 3px solid var(--orange);
      border-radius: 10px;
      background: linear-gradient(180deg, #30302e, #20201f 52%, #343330);
      box-shadow: 0 1.2rem 4rem rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.08);
      padding: 1rem;
    }
    header {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: flex-start;
      margin-bottom: 0.9rem;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.7rem, 2.6vw, 2.7rem);
      line-height: 1;
      letter-spacing: 0;
      font-weight: 900;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.7rem;
    }
    .mark {
      width: 2rem;
      aspect-ratio: 1;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 2px;
    }
    .mark span {
      display: block;
      background: linear-gradient(180deg, #f9f7ef, #c9c2b6);
      box-shadow: 0 0 0 1px rgba(0,0,0,0.45);
    }
    .mark span:nth-child(3n), .title-accent { color: var(--orange); }
    .mark span:nth-child(3n) { background: var(--orange); }
    .note, .hint, .status-sub { color: var(--muted); }
    .note { margin: 0.25rem 0 0; }
    .guide {
      max-width: 28rem;
      display: grid;
      gap: 0.25rem;
      color: var(--muted);
      font-size: 0.88rem;
    }
    .guide p { margin: 0; }
    main { min-width: 0; }
    form {
      display: grid;
      grid-template-columns: minmax(17rem, 0.95fr) minmax(22rem, 1.25fr) minmax(17rem, 0.95fr);
      gap: 1rem;
      align-items: start;
    }
    fieldset {
      margin: 0;
      padding: 0.75rem;
      min-width: 0;
      border: 2px solid #50504e;
      border-radius: 18px;
      background: linear-gradient(180deg, #282827, #181818);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05), 0 1rem 1.6rem rgba(0,0,0,0.35);
    }
    legend {
      width: calc(100% + 1.5rem);
      margin: -0.75rem -0.75rem 0.75rem;
      padding: 0.55rem 0.8rem;
      border-radius: 14px 14px 0 0;
      background: linear-gradient(180deg, #494949, #333333);
      color: var(--ink);
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    label {
      display: grid;
      gap: 0.28rem;
      color: #d9d3c8;
      font-weight: 800;
      letter-spacing: 0.02em;
    }
    .section-help, .field-help {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.35;
    }
    .section-help { margin: 0 0 0.8rem; }
    .field-help { margin: 0.22rem 0 0.65rem; }
    .field-help code {
      color: var(--orange-hi);
      font: 0.8rem/1.3 Menlo, Consolas, monospace;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid #3e3e3b;
      border-radius: 4px;
      background: var(--field);
      color: var(--ink);
      font: 12px/1.35 Menlo, Consolas, monospace;
      padding: 0.55rem;
      box-shadow: inset 0 0.18rem 0.45rem rgba(0,0,0,0.55);
    }
    textarea {
      min-height: 4.8rem;
      resize: vertical;
    }
    input:focus, textarea:focus, select:focus {
      outline: 2px solid rgba(255,149,31,0.5);
      border-color: var(--orange);
    }
    .row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.7rem;
    }
    .wide { grid-column: auto; }
    .layout-module {
      display: grid;
      gap: 0.75rem;
    }
    .pad-deck {
      padding: 0.75rem;
      border-radius: 14px;
      background: #121211;
      box-shadow: inset 0 0 1.2rem rgba(0,0,0,0.8);
    }
    .pad-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.45rem;
    }
    .pad {
      min-height: 4.1rem;
      border: 1px solid #080808;
      border-radius: 3px;
      background: linear-gradient(145deg, #3d3d3b, #181818);
      box-shadow: 0 0.35rem 0.65rem rgba(0,0,0,0.55), inset 0 1px rgba(255,255,255,0.08);
      padding: 0.45rem;
      color: #dcd7cf;
      font-size: 0.72rem;
      font-weight: 850;
    }
    .pad span {
      display: block;
      color: var(--orange);
      font-size: 0.78rem;
    }
    .toggle-panel {
      display: grid;
      gap: 0.6rem;
      padding: 0.8rem;
      border-radius: 12px;
      background: #111110;
    }
    .checks {
      display: grid;
      gap: 0.48rem;
    }
    .checks label, .format-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 800;
      color: #d9d3c8;
    }
    input[type="checkbox"] {
      width: 0.85rem;
      height: 0.85rem;
      accent-color: var(--orange);
      box-shadow: none;
    }
    .actions {
      display: grid;
      gap: 0.5rem;
      margin-top: 0.75rem;
    }
    button {
      width: 100%;
      border: 1px solid #ffbd73;
      border-radius: 6px;
      background: linear-gradient(180deg, var(--orange-hi), var(--orange));
      color: #fff;
      text-shadow: 0 1px rgba(0,0,0,0.3);
      font-weight: 900;
      padding: 0.72rem 1rem;
      cursor: pointer;
      box-shadow: 0 0.45rem 0.8rem rgba(0,0,0,0.38);
    }
    button:hover { background: linear-gradient(180deg, #ffc47e, #ff8b08); }
    button:disabled { opacity: 0.58; cursor: wait; }
    .status {
      grid-column: 1 / -1;
      margin-top: 1rem;
      border: 2px solid #50504e;
      border-radius: 18px;
      padding: 0.85rem;
      background: #161615;
    }
    .status h2 {
      margin: 0 0 0.35rem;
      font-size: 1.05rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.5rem;
      margin: 0.8rem 0;
    }
    .metric {
      border: 1px solid #3e3e3b;
      border-radius: 6px;
      padding: 0.65rem;
      background: #232321;
      color: var(--muted);
    }
    .metric strong {
      display: block;
      color: var(--orange);
      font-size: 1.3rem;
    }
    .error { color: var(--red); font-weight: 850; }
    .ok { color: var(--green); font-weight: 850; }
    pre {
      overflow: auto;
      max-height: 20rem;
      margin: 0.75rem 0 0;
      padding: 0.8rem;
      border-radius: 6px;
      background: #080808;
      color: #e8dfcf;
      font-size: 12px;
    }
    @media (max-width: 1050px) {
      form { grid-template-columns: 1fr 1fr; }
      .export-module { grid-column: 1 / -1; }
    }
    @media (max-width: 760px) {
      .shell { padding: 0.45rem; }
      .machine { padding: 0.7rem; }
      header, form, .row { grid-template-columns: 1fr; }
      header { display: grid; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="machine">
      <header>
        <div class="brand">
          <div class="mark" aria-hidden="true">
            <span></span><span></span><span></span>
            <span></span><span></span><span></span>
            <span></span><span></span><span></span>
          </div>
          <div>
            <h1>KIT <span class="title-accent">CONVERTER</span></h1>
            <p class="note">Local `.xtd` kit builder for MPC workflows.</p>
          </div>
        </div>
        <div class="guide">
          <p><strong>One pack:</strong> put the exact folder in a roots field.</p>
          <p><strong>Many packs:</strong> put the folder that contains those packs in a parents field.</p>
          <p><strong>NI:</strong> Maschine packs with `Groups` and `.mxgrp` files. <strong>Custom:</strong> regular WAV folders.</p>
        </div>
      </header>
      <main>
        <form id="convert-form">
          <fieldset class="import-module">
            <legend>Import</legend>
            <p class="section-help">Choose Maschine packs, raw sample folders, or both. Enter one path per line.</p>
            <label>NI roots
              <textarea name="niRoots" spellcheck="false" placeholder="/Volumes/RAID1_bak/Shared/Boss Of The Trap Library"></textarea>
            </label>
            <p class="field-help">Exact NI pack folders. Use this when you already know the pack path.</p>
            <label>NI parents
              <textarea name="niParents" spellcheck="false" placeholder="/Volumes/RAID1_bak/Shared"></textarea>
            </label>
            <p class="field-help">Scans direct child folders for `Groups/*.mxgrp` or `Groups/Kits/*.mxgrp`.</p>
            <label>Sample roots
              <textarea name="sampleRoots" spellcheck="false" placeholder="/Volumes/RAID1_bak/Shared/Jonlick sounds"></textarea>
            </label>
            <p class="field-help">Exact WAV sample pack folders.</p>
            <label>Sample parents
              <textarea name="sampleParents" spellcheck="false" placeholder="/Volumes/RAID1_bak/Shared"></textarea>
            </label>
            <p class="field-help">Scans direct child folders that contain WAV files.</p>
          </fieldset>
          <fieldset class="layout-module">
            <legend>Layout</legend>
            <div class="pad-deck" aria-label="32 pad layout preview">
              <div class="pad-grid">
                <div class="pad"><span>29</span>Bank B</div><div class="pad"><span>30</span>Bank B</div><div class="pad"><span>31</span>Bank B</div><div class="pad"><span>32</span>Bank B</div>
                <div class="pad"><span>25</span>Bank B</div><div class="pad"><span>26</span>Bank B</div><div class="pad"><span>27</span>Bank B</div><div class="pad"><span>28</span>Bank B</div>
                <div class="pad"><span>21</span>Bank B</div><div class="pad"><span>22</span>Bank B</div><div class="pad"><span>23</span>Bank B</div><div class="pad"><span>24</span>Bank B</div>
                <div class="pad"><span>17</span>Bank B</div><div class="pad"><span>18</span>Bank B</div><div class="pad"><span>19</span>Bank B</div><div class="pad"><span>20</span>Bank B</div>
                <div class="pad"><span>13</span>Misc</div><div class="pad"><span>14</span>Misc</div><div class="pad"><span>15</span>Misc</div><div class="pad"><span>16</span>Misc</div>
                <div class="pad"><span>9</span>Kick</div><div class="pad"><span>10</span>Snare</div><div class="pad"><span>11</span>Perc</div><div class="pad"><span>12</span>Misc</div>
                <div class="pad"><span>5</span>Kick</div><div class="pad"><span>6</span>Snare</div><div class="pad"><span>7</span>Perc</div><div class="pad"><span>8</span>Perc</div>
                <div class="pad"><span>1</span>Kick</div><div class="pad"><span>2</span>Snare</div><div class="pad"><span>3</span>Perc</div><div class="pad"><span>4</span>Perc</div>
              </div>
            </div>
            <p class="section-help">NI kits and custom kits use a 32-pad limit. Larger kits split into `__2`, `__3`, and later parts.</p>
            <div class="row">
              <label>Custom grouping
                <select name="samplesGrouping">
                  <option value="per-folder">Per folder</option>
                  <option value="single-kit">Single mixed kit</option>
                </select>
              </label>
              <label>Pad profile
                <select name="padProfile">
                  <option value="default">Default</option>
                  <option value="darkchild">Darkchild</option>
                </select>
              </label>
            </div>
            <p class="field-help"><code>Per folder</code> creates separate kits from direct child folders. <code>Darkchild</code> anchors kicks, snares, and percussion for custom kits.</p>
            <div class="row">
              <label>Kit filter
                <input name="kitFilters" spellcheck="false" placeholder="Trap, Darkchild, All Drums">
              </label>
              <label>Limit
                <input name="limit" type="number" min="1" step="1" placeholder="Optional">
              </label>
            </div>
          </fieldset>
          <fieldset class="export-module">
            <legend>Output</legend>
            <div class="toggle-panel">
              <div class="format-row"><input type="checkbox" checked disabled> MPC XTD kits</div>
              <div class="format-row"><input type="checkbox" disabled> XPM export later</div>
            </div>
            <p class="section-help">Output writes `.xtd` files and `_[TrackData]` folders. Existing kits are skipped.</p>
            <label>Output root
              <input name="outputRoot" value="/Volumes/Data/MPC_Converter/web_converted_xtd" spellcheck="false" required>
            </label>
            <label>MPC root
              <input name="mpcRoot" value="/Volumes/Data/MPC_Converter/Cla_hwz4BAFN_x" spellcheck="false">
            </label>
            <p class="field-help">Leave Template XTD blank and the app finds a template inside this MPC root.</p>
            <label>Template XTD
              <input name="templateXtd" spellcheck="false" placeholder="Optional specific .xtd template">
            </label>
            <div class="toggle-panel">
              <div class="checks">
                <label><input name="normalizeAudio" type="checkbox" checked> Normalize audio</label>
                <label><input name="dryRun" type="checkbox"> Dry run</label>
                <label><input name="flatOutput" type="checkbox"> Flat output</label>
              </div>
            </div>
            <p class="field-help">Dry run checks without writing kits. Flat output writes selected sources into one folder.</p>
            <div class="actions">
              <button id="run-button" type="submit">Make Kits</button>
              <span id="inline-status" class="status-sub">Ready</span>
            </div>
          </fieldset>
          <section class="status" id="result-panel" hidden>
            <h2 id="result-title">Result</h2>
            <div id="result-message" class="status-sub"></div>
            <div class="metrics" id="metrics"></div>
            <pre id="result-json"></pre>
          </section>
        </form>
      </main>
    </div>
  </div>
  <script>
    const form = document.getElementById("convert-form");
    const runButton = document.getElementById("run-button");
    const inlineStatus = document.getElementById("inline-status");
    const panel = document.getElementById("result-panel");
    const title = document.getElementById("result-title");
    const message = document.getElementById("result-message");
    const metrics = document.getElementById("metrics");
    const resultJson = document.getElementById("result-json");

    function lines(value) {
      return value.split(/\\r?\\n/).map((item) => item.trim()).filter(Boolean);
    }
    function kitTerms(value) {
      return value.split(/[\\n,]/).map((item) => item.trim()).filter(Boolean);
    }
    function metric(label, value) {
      return `<div class="metric"><strong>${value}</strong>${label}</div>`;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const payload = {
        niRoots: lines(data.get("niRoots") || ""),
        niParents: lines(data.get("niParents") || ""),
        sampleRoots: lines(data.get("sampleRoots") || ""),
        sampleParents: lines(data.get("sampleParents") || ""),
        outputRoot: (data.get("outputRoot") || "").trim(),
        mpcRoot: (data.get("mpcRoot") || "").trim(),
        templateXtd: (data.get("templateXtd") || "").trim(),
        samplesGrouping: data.get("samplesGrouping"),
        padProfile: data.get("padProfile"),
        kitFilters: kitTerms(data.get("kitFilters") || ""),
        limit: data.get("limit") ? Number(data.get("limit")) : null,
        normalizeAudio: Boolean(data.get("normalizeAudio")),
        dryRun: Boolean(data.get("dryRun")),
        flatOutput: Boolean(data.get("flatOutput")),
      };
      runButton.disabled = true;
      inlineStatus.textContent = "Running conversion...";
      panel.hidden = true;
      try {
        const response = await fetch("/api/convert", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        const result = await response.json();
        panel.hidden = false;
        title.textContent = result.ok ? "Conversion Complete" : "Conversion Failed";
        title.className = result.ok ? "ok" : "error";
        message.textContent = result.message || "";
        if (result.ok) {
          metrics.innerHTML = [
            metric("Sources", result.sourceCount),
            metric("Scanned", result.totalScannedKits),
            metric("Converted", result.totalConvertedKits),
            metric("Warnings", result.totalWarnings),
          ].join("");
        } else {
          metrics.innerHTML = "";
        }
        resultJson.textContent = JSON.stringify(result, null, 2);
        inlineStatus.textContent = result.ok ? "Complete" : "Failed";
      } catch (error) {
        panel.hidden = false;
        title.textContent = "Conversion Failed";
        title.className = "error";
        message.textContent = String(error);
        metrics.innerHTML = "";
        resultJson.textContent = "";
        inlineStatus.textContent = "Failed";
      } finally {
        runButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


class ConverterRequestHandler(BaseHTTPRequestHandler):
    server_version = "NIMPCConverter/0.1"

    def do_GET(self) -> None:
        request_path = urlparse(self.path).path
        if request_path in ("/", "/index.html"):
            self._send_file(WEB_ROOT / "index.html")
            return
        if request_path.startswith("/static/"):
            self._send_static_file(request_path)
            return
        if request_path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        request_path = urlparse(self.path).path
        if request_path in ("/", "/index.html"):
            self._send_file(WEB_ROOT / "index.html", include_body=False)
            return
        if request_path.startswith("/static/"):
            self._send_static_file(request_path, include_body=False)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/convert":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            result = run_conversion_from_payload(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(result, status=status)
        except Exception as exc:  # Keep the browser from seeing a dropped connection.
            self._send_json(
                {"ok": False, "message": f"{type(exc).__name__}: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Request body must be a JSON object.")
        return parsed

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, request_path: str, include_body: bool = True) -> None:
        rel = unquote(request_path.removeprefix("/static/"))
        if rel.startswith("/") or ".." in Path(rel).parts:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        self._send_file(STATIC_ROOT / rel, include_body=include_body)

    def _send_file(self, path: Path, include_body: bool = True) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)


def run_conversion_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    output_root = _required_path(payload, "outputRoot")
    template_xtd = _optional_path(payload, "templateXtd")
    mpc_root = _optional_path(payload, "mpcRoot")
    samples_grouping = str(payload.get("samplesGrouping") or "per-folder")
    pad_profile = str(payload.get("padProfile") or PAD_PROFILE_DEFAULT)
    custom_pad_map = _custom_pad_map(payload.get("customPadMap"), pad_limit=32)
    kit_filters = _optional_str_list(payload.get("kitFilters"))
    limit = _optional_positive_int(payload.get("limit"))
    normalize_audio = bool(payload.get("normalizeAudio", True))
    dry_run = bool(payload.get("dryRun", False))
    flat_output = bool(payload.get("flatOutput", False))

    if samples_grouping not in {"per-folder", "single-kit"}:
        return _error(f"Unsupported custom grouping: {samples_grouping}")
    if pad_profile not in {PAD_PROFILE_DEFAULT, PAD_PROFILE_DARKCHILD, PAD_PROFILE_CUSTOM}:
        return _error(f"Unsupported pad profile: {pad_profile}")

    sources = _resolve_sources(
        ni_roots=_path_list(payload.get("niRoots")),
        ni_parents=_path_list(payload.get("niParents")),
        sample_roots=_path_list(payload.get("sampleRoots")),
        sample_parents=_path_list(payload.get("sampleParents")),
    )
    if not sources:
        return _error("No valid sources found.")

    resolved_template = _resolve_template_xtd(template_xtd, mpc_root)
    if resolved_template is None:
        return _error("Could not resolve template .xtd. Provide Template XTD or MPC root.")

    if len(sources) == 1:
        source_type, source_root = sources[0]
        report = _convert_for_source(
            source_type=source_type,
            source_root=source_root,
            output_root=output_root,
            template_xtd=resolved_template,
            samples_grouping=samples_grouping,
            pad_profile=pad_profile,
            custom_pad_map=custom_pad_map,
            kit_filters=kit_filters,
            limit=limit,
            normalize_audio=normalize_audio,
            dry_run=dry_run,
        )
        report_path = output_root / "conversion-report.json"
        write_report(report, report_path)
        return _single_report_response(report, report_path, resolved_template)

    return _multi_report_response(
        sources=sources,
        output_root=output_root,
        template_xtd=resolved_template,
        samples_grouping=samples_grouping,
        pad_profile=pad_profile,
        custom_pad_map=custom_pad_map,
        kit_filters=kit_filters,
        limit=limit,
        normalize_audio=normalize_audio,
        dry_run=dry_run,
        flat_output=flat_output,
    )


def _multi_report_response(
    sources: list[tuple[str, Path]],
    output_root: Path,
    template_xtd: Path,
    samples_grouping: str,
    pad_profile: str,
    custom_pad_map: dict[str, list[int]] | None,
    kit_filters: list[str] | None,
    limit: int | None,
    normalize_audio: bool,
    dry_run: bool,
    flat_output: bool,
) -> dict[str, Any]:
    created_subdirs: set[str] = set()
    source_reports: list[dict[str, Any]] = []
    total_scanned = 0
    total_converted = 0
    total_skipped = 0
    total_warnings = 0

    for source_type, source_root in sources:
        if flat_output:
            output_dir = output_root
        else:
            base_subdir = _safe_subdir_name(f"{source_type}_{source_root.name}")
            subdir = _unique_subdir_name(base_subdir, created_subdirs)
            created_subdirs.add(subdir)
            output_dir = output_root / subdir

        report = _convert_for_source(
            source_type=source_type,
            source_root=source_root,
            output_root=output_dir,
            template_xtd=template_xtd,
            samples_grouping=samples_grouping,
            pad_profile=pad_profile,
            custom_pad_map=custom_pad_map,
            kit_filters=kit_filters,
            limit=limit,
            normalize_audio=normalize_audio,
            dry_run=dry_run,
        )
        report_path = output_dir / "conversion-report.json"
        write_report(report, report_path)
        total_scanned += report.scanned_kits
        total_converted += report.converted_kits
        total_skipped += report.skipped_kits
        total_warnings += len(report.warnings)
        source_reports.append(
            {
                "sourceType": source_type,
                "sourceRoot": str(source_root),
                "outputRoot": str(output_dir),
                "report": str(report_path),
                "scannedKits": report.scanned_kits,
                "convertedKits": report.converted_kits,
                "skippedKits": report.skipped_kits,
                "warningCount": len(report.warnings),
            }
        )

    aggregate = {
        "template_xtd": str(template_xtd),
        "source_count": len(sources),
        "total_scanned_kits": total_scanned,
        "total_converted_kits": total_converted,
        "total_skipped_kits": total_skipped,
        "total_warnings": total_warnings,
        "sources": source_reports,
    }
    aggregate_path = output_root / "multi-pack-report.json"
    aggregate_path.parent.mkdir(parents=True, exist_ok=True)
    aggregate_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "message": f"Processed {len(sources)} sources.",
        "sourceCount": len(sources),
        "totalScannedKits": total_scanned,
        "totalConvertedKits": total_converted,
        "totalSkippedKits": total_skipped,
        "totalWarnings": total_warnings,
        "templateXtd": str(template_xtd),
        "report": str(aggregate_path),
        "sources": source_reports,
    }


def _single_report_response(report: Any, report_path: Path, template_xtd: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "message": f"Processed {report.source_root}.",
        "sourceCount": 1,
        "totalScannedKits": report.scanned_kits,
        "totalConvertedKits": report.converted_kits,
        "totalSkippedKits": report.skipped_kits,
        "totalWarnings": len(report.warnings),
        "templateXtd": str(template_xtd),
        "report": str(report_path),
        "sources": [
            {
                "sourceType": report.source_type,
                "sourceRoot": report.source_root,
                "outputRoot": report.output_root,
                "report": str(report_path),
                "scannedKits": report.scanned_kits,
                "convertedKits": report.converted_kits,
                "skippedKits": report.skipped_kits,
                "warningCount": len(report.warnings),
            }
        ],
    }


def _custom_pad_map(value: Any, pad_limit: int) -> dict[str, list[int]] | None:
    if not isinstance(value, dict):
        return None

    allowed_roles = ("kick", "snare", "perc", "clap", "hat_closed", "hat_open", "tom", "fx", "other")
    converted: dict[str, list[int]] = {}
    used_pads: set[int] = set()

    for role in allowed_roles:
        raw_slots = value.get(role)
        if not isinstance(raw_slots, list):
            continue
        slots: list[int] = []
        for raw_slot in raw_slots:
            try:
                one_based = int(raw_slot)
            except (TypeError, ValueError):
                continue
            if one_based < 1 or one_based > pad_limit:
                continue
            zero_based = one_based - 1
            if zero_based in used_pads:
                continue
            used_pads.add(zero_based)
            slots.append(zero_based)
        if slots:
            converted[role] = slots

    return converted or None


def _path_list(value: Any) -> list[Path]:
    if not isinstance(value, list):
        return []
    return [Path(str(item).strip()) for item in value if str(item).strip()]


def _optional_str_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or None


def _required_path(payload: dict[str, Any], key: str) -> Path:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required field: {key}")
    return Path(value)


def _optional_path(payload: dict[str, Any], key: str) -> Path | None:
    value = str(payload.get(key) or "").strip()
    return Path(value) if value else None


def _optional_positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError("Limit must be greater than zero.")
    return parsed


def _error(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "message": message,
        "sourceCount": 0,
        "totalScannedKits": 0,
        "totalConvertedKits": 0,
        "totalSkippedKits": 0,
        "totalWarnings": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local NI to MPC Converter web app.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind. Default: {DEFAULT_HOST}")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help=f"Port to bind. Default: {DEFAULT_PORT}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), ConverterRequestHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"NI to MPC Converter web app running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web app.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
