#!/usr/bin/env node
/**
 * Aktifkan Ollama Cloud secara GLOBAL untuk semua app/terminal/extension.
 *
 * Cara pakai:
 *   1. Edit config.json dan masukkan API Key asli.
 *   2. Jalankan: node enable-ollama-global.js
 *      atau double-click enable-ollama-global.bat
 */

import { spawn } from "node:child_process";
import { join, dirname } from "node:path";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CONFIG_FILE = join(__dirname, "config.json");

function loadConfig() {
  if (!existsSync(CONFIG_FILE)) {
    console.error(`❌ File ${CONFIG_FILE} tidak ditemukan.`);
    console.error('   Buat file config.json dengan isi: { "OLLAMA_API_KEY": "sk-ollama-xxxx" }');
    process.exit(1);
  }
  try {
    return JSON.parse(readFileSync(CONFIG_FILE, "utf-8"));
  } catch (err) {
    console.error("❌ Gagal membaca config.json:", err.message);
    process.exit(1);
  }
}

function setx(key, value) {
  return new Promise((resolve, reject) => {
    const child = spawn("setx", [key, value], { stdio: "pipe", shell: false });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d; });
    child.stderr.on("data", (d) => { stderr += d; });
    child.on("close", (code) => {
      if (code === 0) resolve(stdout.trim());
      else reject(new Error(stderr || `exit code ${code}`));
    });
  });
}

async function main() {
  console.log("🌐 Mengaktifkan Ollama Cloud secara GLOBAL...\n");

  const config = loadConfig();
  const OLLAMA_API_KEY = config.OLLAMA_API_KEY;

  if (!OLLAMA_API_KEY || OLLAMA_API_KEY.includes("xxxxxxxx")) {
    console.error("❌ OLLAMA_API_KEY belum diisi di config.json!");
    console.error("   Edit file config.json dan ganti placeholder dengan API Key asli.");
    process.exit(1);
  }

  console.log("⚙️  Menulis environment variables via setx (User)...\n");

  try {
    await setx("ANTHROPIC_BASE_URL", "https://ollama.com");
    console.log("✅ ANTHROPIC_BASE_URL=https://ollama.com");
  } catch (err) {
    console.error("❌ Gagal set ANTHROPIC_BASE_URL:", err.message);
  }

  try {
    await setx("ANTHROPIC_AUTH_TOKEN", OLLAMA_API_KEY);
    console.log("✅ ANTHROPIC_AUTH_TOKEN=******");
  } catch (err) {
    console.error("❌ Gagal set ANTHROPIC_AUTH_TOKEN:", err.message);
  }

  try {
    await setx("ANTHROPIC_API_KEY", "");
    console.log("✅ ANTHROPIC_API_KEY=\"\"");
  } catch (err) {
    console.error("❌ Gagal set ANTHROPIC_API_KEY:", err.message);
  }

  // Map slot model Anthropic -> model Ollama Cloud
  const modelMappings = [
    ["ANTHROPIC_MODEL", "minimax-m3:cloud"],
    ["ANTHROPIC_DEFAULT_OPUS_MODEL", "glm-5.2:cloud"],
    ["ANTHROPIC_DEFAULT_SONNET_MODEL", "qwen3.5:cloud"],
    ["ANTHROPIC_DEFAULT_HAIKU_MODEL", "kimi-k2.7-code:cloud"],
    ["ANTHROPIC_CUSTOM_MODEL_OPTION", "deepseek-v4-pro:cloud"],
    ["ANTHROPIC_CUSTOM_MODEL_OPTION_NAME", "deepseek-v4-pro:cloud"],
    ["ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION", "DeepSeek V4 Pro via Ollama Cloud"],
    ["CLAUDE_CODE_SUBAGENT_MODEL", "deepseek-v4-pro:cloud"],
    ["CLAUDE_CODE_MAX_CONTEXT_TOKENS", "1000000"],
    ["CLAUDE_CODE_MAX_OUTPUT_TOKENS", "65536"],
  ];

  for (const [key, value] of modelMappings) {
    try {
      await setx(key, value);
      console.log(`✅ ${key}=${value}`);
    } catch (err) {
      console.error(`❌ Gagal set ${key}:`, err.message);
    }
  }

  // Hapus ENABLE_TOOL_SEARCH kalau pernah di-set (tidak disebut di docs resmi)
  try {
    await setx("ENABLE_TOOL_SEARCH", "");
    console.log("✅ ENABLE_TOOL_SEARCH dihapus (bersih-bersih)");
  } catch (err) {
    // Abaikan error
  }

  console.log("\n✅ Ollama Cloud Global AKTIF!");
  console.log("\n⚠️  PENTING — Lakukan salah satu dari ini agar kebaca:");
  console.log("   1. Tutup dan buka ulang semua terminal / VS Code / Cursor.");
  console.log("   2. Kalau masih belum kebaca, Log Off dan Log On ulang Windows.");
  console.log("\n💡 Untuk balik ke Claude asli, jalankan: disable-ollama-global.bat");
}

main();
