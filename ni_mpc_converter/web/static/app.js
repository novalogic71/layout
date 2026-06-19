const form = requireElement("convert-form");
const runButton = requireElement("run-button");
const inlineStatus = requireElement("inline-status");
const panel = requireElement("result-panel");
const title = requireElement("result-title");
const message = requireElement("result-message");
const metrics = requireElement("metrics");
const resultJson = requireElement("result-json");
const queueCount = requireElement("queue-count");
const modeLabel = requireElement("mode-label");
const profileLabel = requireElement("profile-label");
const queueList = requireElement("queue-list");
const sourceResults = requireElement("source-results");
const serverState = requireElement("server-state");
const customMapPanel = requireElement("custom-map");
const profileNote = requireElement("profile-note");
const padSelector = requireElement("pad-selector");
const padSelectionReadout = requireElement("pad-selection-readout");
const roleTabs = Array.from(document.querySelectorAll(".role-tab"));
const customPadInputs = {
    kick: requireNamedInput("customKickPads"),
    snare: requireNamedInput("customSnarePads"),
    perc: requireNamedInput("customPercPads"),
    clap: requireNamedInput("customClapPads"),
};
const roleLabels = {
    kick: "Kick",
    snare: "Snare",
    perc: "Perc",
    clap: "Clap",
};
const roleClassNames = {
    kick: "role-kick",
    snare: "role-snare",
    perc: "role-perc",
    clap: "role-clap",
};
const customSelections = {
    kick: [1, 5, 9],
    snare: [2, 6, 10],
    perc: [3, 4, 7, 8],
    clap: [13, 14, 15, 16],
};
let activeRole = "kick";
function requireElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        throw new Error(`Missing element: ${id}`);
    }
    return element;
}
function requireNamedInput(name) {
    const element = form.elements.namedItem(name);
    if (!(element instanceof HTMLInputElement)) {
        throw new Error(`Missing input: ${name}`);
    }
    return element;
}
function lines(value) {
    return String(value ?? "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean);
}
function terms(value) {
    return String(value ?? "")
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean);
}
function padList(value) {
    const seen = new Set();
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
function getString(data, name) {
    return String(data.get(name) ?? "").trim();
}
function getPayload() {
    const data = new FormData(form);
    const rawGrouping = getString(data, "samplesGrouping") || "per-folder";
    const rawProfile = getString(data, "padProfile") || "default";
    const padProfile = rawProfile === "darkchild" || rawProfile === "custom" ? rawProfile : "default";
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
function queuedSources(payload) {
    return [
        ...payload.niRoots.map((path) => ({ type: "NI root", path })),
        ...payload.niParents.map((path) => ({ type: "NI parent", path })),
        ...payload.sampleRoots.map((path) => ({ type: "Sample root", path })),
        ...payload.sampleParents.map((path) => ({ type: "Sample parent", path })),
    ];
}
function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}
function renderQueue() {
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
    }
    else if (payload.padProfile === "darkchild") {
        profileNote.innerHTML =
            "<strong>Darkchild profile:</strong> kicks on pads 01/05/09, snares on 02/06/10, percussion on 03/04/07/08, then deterministic fill.";
    }
    else {
        profileNote.innerHTML =
            "<strong>Default profile:</strong> uses the converter's role priority and balanced fill behavior.";
    }
    if (items.length === 0) {
        queueList.innerHTML = "<p>No sources queued.</p>";
        return;
    }
    queueList.innerHTML = items
        .map((item) => `
        <div class="queue-item">
          <strong>${escapeHtml(item.type)}</strong>
          <span>${escapeHtml(item.path)}</span>
        </div>
      `)
        .join("");
}
function roleForPad(pad) {
    for (const role of Object.keys(customSelections)) {
        if (customSelections[role].includes(pad)) {
            return role;
        }
    }
    return null;
}
function setActiveRole(role) {
    activeRole = role;
    for (const tab of roleTabs) {
        tab.classList.toggle("is-active", tab.dataset.role === role);
    }
}
function assignPad(pad, role) {
    for (const currentRole of Object.keys(customSelections)) {
        customSelections[currentRole] = customSelections[currentRole].filter((item) => item !== pad);
    }
    if (role !== "clear") {
        customSelections[role] = [...customSelections[role], pad].sort((a, b) => a - b);
    }
    syncCustomPadInputs();
    renderPadSelector();
    renderQueue();
}
function syncCustomPadInputs() {
    for (const role of Object.keys(customSelections)) {
        customPadInputs[role].value = customSelections[role].join(",");
    }
}
function renderPadSelector() {
    const pads = Array.from({ length: 32 }, (_, index) => 32 - index);
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
    padSelectionReadout.innerHTML = Object.keys(customSelections)
        .map((role) => `<span><strong>${roleLabels[role]}:</strong> ${customSelections[role].join(", ") || "-"}</span>`)
        .join("");
}
function metric(label, value) {
    return `<div class="metric"><strong>${value}</strong>${escapeHtml(label)}</div>`;
}
function renderSourceResults(result) {
    const sources = result.sources ?? [];
    if (sources.length === 0) {
        sourceResults.innerHTML = "";
        return;
    }
    sourceResults.innerHTML = sources
        .map((source) => `
        <div class="source-result">
          <strong>${escapeHtml(source.sourceType)}: ${escapeHtml(source.sourceRoot)}</strong>
          <span>scanned=${source.scannedKits} converted=${source.convertedKits} skipped=${source.skippedKits} warnings=${source.warningCount}</span>
          <span>${escapeHtml(source.report)}</span>
        </div>
      `)
        .join("");
}
function renderResult(result) {
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
    }
    else {
        metrics.innerHTML = "";
    }
    renderSourceResults(result);
    resultJson.textContent = JSON.stringify(result, null, 2);
}
async function runConversion(event) {
    event.preventDefault();
    const payload = getPayload();
    runButton.disabled = true;
    inlineStatus.textContent = "Running batch...";
    serverState.textContent = "Running";
    panel.hidden = true;
    try {
        const response = await fetch("/api/convert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = (await response.json());
        renderResult(result);
        inlineStatus.textContent = result.ok ? "Complete" : "Failed";
    }
    catch (error) {
        const result = {
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
    }
    finally {
        runButton.disabled = false;
    }
}
form.addEventListener("submit", (event) => {
    void runConversion(event);
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
    const target = event.target instanceof HTMLElement ? event.target.closest(".select-pad") : null;
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
