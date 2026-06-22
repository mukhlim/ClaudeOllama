document.addEventListener("DOMContentLoaded", () => {
    waitForPywebview(() => {
        loadVersion();
        loadConfig();
        loadWorkspaces();
        checkStatus();
    });
});

async function loadVersion() {
    try {
        const version = await callPy("get_version");
        const el = document.querySelector("#app-version");
        if (el) el.textContent = "v" + version;
    } catch (e) {
        // Versi opsional, jangan ganggu fungsi lain
    }
}

const FIELD_IDS = {
    api_key: "api-key",
    base_url: "base-url",
    model_default: "model-default",
    model_opus: "model-opus",
    model_sonnet: "model-sonnet",
    model_haiku: "model-haiku",
    model_subagent: "model-subagent",
    max_context_tokens: "max-context",
    max_output_tokens: "max-output",
    terminal: "terminal",
};

function waitForPywebview(callback, maxAttempts = 50) {
    let attempts = 0;
    const interval = setInterval(() => {
        attempts++;
        if (window.pywebview && window.pywebview.api) {
            clearInterval(interval);
            callback();
        } else if (attempts >= maxAttempts) {
            clearInterval(interval);
            log("pywebview API failed to load. Functionality limited.");
        }
    }, 100);
}

async function callPy(name, ...args) {
    if (!window.pywebview || !window.pywebview.api) {
        throw new Error("pywebview API not ready. Are you running inside the desktop app?");
    }
    const fn = window.pywebview.api[name];
    if (typeof fn !== "function") {
        throw new Error(`API function '${name}' not found.`);
    }
    return await fn(...args);
}

function getInputValues() {
    const data = {};
    for (const [key, id] of Object.entries(FIELD_IDS)) {
        const el = document.querySelector(`#${id}`);
        data[key] = el ? el.value.trim() : "";
    }
    return data;
}

function setInputValues(cfg) {
    for (const [key, id] of Object.entries(FIELD_IDS)) {
        const el = document.querySelector(`#${id}`);
        if (el && cfg[key] !== undefined) {
            el.value = cfg[key];
        }
    }
}

function updateKeyHint(apiKey) {
    const hint = document.querySelector("#key-hint");
    if (apiKey && apiKey.length > 8) {
        const masked = apiKey.slice(0, 4) + "..." + apiKey.slice(-4);
        hint.textContent = `(loaded: ${masked}, ${apiKey.length} chars)`;
    } else {
        hint.textContent = apiKey ? "(too short)" : "(not set)";
    }
}

async function loadConfig() {
    try {
        const cfg = await callPy("load_config");
        setInputValues(cfg);
        updateKeyHint(cfg.api_key || "");
        if (cfg.api_key && cfg.api_key.length > 8) {
            log(`Config loaded. API key: ${cfg.api_key.slice(0, 4)}...${cfg.api_key.slice(-4)}`);
        } else {
            log("Config loaded, but API key is empty or too short.");
        }
    } catch (e) {
        log("Config load error: " + e.message);
        document.querySelector("#key-hint").textContent = "(error loading config)";
    }
}

async function saveConfig() {
    const data = getInputValues();
    if (!data.api_key) {
        alert("API Key tidak boleh kosong!");
        return;
    }
    try {
        const result = await callPy("save_config", data);
        updateKeyHint(data.api_key);
        log(result);
    } catch (e) {
        log("Error saving config: " + e.message);
    }
}

async function launchClaude() {
    log("Launching Claude Code in current workspace...");
    try {
        // Kirimkan pilihan terminal saat ini dari dropdown (#terminal)
        // agar backend tidak selalu membaca config.json (yang mungkin stale)
        // dan user tidak perlu menekan "Save Config" dulu.
        const termEl = document.querySelector("#terminal");
        const terminalOverride = termEl ? termEl.value.trim().toLowerCase() : "";
        const result = await callPy("launch_claude", terminalOverride);
        log(result);
        // Sinkronkan UI workspace (cwd baru masuk ke recent)
        await loadWorkspaces();
    } catch (e) {
        log("Error: " + e.message);
    }
}

async function enableGlobal() {
    log("Setting global environment variables...");
    try {
        const result = await callPy("enable_global");
        log(result);
        checkStatus();
    } catch (e) {
        log("Error: " + e.message);
    }
}

async function disableGlobal() {
    log("Removing global environment variables...");
    try {
        const result = await callPy("disable_global");
        log(result);
        checkStatus();
    } catch (e) {
        log("Error: " + e.message);
    }
}

async function checkStatus() {
    try {
        const status = await callPy("check_env");
        const tbody = document.querySelector("#env-table tbody");
        tbody.innerHTML = "";
        for (const item of status) {
            const row = document.createElement("tr");
            const keyCell = document.createElement("td");
            const valCell = document.createElement("td");
            keyCell.textContent = item.key;
            valCell.textContent = item.value;
            valCell.className = item.set ? "set" : "unset";
            row.append(keyCell, valCell);
            tbody.append(row);
        }
    } catch (e) {
        log("Failed to check env status: " + e.message);
    }
}

async function skipOnboarding() {
    try {
        const result = await callPy("skip_onboarding");
        log(result);
    } catch (e) {
        log("Error: " + e.message);
    }
}

function log(msg) {
    const box = document.querySelector("#log");
    const time = new Date().toLocaleTimeString();
    box.value += `[${time}] ${msg}\n`;
    box.scrollTop = box.scrollHeight;
}

function toggleKeyVisibility() {
    const input = document.querySelector("#api-key");
    const btn = document.querySelector("#eye-btn");
    const icon = document.querySelector("#eye-icon");
    if (input.type === "password") {
        input.type = "text";
        btn.title = "Hide API key";
        // Eye-off icon
        icon.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
            <line x1="1" y1="1" x2="23" y2="23"></line>
        `;
    } else {
        input.type = "password";
        btn.title = "Show API key";
        // Eye icon
        icon.innerHTML = `
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>
        `;
    }
}

function switchTab(tabId) {
    // Update buttons
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.tab === tabId);
    });

    // Update panels
    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === "tab-" + tabId);
    });
}

function clearLog() {
    document.querySelector("#log").value = "";
}

// ------------------------------------------------------------------
// Workspace functions
// ------------------------------------------------------------------
let currentWorkspaces = { current: "", recent: [] };

async function loadWorkspaces() {
    try {
        const data = await callPy("load_workspaces");
        currentWorkspaces = data;
        document.querySelector("#workspace-path").value = data.current || "";
        renderWorkspaceList(data);
        log("Workspaces loaded.");
    } catch (e) {
        log("Workspace load error: " + e.message);
    }
}

function renderWorkspaceList(data) {
    const list = document.querySelector("#workspace-list");
    list.innerHTML = "";
    const current = data.current || "";
    const recent = data.recent || [];

    if (recent.length === 0) {
        const empty = document.createElement("li");
        empty.textContent = "No recent workspaces.";
        empty.style.color = "var(--text-muted)";
        empty.style.fontStyle = "italic";
        list.append(empty);
        return;
    }

    for (const path of recent) {
        const li = document.createElement("li");
        if (path === current) {
            li.classList.add("current");
        }

        const pathSpan = document.createElement("span");
        pathSpan.className = "path";
        pathSpan.textContent = path;
        pathSpan.title = "Click to set as current";
        pathSpan.onclick = () => {
            document.querySelector("#workspace-path").value = path;
            setCurrentWorkspace(path);
        };

        const actions = document.createElement("div");
        actions.className = "actions";

        const warpBtn = document.createElement("button");
        warpBtn.textContent = "Warp";
        warpBtn.onclick = () => openWarp(path);

        const removeBtn = document.createElement("button");
        removeBtn.textContent = "Remove";
        removeBtn.className = "danger";
        removeBtn.onclick = () => removeWorkspace(path);

        actions.append(warpBtn, removeBtn);
        li.append(pathSpan, actions);
        list.append(li);
    }
}

async function setCurrentWorkspace(path) {
    if (!path) return;
    try {
        const result = await callPy("set_current_workspace", path);
        if (result.ok) {
            currentWorkspaces = result.data;
            document.querySelector("#workspace-path").value = result.data.current || "";
            renderWorkspaceList(result.data);
            log("Current workspace set to: " + path);
        } else {
            log("Set current workspace failed: " + (result.error || "unknown"));
        }
    } catch (e) {
        log("Error setting current workspace: " + e.message);
    }
}

function setCurrentWorkspaceFromInput() {
    const path = document.querySelector("#workspace-path").value.trim();
    if (!path) {
        alert("Workspace path cannot be empty.");
        return;
    }
    setCurrentWorkspace(path);
}

async function browseWorkspaceFolder() {
    try {
        const result = await callPy("browse_folder");
        if (result.ok && result.path) {
            document.querySelector("#workspace-path").value = result.path;
            await setCurrentWorkspace(result.path);
            await loadWorkspaces();  // pastikan UI sinkron dengan file
        } else if (result.error) {
            log("Browse folder: " + result.error);
        }
    } catch (e) {
        log("Error browsing folder: " + e.message);
    }
}

async function addWorkspace(path) {
    if (!path) return;
    try {
        const result = await callPy("add_workspace", path);
        if (result.ok) {
            currentWorkspaces = result.data;
            renderWorkspaceList(result.data);
            log("Workspace added: " + path);
        } else {
            log("Add workspace failed: " + (result.error || "unknown"));
        }
    } catch (e) {
        log("Error adding workspace: " + e.message);
    }
}

function addWorkspaceFromInput() {
    const path = document.querySelector("#workspace-path").value.trim();
    if (!path) {
        alert("Workspace path cannot be empty.");
        return;
    }
    addWorkspace(path);
}

async function removeWorkspace(path) {
    if (!path) return;
    try {
        const result = await callPy("remove_workspace", path);
        if (result.ok) {
            currentWorkspaces = result.data;
            renderWorkspaceList(result.data);
            log("Workspace removed: " + path);
        } else {
            log("Remove workspace failed: " + (result.error || "unknown"));
        }
    } catch (e) {
        log("Error removing workspace: " + e.message);
    }
}

function refreshWorkspaces() {
    loadWorkspaces();
}

async function openWarp(path) {
    if (!path) {
        path = document.querySelector("#workspace-path").value.trim();
    }
    if (!path) {
        alert("No workspace selected.");
        return;
    }
    try {
        const result = await callPy("open_warp", path);
        log(result);
    } catch (e) {
        log("Error opening Warp: " + e.message);
    }
}

function openWarpForWorkspace() {
    const path = document.querySelector("#workspace-path").value.trim();
    openWarp(path);
}
