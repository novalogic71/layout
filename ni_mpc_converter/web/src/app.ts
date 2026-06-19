type SamplesGrouping = "per-folder" | "single-kit";
type PadProfile = "default" | "darkchild" | "custom";
type CustomRole = keyof CustomPadMap;

interface CustomPadMap {
  kick: number[];
  snare: number[];
  perc: number[];
  clap: number[];
}

interface ConvertPayload {
  niRoots: string[];
  niParents: string[];
  sampleRoots: string[];
  sampleParents: string[];
  outputRoot: string;
  mpcRoot: string;
  templateXtd: string;
  samplesGrouping: SamplesGrouping;
  padProfile: PadProfile;
  customPadMap: CustomPadMap;
  kitFilters: string[];
  limit: number | null;
  normalizeAudio: boolean;
  dryRun: boolean;
  flatOutput: boolean;
}

interface SourceResult {
  sourceType: string;
  sourceRoot: string;
  outputRoot: string;
  report: string;
  scannedKits: number;
  convertedKits: number;
  skippedKits: number;
  warningCount: number;
}

interface ConvertResult {
  ok: boolean;
  message: string;
  sourceCount: number;
  totalScannedKits: number;
  totalConvertedKits: number;
  totalSkippedKits: number;
  totalWarnings: number;
  templateXtd?: string;
  report?: string;
  sources?: SourceResult[];
}

interface QueueItem {
  type: string;
  path: string;
}

const form = requireElement<HTMLFormElement>("convert-form");
const runButton = requireElement<HTMLButtonElement>("run-button");
const inlineStatus = requireElement<HTMLElement>("inline-status");
const panel = requireElement<HTMLElement>("result-panel");
const title = requireElement<HTMLElement>("result-title");
const message = requireElement<HTMLElement>("result-message");
const metrics = requireElement<HTMLElement>("metrics");
const resultJson = requireElement<HTMLElement>("result-json");
const queueCount = requireElement<HTMLElement>("queue-count");
const modeLabel = requireElement<HTMLElement>("mode-label");
const profileLabel = requireElement<HTMLElement>("profile-label");
const queueList = requireElement<HTMLElement>("queue-list");
const sourceResults = requireElement<HTMLElement>("source-results");
const serverState = requireElement<HTMLElement>("server-state");
const customMapPanel = requireElement<HTMLElement>("custom-map");
const profileNote = requireElement<HTMLElement>("profile-note");
const padSelector = requireElement<HTMLElement>("pad-selector");
const padSelectionReadout = requireElement<HTMLElement>("pad-selection-readout");
const roleTabs = Array.from(document.querySelectorAll<HTMLButtonElement>(".role-tab"));
const customPadInputs: Record<CustomRole, HTMLInputElement> = {
  kick: requireNamedInput("customKickPads"),
  snare: requireNamedInput("customSnarePads"),
  perc: requireNamedInput("customPercPads"),
  clap: requireNamedInput("customClapPads"),
};
const roleLabels: Record<CustomRole, string> = {
  kick: "Kick",
  snare: "Snare",
  perc: "Perc",
  clap: "Clap",
};
const roleClassNames: Record<CustomRole, string> = {
  kick: "role-kick",
  snare: "role-snare",
  perc: "role-perc",
  clap: "role-clap",
};
const customSelections: CustomPadMap = {
  kick: [1, 5, 9],
  snare: [2, 6, 10],
  perc: [3, 4, 7, 8],
  clap: [13, 14, 15, 16],
};
let activeRole: CustomRole = "kick";

function requireElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: ${id}`);
  }
  return element as T;
}

function requireNamedInput(name: string): HTMLInputElement {
  const element = form.elements.namedItem(name);
  if (!(element instanceof HTMLInputElement)) {
    throw new Error(`Missing input: ${name}`);
  }
  return element;
}

function lines(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function terms(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function padList(value: FormDataEntryValue | null): number[] {
  const seen = new Set<number>();
  return String(value ?? "")
    .split(/[\s,]+/)
    .map((item) => Number(item.trim()))
    .filter((pad) => Number.isInteger(pad) && pad >= 1 && pad <= 32)
    .filter((pad) => {
      if (seen.has(pad)) {
        return false;
      }
      seen.add(pad);
      return true;
    });
}

function getString(data: FormData, name: string): string {
  return String(data.get(name) ?? "").trim();
}

function getPayload(): ConvertPayload {
  const data = new FormData(form);
  const rawGrouping = getString(data, "samplesGrouping") || "per-folder";
  const rawProfile = getString(data, "padProfile") || "default";
  const padProfile: PadProfile =
    rawProfile === "darkchild" || rawProfile === "custom" ? rawProfile : "default";
  return {
    niRoots: lines(data.get("niRoots")),
    niParents: lines(data.get("niParents")),
    sampleRoots: lines(data.get("sampleRoots")),
    sampleParents: lines(data.get("sampleParents")),
    outputRoot: getString(data, "outputRoot"),
    mpcRoot: getString(data, "mpcRoot"),
    templateXtd: getString(data, "templateXtd"),
    samplesGrouping: rawGrouping === "single-kit" ? "single-kit" : "per-folder",
    padProfile,
    customPadMap: {
      kick: padList(data.get("customKickPads")),
      snare: padList(data.get("customSnarePads")),
      perc: padList(data.get("customPercPads")),
      clap: padList(data.get("customClapPads")),
    },
    kitFilters: terms(data.get("kitFilters")),
    limit: getString(data, "limit") ? Number(getString(data, "limit")) : null,
    normalizeAudio: data.has("normalizeAudio"),
    dryRun: data.has("dryRun"),
    flatOutput: data.has("flatOutput"),
  };
}

function queuedSources(payload: ConvertPayload): QueueItem[] {
  return [
    ...payload.niRoots.map((path) => ({type: "NI root", path})),
    ...payload.niParents.map((path) => ({type: "NI parent", path})),
    ...payload.sampleRoots.map((path) => ({type: "Sample root", path})),
    ...payload.sampleParents.map((path) => ({type: "Sample parent", path})),
  ];
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderQueue(): void {
  const payload = getPayload();
  const items = queuedSources(payload);
  queueCount.textContent = String(items.length);
  modeLabel.textContent = payload.samplesGrouping === "single-kit" ? "Single kit" : "Per folder";
  profileLabel.textContent =
    payload.padProfile === "darkchild" ? "Darkchild" : payload.padProfile === "custom" ? "Custom" : "Default";
  customMapPanel.classList.toggle("is-visible", payload.padProfile === "custom");
  if (payload.padProfile === "custom") {
    profileNote.innerHTML =
      "<strong>Custom profile:</strong> uses your pad anchors below first, then fills remaining pads deterministically.";
  } else if (payload.padProfile === "darkchild") {
    profileNote.innerHTML =
      "<strong>Darkchild profile:</strong> kicks on pads 01/05/09, snares on 02/06/10, percussion on 03/04/07/08, then deterministic fill.";
  } else {
    profileNote.innerHTML =
      "<strong>Default profile:</strong> uses the converter's role priority and balanced fill behavior.";
  }

  if (items.length === 0) {
    queueList.innerHTML = "<p>No sources queued.</p>";
    return;
  }

  queueList.innerHTML = items
    .map(
      (item) => `
        <div class="queue-item">
          <strong>${escapeHtml(item.type)}</strong>
          <span>${escapeHtml(item.path)}</span>
        </div>
      `,
    )
    .join("");
}

function roleForPad(pad: number): CustomRole | null {
  for (const role of Object.keys(customSelections) as CustomRole[]) {
    if (customSelections[role].includes(pad)) {
      return role;
    }
  }
  return null;
}

function setActiveRole(role: CustomRole): void {
  activeRole = role;
  for (const tab of roleTabs) {
    tab.classList.toggle("is-active", tab.dataset.role === role);
  }
}

function assignPad(pad: number, role: CustomRole | "clear"): void {
  for (const currentRole of Object.keys(customSelections) as CustomRole[]) {
    customSelections[currentRole] = customSelections[currentRole].filter((item) => item !== pad);
  }
  if (role !== "clear") {
    customSelections[role] = [...customSelections[role], pad].sort((a, b) => a - b);
  }
  syncCustomPadInputs();
  renderPadSelector();
  renderQueue();
}

function syncCustomPadInputs(): void {
  for (const role of Object.keys(customSelections) as CustomRole[]) {
    customPadInputs[role].value = customSelections[role].join(",");
  }
}

function renderPadSelector(): void {
  const pads = Array.from({length: 32}, (_, index) => 32 - index);
  padSelector.innerHTML = pads
    .map((pad) => {
      const role = roleForPad(pad);
      const roleClass = role ? roleClassNames[role] : "";
      const label = role ? roleLabels[role] : "";
      return `
        <button class="select-pad ${roleClass}" type="button" data-pad="${pad}">
          ${String(pad).padStart(2, "0")}
          <small>${label}</small>
        </button>
      `;
    })
    .join("");
  padSelectionReadout.innerHTML = (Object.keys(customSelections) as CustomRole[])
    .map((role) => `<span><strong>${roleLabels[role]}:</strong> ${customSelections[role].join(", ") || "-"}</span>`)
    .join("");
}

function metric(label: string, value: number): string {
  return `<div class="metric"><strong>${value}</strong>${escapeHtml(label)}</div>`;
}

function renderSourceResults(result: ConvertResult): void {
  const sources = result.sources ?? [];
  if (sources.length === 0) {
    sourceResults.innerHTML = "";
    return;
  }

  sourceResults.innerHTML = sources
    .map(
      (source) => `
        <div class="source-result">
          <strong>${escapeHtml(source.sourceType)}: ${escapeHtml(source.sourceRoot)}</strong>
          <span>scanned=${source.scannedKits} converted=${source.convertedKits} skipped=${source.skippedKits} warnings=${source.warningCount}</span>
          <span>${escapeHtml(source.report)}</span>
        </div>
      `,
    )
    .join("");
}

function renderResult(result: ConvertResult): void {
  panel.hidden = false;
  title.textContent = result.ok ? "Batch Complete" : "Batch Failed";
  title.className = result.ok ? "ok" : "error";
  message.textContent = result.message || "";
  serverState.textContent = result.ok ? "Complete" : "Failed";

  if (result.ok) {
    metrics.innerHTML = [
      metric("sources", result.sourceCount),
      metric("scanned", result.totalScannedKits),
      metric("converted", result.totalConvertedKits),
      metric("warnings", result.totalWarnings),
    ].join("");
  } else {
    metrics.innerHTML = "";
  }

  renderSourceResults(result);
  resultJson.textContent = JSON.stringify(result, null, 2);
}

async function runConversion(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const payload = getPayload();
  runButton.disabled = true;
  inlineStatus.textContent = "Running batch...";
  serverState.textContent = "Running";
  panel.hidden = true;

  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const result = (await response.json()) as ConvertResult;
    renderResult(result);
    inlineStatus.textContent = result.ok ? "Complete" : "Failed";
  } catch (error) {
    const result: ConvertResult = {
      ok: false,
      message: String(error),
      sourceCount: 0,
      totalScannedKits: 0,
      totalConvertedKits: 0,
      totalSkippedKits: 0,
      totalWarnings: 0,
    };
    renderResult(result);
    inlineStatus.textContent = "Failed";
  } finally {
    runButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  void runConversion(event as SubmitEvent);
});

roleTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const role = tab.dataset.role;
    if (role === "clear") {
      padSelector.classList.add("is-clearing");
      for (const currentTab of roleTabs) {
        currentTab.classList.toggle("is-active", currentTab === tab);
      }
      return;
    }
    if (role === "kick" || role === "snare" || role === "perc" || role === "clap") {
      padSelector.classList.remove("is-clearing");
      setActiveRole(role);
    }
  });
});

padSelector.addEventListener("click", (event) => {
  const target = event.target instanceof HTMLElement ? event.target.closest<HTMLButtonElement>(".select-pad") : null;
  if (!target) {
    return;
  }
  const pad = Number(target.dataset.pad);
  if (!Number.isInteger(pad)) {
    return;
  }
  assignPad(pad, padSelector.classList.contains("is-clearing") ? "clear" : activeRole);
});

form.addEventListener("input", renderQueue);
form.addEventListener("change", renderQueue);
syncCustomPadInputs();
renderPadSelector();
renderQueue();
