#!/usr/bin/env node
/**
 * Nonaktifkan Ollama Cloud global — hapus env vars agar Claude Code
 * kembali ke backend Anthropic (Claude asli).
 *
 * Cara pakai:
 *   node disable-ollama-global.js
 *   atau double-click disable-ollama-global.bat
 */

import { spawn } from "node:child_process";

function removeUserEnvVar(key) {
  return new Promise((resolve, reject) => {
    const ps = spawn(
      "powershell",
      [
        "-Command",
        `[Environment]::SetEnvironmentVariable('${key}', $null, 'User')`,
      ],
      { stdio: "pipe", shell: true }
    );
    let stderr = "";
    ps.stderr.on("data", (d) => { stderr += d; });
    ps.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr || `exit code ${code}`));
    });
  });
}

async function main() {
  console.log("🔁 Menonaktifkan Ollama Cloud global...\n");
  console.log("⚙️  Menghapus environment variables dari Windows User Environment...");

  const vars = [
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
    "ENABLE_TOOL_SEARCH",
  ];

  for (const key of vars) {
    try {
      await removeUserEnvVar(key);
      console.log(`   ✓ ${key} dihapus`);
    } catch (err) {
      console.log(`   ⚠️  ${key} (tidak ditemukan atau sudah dihapus)`);
    }
  }

  console.log("\n✅ Ollama Cloud Global NONAKTIF!");
  console.log("   Claude Code sekarang kembali ke backend Anthropic (Claude asli).");
  console.log("\n⚠️  Catatan:");
  console.log("   - Tutup dan buka ulang terminal/VS Code agar perubahan terbaca.");
  console.log("   - Kalau mau aktifin Ollama Cloud lagi, jalankan: enable-ollama-global.bat");
}

main();
