# Claude Code + Ollama Cloud

Repo ini berisi launcher untuk menjalankan **Claude Code** dengan backend **Ollama Cloud** di Windows.

Dokumentasi resmi Ollama Cloud: https://ollama.com/cloud

---

## 📋 Prasyarat

1. **Akun Ollama Cloud** aktif dengan akses ke model-model berbayar.
2. **API Key** dari [Ollama Cloud](https://ollama.com/cloud).
3. **Claude Code** terinstall:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```
4. **Node.js** (v18+) atau **Bun** terinstall.
5. Untuk **WebView2 GUI** (opsional):
   - Python 3.10+ dan `pip install -r webview2-app/requirements.txt`
   - WebView2 runtime sudah ada di Windows 10/11 modern.

---

## ⚡ Quick Start

### 1. Konfigurasi

```bash
copy config.example.json config.json
```

Edit `config.json` dan masukkan API Key Ollama Cloud-mu:

```json
{
  "OLLAMA_API_KEY": "sk-ollama-xxxxxxxxxxxxxxxx",
  "ANTHROPIC_BASE_URL": "https://ollama.com",
  "ANTHROPIC_MODEL": "glm-5.2:cloud",
  "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.2:cloud",
  "ANTHROPIC_DEFAULT_SONNET_MODEL": "minimax-m3:cloud",
  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "kimi-k2.7-code:cloud",
  "CLAUDE_CODE_SUBAGENT_MODEL": "minimax-m3:cloud",
  "CLAUDE_CODE_MAX_CONTEXT_TOKENS": 262144,
  "CLAUDE_CODE_MAX_OUTPUT_TOKENS": 131072,
  "TERMINAL": "windows_terminal"
}
```

> ⚠️ **Jangan commit `config.json` ke Git!** File ini sudah di-ignore di `.gitignore`.

### 2. Jalankan Claude Code dengan Ollama Cloud

#### A. WebView2 Desktop GUI (Baru & Direkomendasikan)

Double-click `launch-webview2.bat`, atau dari CMD:

```bash
launch-webview2.bat
```

Untuk compile jadi `.exe`:

```bash
build-webview2.bat
```

Output: `dist\ClaudeOllamaLauncher.exe`

#### B. PowerShell (CLI — handle logout & model mapping)

```powershell
.\claude-ollama.ps1
```

#### C. Batch file

```bash
run-claude-ollama.bat
```

#### D. Node.js langsung

```bash
node run-claude-ollama.js
```

---

## 🚨 Handle Kasus Logout / Onboarding Ulang

Kalau kamu **terlanjur logout** dari Claude Code dan sekarang diminta login Anthropic lagi:

- Di **WebView2 GUI**, klik tombol **Skip Onboarding** lalu **Launch Claude Code**.
- Atau jalankan PowerShell script:
  ```powershell
  .\claude-ollama.ps1
  ```

Kalau masih diminta login, tekan **Ctrl+C** dan jalankan lagi.

---

## 🌐 Mode Global (Opsional)

Kalau mau Ollama Cloud aktif untuk **semua terminal** tanpa perlu jalankan launcher:

**Aktifkan:**
```bash
enable-ollama-global.bat
```
Kemudian **Log Off dan Log On ulang Windows** agar env vars kebaca.

**Nonaktifkan (kembali ke Claude asli):**
```bash
disable-ollama-global.bat
```

**Cek status env vars:**
```bash
check-env-ollama.bat
```

---

## ⌨️ Tips Penggunaan

| Aksi | Shortcut |
|------|----------|
| Cek model aktif | Ketik `/status` di Claude Code |
| Toggle Thinking mode | `Alt + T` (Windows/Linux) |

---

## 🗂️ Struktur File

| File | Fungsi |
|------|--------|
| `webview2-app/main.py` | **WebView2 GUI launcher** — desktop app modern berbasis Edge/WebView2 |
| `webview2-app/ui/` | HTML/CSS/JS untuk antarmuka GUI |
| `launch-webview2.bat` / `.ps1` | Launcher untuk GUI |
| `webview2-build.spec` | PyInstaller spec untuk build `.exe` GUI |
| `build-webview2.bat` | Build GUI jadi `dist\ClaudeOllamaLauncher.exe` |
| `claude-ollama.ps1` | **PowerShell launcher** — paling robust, handle logout & model mapping |
| `run-claude-ollama.js` | Launcher Node.js dengan model mapping |
| `run-claude-ollama.bat` | Batch wrapper (auto-detect Node.js / Bun) |
| `enable-ollama-global.js` | Set env vars global via `setx` (include model mapping) |
| `disable-ollama-global.js` | Hapus env vars global |
| `check-env-ollama.js` | Cek env vars yang tersimpan |
| `config.json` | Konfigurasi parameter lengkap (**jangan di-commit**) |
| `config.example.json` | Template konfigurasi |

---

## 🗺️ Model Mapping Default

Launcher ini mengarahkan tier model Claude Code ke model Ollama Cloud berikut:

| Tier Claude Code | Model Ollama Cloud |
|------------------|--------------------|
| Opus             | `glm-5.2:cloud` |
| Sonnet           | `minimax-m3:cloud` |
| Haiku            | `kimi-k2.7-code:cloud` |

Semua mapping bisa diedit langsung di `config.json` atau lewat GUI WebView2.

---

## ❓ Troubleshooting

### "'claude' tidak ditemukan di PATH"
Pastikan Claude Code sudah terinstall:
```bash
npm install -g @anthropic-ai/claude-code
```

### Nama model di UI masih "Claude Sonnet / Opus / Haiku"
**Ini normal!** Claude Code adalah client Anthropic — UI-nya hardcoded menampilkan nama model Anthropic. Yang penting adalah **backend request sudah ke Ollama Cloud** karena `ANTHROPIC_BASE_URL` diarahkan ke `https://ollama.com`. Script ini juga sudah melakukan **model mapping** agar Claude Code mengirim ID model Ollama Cloud ke server.

### Context window terbatas / auto-compact terlalu sering
Claude Code kalau pakai third-party provider akan **fallback ke context default 200K**. Launcher sudah set:
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS=262144`
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072`

### Claude masih connect ke Anthropic (bukan Ollama Cloud)
1. Pastikan `ANTHROPIC_BASE_URL` dan `ANTHROPIC_AUTH_TOKEN` sudah di-set.
2. Pastikan `ANTHROPIC_API_KEY` di-set kosong (`""`) agar Claude Code tidak fallback ke akun Anthropic.
3. Kalau pakai mode global, **Log Off dan Log On ulang Windows**.
4. Kalau pakai launcher, pastikan jalankan dari terminal yang bersih.

### "Diminta login Anthropic terus"
Di GUI, klik **Skip Onboarding** lalu **Launch Claude Code**. Atau jalankan `.\claude-ollama.ps1`.

### API key tidak terbaca dari config.json
Pastikan file `config.json` ada di root repo dan berisi `OLLAMA_API_KEY` yang valid. Kalau pakai GUI `.exe`, file `config.json` sudah di-bundle saat build. Rebuild `.exe` kalau config diubah.

---

## 📄 Lisensi

MIT — Gunakan dengan risiko sendiri.
