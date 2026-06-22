#!/usr/bin/env node
/**
 * Script launcher untuk menjalankan Claude Code dengan backend Ollama Cloud.
 *
 * Cara pakai:
 *   1. Edit file config.json dan masukkan API Key Ollama Cloud-mu.
 *   2. Jalankan: node run-claude-ollama.js
 *      (atau double-click run-claude-ollama.bat di Windows)
 */

import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join, dirname } from "node:path";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Compatibel dengan Node.js (bukan Bun)
const __dirname = dirname(fileURLToPath(import.meta.url));
const CONFIG_FILE = join(__dirname, "config.json");
const CLAUDE_CONFIG_FILE = join(homedir(), ".claude.json");
const ANTHROPIC_BASE_URL = "https://ollama.com";

const MODEL_MAP = {
  default: "glm-5.2:cloud",
  opus: "glm-5.2:cloud",
  sonnet: "minimax-m3:cloud",
  haiku: "kimi-k2.7-code:cloud",
};

function loadConfig() {
  if (!existsSync(CONFIG_FILE)) {
    console.error(`❌ File ${CONFIG_FILE} tidak ditemukan.`);
    console.error("   Buat file config.json di folder ini dengan isi:");
    console.error('   { "OLLAMA_API_KEY": "sk-ollama-xxxxxxxxxxxxxxxx" }');
    process.exit(1);
  }

  try {
    return JSON.parse(readFileSync(CONFIG_FILE, "utf-8"));
  } catch (err) {
    console.error("❌ Gagal membaca config.json:", err.message);
    process.exit(1);
  }
}

function skipOnboarding() {
  try {
    let config = {};
    if (existsSync(CLAUDE_CONFIG_FILE)) {
      const raw = readFileSync(CLAUDE_CONFIG_FILE, "utf-8");
      config = JSON.parse(raw);
    }
    config.hasCompletedOnboarding = true;
    writeFileSync(CLAUDE_CONFIG_FILE, JSON.stringify(config, null, 2), "utf-8");
    console.log("✅ Onboarding flag ditulis ke", CLAUDE_CONFIG_FILE);
  } catch (err) {
    console.error("⚠️  Gagal menulis .claude.json:", err.message);
  }
}

function main() {
  const config = loadConfig();
  const OLLAMA_API_KEY = config.OLLAMA_API_KEY;

  if (!OLLAMA_API_KEY || OLLAMA_API_KEY.includes("xxxxxxxx")) {
    console.error("❌ OLLAMA_API_KEY belum diisi di config.json!");
    console.error("   Edit file config.json dan ganti placeholder dengan API Key asli.");
    process.exit(1);
  }

  // 1. Skip onboarding Anthropic (force true, handle kasus logout)
  skipOnboarding();

  // 2. Siapkan environment variables
  const env = {
    ...process.env,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_AUTH_TOKEN: OLLAMA_API_KEY,
    ANTHROPIC_API_KEY: "",
    // Map slot model Anthropic -> model Ollama Cloud
    // UI Claude Code tetap nunjukin nama Anthropic, tapi backend ke Ollama Cloud
    ANTHROPIC_MODEL: MODEL_MAP.default,
    ANTHROPIC_DEFAULT_OPUS_MODEL: MODEL_MAP.opus,
    ANTHROPIC_DEFAULT_SONNET_MODEL: MODEL_MAP.sonnet,
    ANTHROPIC_DEFAULT_HAIKU_MODEL: MODEL_MAP.haiku,
    CLAUDE_CODE_SUBAGENT_MODEL: MODEL_MAP.sonnet,
    // Override context & output tokens (Claude Code fallback ke default kalau tidak di-set)
    CLAUDE_CODE_MAX_CONTEXT_TOKENS: "262144",
    CLAUDE_CODE_MAX_OUTPUT_TOKENS: "131072",
  };

  // Bersihkan ENABLE_TOOL_SEARCH kalau pernah di-set global
  delete env.ENABLE_TOOL_SEARCH;

  console.log("🚀 Menjalankan Claude Code dengan backend Ollama Cloud...");
  console.log("   Base URL :", ANTHROPIC_BASE_URL);
  console.log("   API Key  :", OLLAMA_API_KEY.slice(0, 6) + "..." + OLLAMA_API_KEY.slice(-4));
  console.log("");
  console.log("📋 Model Mapping:");
  console.log("   Default  :", env.ANTHROPIC_MODEL);
  console.log("   Opus     :", env.ANTHROPIC_DEFAULT_OPUS_MODEL, "(-> glm-5.2:cloud)");
  console.log("   Sonnet   :", env.ANTHROPIC_DEFAULT_SONNET_MODEL, "(-> minimax-m3:cloud)");
  console.log("   Haiku    :", env.ANTHROPIC_DEFAULT_HAIKU_MODEL, "(-> kimi-k2.7-code:cloud)");
  console.log("   Subagent :", env.CLAUDE_CODE_SUBAGENT_MODEL);
  console.log("");
  console.log("📐 Context / Output:");
  console.log("   Max Context Tokens :", env.CLAUDE_CODE_MAX_CONTEXT_TOKENS);
  console.log("   Max Output Tokens  :", env.CLAUDE_CODE_MAX_OUTPUT_TOKENS);
  console.log("");
  console.log("💡 Tips: Setelah Claude nyala, ketik /status untuk cek model aktif.");
  console.log("   Tekan Alt+T untuk toggle Thinking mode.");
  console.log("-".repeat(60));

  // 3. Spawn claude
  const claude = spawn("claude", [], {
    env,
    stdio: "inherit",
    shell: true,
    windowsHide: false,
  });

  claude.on("error", (err) => {
    if (err.code === "ENOENT") {
      console.error("\n❌ 'claude' tidak ditemukan di PATH.");
      console.error("   Pastikan Claude Code sudah terinstall.");
      console.error("   Install: npm install -g @anthropic-ai/claude-code");
    } else {
      console.error("\n❌ Error menjalankan claude:", err.message);
    }
    process.exit(1);
  });

  claude.on("close", (code) => {
    console.log("\n👋 Claude Code exited with code", code);
    process.exit(code ?? 0);
  });
}

main();
