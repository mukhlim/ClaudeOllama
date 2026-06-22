#!/usr/bin/env node
/**
 * Cek environment variables Ollama Cloud di Windows User Environment.
 * Jalankan: node check-env-ollama.js
 */

import { spawn } from "node:child_process";

const VARS = [
  "ANTHROPIC_BASE_URL",
  "ANTHROPIC_AUTH_TOKEN",
  "ANTHROPIC_API_KEY",
  "ANTHROPIC_MODEL",
  "ANTHROPIC_DEFAULT_OPUS_MODEL",
  "ANTHROPIC_DEFAULT_SONNET_MODEL",
  "ANTHROPIC_DEFAULT_HAIKU_MODEL",
  "CLAUDE_CODE_SUBAGENT_MODEL",
  "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
  "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
];

function getUserEnvVar(key) {
  return new Promise((resolve) => {
    let stdout = "";
    const ps = spawn(
      "powershell",
      ["-Command", `[Environment]::GetEnvironmentVariable('${key}', 'User')`],
      { stdio: "pipe", shell: true }
    );
    ps.stdout.on("data", (d) => { stdout += d; });
    ps.on("close", () => {
      resolve(stdout.trim());
    });
  });
}

async function main() {
  console.log("🔍 Mengecek User Environment Variables...\n");

  for (const key of VARS) {
    const val = await getUserEnvVar(key);
    if (val) {
      const display = key === "ANTHROPIC_AUTH_TOKEN" && val.length > 10
        ? val.slice(0, 6) + "..." + val.slice(-4)
        : val;
      console.log(`✅ ${key} = ${display}`);
    } else {
      console.log(`❌ ${key} = (tidak di-set)`);
    }
  }

  // Cek ENABLE_TOOL_SEARCH (legacy, sebaiknya tidak di-set)
  const toolSearch = await getUserEnvVar("ENABLE_TOOL_SEARCH");
  if (toolSearch) {
    console.log(`⚠️  ENABLE_TOOL_SEARCH = ${toolSearch} (sebaiknya dihapus, tidak diperlukan)`);
  }

  console.log("\n📌 Catatan:");
  console.log("   Kalau semua ✅ tapi Claude masih ke Anthropic,");
  console.log("   coba Log Off dan Log On ulang Windows.");
  console.log("   Kalau masih ❌, jalankan enable-ollama-global.bat lagi.");
}

main();
