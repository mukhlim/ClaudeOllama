#!/usr/bin/env python3
"""
WebView2 Desktop App untuk Claude + Ollama Cloud Launcher.

Prasyarat:
    pip install pywebview pyinstaller

Cara jalankan:
    python webview2-app/main.py

Deskripsi:
    Aplikasi desktop berbasis HTML/CSS/JavaScript yang berjalan di atas
    WebView2 (Edge) runtime Windows. Host Python menangani operasi OS
    (spawn proses, registry, file I/O) dan mengekspose fungsi-fungsi
    tersebut ke JS frontend melalui pywebview JS API.
"""

import os
import sys
import json
import time
import tempfile
import subprocess
import ctypes
import threading
from pathlib import Path

# Deteksi apakah running dari PyInstaller bundle
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _BUNDLE_DIR = Path(sys._MEIPASS)
    # Folder temp bundle; data persisten sebaiknya disimpan di samping .exe
    _EXEC_DIR = Path(sys.executable).parent.resolve()
else:
    _BUNDLE_DIR = Path(__file__).parent.resolve()
    _EXEC_DIR = _BUNDLE_DIR.parent

# Saat di-bundle oleh PyInstaller, config.json ada di _BUNDLE_DIR (root bundle)
# Saat development, config.json ada di parent folder (root repo)
if (_BUNDLE_DIR / "config.json").exists():
    REPO_DIR = _BUNDLE_DIR
else:
    REPO_DIR = _BUNDLE_DIR.parent

CONFIG_FILE = REPO_DIR / "config.json"
CLAUDE_CONFIG_FILE = Path.home() / ".claude.json"
# workspaces.json harus persisten antar-run, jadi simpan di folder .exe/repo root
WORKSPACES_FILE = _EXEC_DIR / "workspaces.json"

DEFAULT_CONFIG = {
    "OLLAMA_API_KEY": "",
    "ANTHROPIC_BASE_URL": "https://ollama.com",
    "ANTHROPIC_MODEL": "glm-5.2:cloud",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.2:cloud",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "minimax-m3:cloud",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "kimi-k2.7-code:cloud",
    "CLAUDE_CODE_SUBAGENT_MODEL": "minimax-m3:cloud",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": 262144,
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": 131072,
    "TERMINAL": "windows_terminal",
}

ENV_VARS = [
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
]


def _load_config_raw():
    """Baca config.json, merge dengan default kalau ada field yang hilang."""
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            user_cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
        except Exception:
            pass
    return cfg


def _save_config_raw(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _model_map_from_config(cfg):
    """Bangun model mapping dari config."""
    return {
        "default": cfg.get("ANTHROPIC_MODEL", DEFAULT_CONFIG["ANTHROPIC_MODEL"]),
        "opus": cfg.get("ANTHROPIC_DEFAULT_OPUS_MODEL", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_OPUS_MODEL"]),
        "sonnet": cfg.get("ANTHROPIC_DEFAULT_SONNET_MODEL", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_SONNET_MODEL"]),
        "haiku": cfg.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_HAIKU_MODEL"]),
    }


def _set_user_env(key, value):
    """Set environment variable di User (Windows) via setx."""
    subprocess.run(["setx", key, str(value)], capture_output=True, text=True)


def _remove_user_env(key):
    """Hapus environment variable di User (Windows) via REG."""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_SET_VALUE,
        ) as regkey:
            try:
                winreg.DeleteValue(regkey, key)
            except FileNotFoundError:
                pass
        # Notify Windows of environment change
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x1A
        ctypes.windll.user32.SendNotifyMessageW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment"
        )
    except Exception as e:
        print(f"Failed to remove env {key}: {e}")


def _get_user_env(key):
    """Ambil env var dari User (Windows)."""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ,
        ) as regkey:
            return winreg.QueryValueEx(regkey, key)[0]
    except Exception:
        return ""


def _mask_token(value):
    """Masking token untuk tampilan."""
    if not value or len(value) <= 8:
        return value or ""
    return value[:4] + "..." + value[-4:]


def _which(cmd):
    """Cek apakah command tersedia di PATH Windows."""
    try:
        result = subprocess.run(["where", cmd], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _copy_to_clipboard(text):
    """Copy text ke clipboard via Windows API (ctypes) - lebih reliable daripada pyperclip."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # Set argtypes/restypes agar handle (HGLOBAL) tidak jadi negative int
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalSize.restype = ctypes.c_size_t
        kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]

        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.CloseClipboard.restype = wintypes.BOOL

        GMEM_MOVEABLE = 0x0002
        CF_UNICODETEXT = 13

        data = str(text) + "\0"
        buf = data.encode("utf-16-le")
        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(buf))
        if not h_global:
            return False
        locked = kernel32.GlobalLock(h_global)
        if not locked:
            return False
        ctypes.memmove(locked, buf, len(buf))
        kernel32.GlobalUnlock(h_global)

        if not user32.OpenClipboard(0):
            return False
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, h_global)
        user32.CloseClipboard()
        return True
    except Exception as e:
        _debug_log(f"[clipboard] ctypes error: {e}")
        # Fallback ke pyperclip
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception as e2:
            _debug_log(f"[clipboard] pyperclip fallback error: {e2}")
            return False


def _debug_log(msg):
    """Tulis log debug ke file untuk tracing di .exe."""
    try:
        log_path = Path.home() / "claude-ollama-launcher-debug.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


_WINDOW = None


def _set_window(window):
    global _WINDOW
    _WINDOW = window


def _js_log(message):
    """Kirim log ke frontend JS jika window tersedia.

    Gunakan json.dumps agar newline, backslash, dan quote di-escape dengan
    benar. Sebelumnya pesan mengandung newline membuat evaluate_js melempar
    SyntaxError karena string JS pecah sebelum ditutup.
    """
    try:
        if _WINDOW:
            payload = json.dumps(str(message), ensure_ascii=False)
            _WINDOW.evaluate_js(
                f"if (typeof log === 'function') log({payload});"
            )
    except Exception as e:
        _debug_log(f"_js_log failed: {e}")


def _run_background(target, args=()):
    """Jalankan target di thread daemon agar tidak memblokir pywebview API."""
    def wrapper():
        try:
            result = target(*args)
            _debug_log(f"[bg] result: {result}")
            _js_log(result)
        except Exception as e:
            _debug_log(f"[bg] error: {e}")
            import traceback
            _debug_log(traceback.format_exc())
            _js_log(f"Error: {e}")
    t = threading.Thread(target=wrapper, daemon=True)
    t.start()


def _wait_foreground(hwnd, timeout=8):
    """Tunggu sampai window hwnd menjadi foreground (aktif dan dapat fokus).

    Mengembalikan True kalau berhasil jadi foreground dalam timeout.
    """
    import ctypes
    user32 = ctypes.windll.user32
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            hwnd.activate()
        except Exception:
            pass
        fg = user32.GetForegroundWindow()
        # Dapatkan HWND dari pygetwindow object
        try:
            target = hwnd._hWnd
        except AttributeError:
            try:
                target = hwnd.getHandle()
            except Exception:
                target = 0
        if fg and target and fg == target:
            return True
        time.sleep(0.3)
    return False


def _send_paste_and_enter(delay_before=0.8, use_shift=False):
    """Kirim Ctrl(+Shift)+V (paste) lalu Enter via Windows SendInput (lebih reliable).

    use_shift=True untuk Ctrl+Shift+V (mis. Hyper).
    """
    try:
        import ctypes
        from ctypes import wintypes

        # Beri waktu window benar-benar siap menerima input
        if delay_before > 0:
            time.sleep(delay_before)

        user32 = ctypes.windll.user32

        # INPUT_KEYBOARD = 1
        # Key flags
        KEYEVENTF_KEYDOWN = 0x0000
        KEYEVENTF_KEYUP = 0x0002

        VK_CONTROL = 0x11
        VK_SHIFT = 0x10
        VK_V = 0x56
        VK_RETURN = 0x0D

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]
            _anonymous_ = ("_input",)
            _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]

        def make_key(vk, flags=KEYEVENTF_KEYDOWN):
            inp = INPUT()
            inp.type = 1  # INPUT_KEYBOARD
            inp.ki.wVk = vk
            inp.ki.dwFlags = flags
            return inp

        def send(*inputs):
            n = len(inputs)
            arr = (INPUT * n)(*inputs)
            user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))

        # Ctrl down, (Shift down kalau use_shift), V down, V up, (Shift up), Ctrl up
        keys = [make_key(VK_CONTROL)]
        if use_shift:
            keys.append(make_key(VK_SHIFT))
        keys.append(make_key(VK_V))
        keys.append(make_key(VK_V, KEYEVENTF_KEYUP))
        if use_shift:
            keys.append(make_key(VK_SHIFT, KEYEVENTF_KEYUP))
        keys.append(make_key(VK_CONTROL, KEYEVENTF_KEYUP))
        send(*keys)
        time.sleep(0.25)
        # Enter
        send(
            make_key(VK_RETURN),
            make_key(VK_RETURN, KEYEVENTF_KEYUP),
        )
        return True
    except Exception as e:
        _debug_log(f"_send_paste_and_enter error: {e}")
        return False


def _send_text_and_enter(text, delay_before=1.0):
    """Ketik teks ke window aktif via SendInput Unicode, lalu Enter.

    Ini lebih stabil untuk Hyper daripada mengandalkan shortcut paste
    (Ctrl+V / Ctrl+Shift+V) yang bisa berbeda antar shell/keymap.
    """
    try:
        import ctypes
        from ctypes import wintypes

        if delay_before > 0:
            time.sleep(delay_before)

        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_UNICODE = 0x0004
        VK_RETURN = 0x0D

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]
            _anonymous_ = ("_input",)
            _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]

        def send_input(*inputs):
            n = len(inputs)
            arr = (INPUT * n)(*inputs)
            sent = user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))
            return sent == n

        def make_unicode(ch, flags=0):
            inp = INPUT()
            inp.type = 1  # INPUT_KEYBOARD
            inp.ki.wVk = 0
            inp.ki.wScan = ord(ch)
            inp.ki.dwFlags = KEYEVENTF_UNICODE | flags
            return inp

        def make_key(vk, flags=0):
            inp = INPUT()
            inp.type = 1
            inp.ki.wVk = vk
            inp.ki.wScan = 0
            inp.ki.dwFlags = flags
            return inp

        for ch in str(text):
            codepoint = ord(ch)
            if codepoint <= 0xFFFF:
                if not send_input(
                    make_unicode(ch),
                    make_unicode(ch, KEYEVENTF_KEYUP),
                ):
                    return False
            else:
                # Kirim surrogate pair untuk karakter di luar BMP.
                codepoint -= 0x10000
                high = chr(0xD800 + (codepoint >> 10))
                low = chr(0xDC00 + (codepoint & 0x3FF))
                for part in (high, low):
                    if not send_input(
                        make_unicode(part),
                        make_unicode(part, KEYEVENTF_KEYUP),
                    ):
                        return False

        time.sleep(0.2)
        return send_input(
            make_key(VK_RETURN),
            make_key(VK_RETURN, KEYEVENTF_KEYUP),
        )
    except Exception as e:
        _debug_log(f"_send_text_and_enter error: {e}")
        return False


def _write_claude_temp_script(cwd, ps_command):
    """Tulis script PowerShell temp berisi env inline + `claude`."""
    temp_dir = Path(tempfile.gettempdir()) / "ClaudeOllamaLauncher"
    temp_dir.mkdir(parents=True, exist_ok=True)
    script_path = temp_dir / f"launch-claude-{os.getpid()}-{int(time.time() * 1000)}.ps1"
    safe_cwd = str(cwd).replace("'", "''")
    content = (
        "$ErrorActionPreference = 'Continue'\n"
        f"Set-Location -LiteralPath '{safe_cwd}'\n"
        f"{ps_command}\n"
        "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue\n"
    )
    script_path.write_text(content, encoding="utf-8-sig")
    return script_path


def _build_hyper_launcher_command(cwd, ps_command):
    """Buat command pendek untuk Hyper yang menjalankan Claude via PowerShell.

    Hyper CLI tidak punya opsi resmi untuk menjalankan command pada tab baru.
    Karena itu launcher membuka Hyper lalu mengetik command pendek ini. Script
    PowerShell temp berisi env inline + `claude`, lalu self-delete setelah
    Claude selesai.
    """
    script_path = _write_claude_temp_script(cwd, ps_command)
    return f'powershell.exe -NoExit -ExecutionPolicy Bypass -File "{script_path}"'


def _launch_hyper(cwd, command, timeout=15):
    """Launch Hyper terminal di working directory tertentu, lalu inject command.

    Hyper tidak menyediakan CLI resmi untuk menjalankan command pada tab baru.
    Karena shortcut paste Hyper sering beda antar konfigurasi, command diketik
    via SendInput Unicode. Clipboard tetap diisi sebagai fallback manual.
    """
    try:
        import pyautogui
        import pygetwindow as gw

        hyper_path = _which("hyper.cmd") or _which("hyper")
        pyautogui.FAILSAFE = True

        # Cari window Hyper yang sudah ada
        existing = None
        for title in gw.getAllTitles():
            if title and "hyper" in title.lower():
                existing = gw.getWindowsWithTitle(title)[0]
                break

        if existing:
            try:
                existing.activate()
            except Exception:
                pass
            _copy_to_clipboard(command)
            if _wait_foreground(existing, timeout=5):
                if _send_text_and_enter(command, delay_before=1.0):
                    return "Hyper activated and Claude command typed/run automatically."
                return "Hyper activated. Command copied to clipboard; paste it then Enter."
            return "Hyper activated. Command copied to clipboard; paste it then Enter."

        if not hyper_path:
            return None  # fallback ke powershell

        # Spawn window Hyper baru (tanpa CREATE_NEW_CONSOLE agar tidak double window)
        subprocess.Popen(
            f'"{hyper_path}" "{str(cwd)}"',
            shell=True,
        )

        # Tunggu window Hyper muncul dengan batasan timeout
        deadline = time.time() + timeout
        hwnd = None
        while time.time() < deadline:
            for title in gw.getAllTitles():
                if title and "hyper" in title.lower():
                    wins = gw.getWindowsWithTitle(title)
                    if wins:
                        hwnd = wins[0]
                        break
            if hwnd:
                break
            time.sleep(0.3)

        _copy_to_clipboard(command)
        if not hwnd:
            return "Hyper opened but could not find its window. Command copied to clipboard; paste it then Enter."

        if _wait_foreground(hwnd, timeout=8):
            if _send_text_and_enter(command, delay_before=1.5):
                return "Hyper opened and Claude command typed/run automatically."
            return "Hyper opened. Command copied to clipboard; paste it then Enter."
        return "Hyper opened. Command copied to clipboard; paste it then Enter."
    except Exception as e:
        print(f"[hyper launch] error: {e}")
        return f"Hyper launch error: {e}"


def _open_warp(path):
    """Buka Warp di path tertentu via URI scheme (new_tab)."""
    import urllib.parse
    _debug_log(f"_open_warp called with path={path}")
    try:
        encoded_path = urllib.parse.quote(str(Path(path).resolve()))
        uri = f"warp://action/new_tab?path={encoded_path}"
        _debug_log(f"_open_warp URI={uri}")
        # os.startfile lebih reliable untuk URI scheme di Windows
        try:
            os.startfile(uri)
            _debug_log("_open_warp os.startfile succeeded")
        except AttributeError:
            # Fallback kalau os.startfile tidak tersedia
            _debug_log("_open_warp os.startfile unavailable, falling back to cmd start")
            subprocess.Popen(
                ["cmd", "/c", "start", "", uri],
                shell=True,
            )
        return f"Warp opened at: {path}"
    except Exception as e:
        _debug_log(f"_open_warp error: {e}")
        import traceback
        _debug_log(traceback.format_exc())
        return f"ERROR opening Warp: {e}"


def _launch_warp(cwd, ps_command):
    """Buka Warp di cwd, copy command ke clipboard, lalu auto paste+enter.

    Urutan:
      1. Copy ps_command ke clipboard.
      2. Buka Warp via URI scheme (new_tab) di cwd.
      3. Tunggu window Warp muncul/ter-focus.
      4. Activate window Warp, Ctrl+V (paste), Enter (run).
    Kalau auto-paste gagal (window tidak ketemu), command tetap di clipboard
    agar user bisa paste manual.
    """
    # 1. Copy command ke clipboard dulu (selalu, sebagai fallback)
    _copy_to_clipboard(ps_command)

    # 2. Buka Warp di cwd
    result = _open_warp(cwd)

    # 3. Coba auto paste+enter ke window Warp
    try:
        import time as _time
        import pyautogui
        import pygetwindow as gw

        pyautogui.FAILSAFE = True

        # Tunggu window Warp muncul/ter-focus (maks ~6 detik)
        deadline = _time.time() + 6
        warp_win = None
        while _time.time() < deadline:
            for title in gw.getAllTitles():
                if title and "warp" in title.lower():
                    wins = gw.getWindowsWithTitle(title)
                    if wins:
                        warp_win = wins[0]
                        break
            if warp_win:
                break
            _time.sleep(0.3)

        if not warp_win:
            return (
                f"{result}\nClaude launch command copied to clipboard "
                "(Warp window not detected; paste with Ctrl+V then Enter)."
            )

        # 4. Activate, tunggu jadi foreground, lalu paste+enter
        if _wait_foreground(warp_win, timeout=8):
            _send_paste_and_enter(delay_before=0.6)
            return f"{result}\nClaude launch command pasted and run automatically in Warp."
        else:
            return (
                f"{result}\nClaude launch command copied to clipboard "
                "(Warp window not focused; paste with Ctrl+V then Enter)."
            )
    except Exception as e:
        _debug_log(f"_launch_warp auto-paste error: {e}")
        return (
            f"{result}\nClaude launch command copied to clipboard "
            f"(auto-paste failed: {e}; paste with Ctrl+V then Enter)."
        )


def _open_warp_and_log(path):
    """Buka Warp dan kembalikan pesan log."""
    _debug_log(f"_open_warp_and_log path={path}")
    result = _open_warp(path)
    _debug_log(f"_open_warp_and_log result={result}")
    # Copy command claude ke clipboard untuk kemudahan paste
    cfg = _load_config_raw()
    if cfg.get("OLLAMA_API_KEY"):
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = cfg.get("ANTHROPIC_BASE_URL", DEFAULT_CONFIG["ANTHROPIC_BASE_URL"])
        env["ANTHROPIC_AUTH_TOKEN"] = cfg.get("OLLAMA_API_KEY", "")
        env["ANTHROPIC_API_KEY"] = ""
        model_map = _model_map_from_config(cfg)
        env["ANTHROPIC_MODEL"] = model_map["default"]
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_map["opus"]
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model_map["sonnet"]
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model_map["haiku"]
        env["CLAUDE_CODE_SUBAGENT_MODEL"] = cfg.get("CLAUDE_CODE_SUBAGENT_MODEL", DEFAULT_CONFIG["CLAUDE_CODE_SUBAGENT_MODEL"])
        env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(cfg.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS", DEFAULT_CONFIG["CLAUDE_CODE_MAX_CONTEXT_TOKENS"]))
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(cfg.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS", DEFAULT_CONFIG["CLAUDE_CODE_MAX_OUTPUT_TOKENS"]))
        ps_cmd = _build_claude_command(env)
        if _copy_to_clipboard(ps_cmd):
            result += "\nClaude launch command copied to clipboard. Paste with Ctrl+V."
    return result


def _load_workspaces():
    """Muat daftar workspace dari WORKSPACES_FILE. Default kalau belum ada."""
    data = {"current": str(REPO_DIR), "recent": [str(REPO_DIR)]}
    try:
        if WORKSPACES_FILE.exists():
            user = json.loads(WORKSPACES_FILE.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                if "current" in user:
                    data["current"] = str(user["current"])
                if isinstance(user.get("recent"), list):
                    data["recent"] = [str(p) for p in user["recent"]]
    except Exception as e:
        _debug_log(f"_load_workspaces error: {e}")
    return data


def _save_workspaces(data):
    """Simpan daftar workspace ke WORKSPACES_FILE."""
    try:
        WORKSPACES_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except Exception as e:
        _debug_log(f"_save_workspaces error: {e}")


def _add_recent_workspace(path, max_recent=20):
    """Tambah path ke daftar recent, pindah ke paling atas, dan set sebagai current."""
    data = _load_workspaces()
    path = str(path)
    recent = [p for p in data.get("recent", []) if p != path]
    recent.insert(0, path)
    recent = recent[:max_recent]
    data["recent"] = recent
    data["current"] = path
    _save_workspaces(data)
    return data


def _browse_folder_worker(initial_dir, queue):
    """Worker yang menjalankan tkinter folder dialog di thread terpisah.

    pywebview (Edge Chromium) harus berjalan di main thread, jadi dialog
    Tkinter tidak boleh dibuka di main thread -> gunakan thread ini.
    Hasil (status, value) dikembalikan via queue.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        # Set initial dir kalau valid
        try:
            if initial_dir and Path(initial_dir).exists():
                root.tk.call("tk", "chooserDir", initial_dir)  # no-op hint
        except Exception:
            pass
        chosen = filedialog.askdirectory(
            initialdir=initial_dir if (initial_dir and Path(initial_dir).exists()) else None,
            title="Pilih Workspace Folder",
        )
        root.destroy()
        queue.put(("ok", chosen or ""))
    except Exception as e:
        try:
            queue.put(("error", str(e)))
        except Exception:
            pass


def _run_background_with_result(target, args=()):
    """Jalankan target di thread daemon, kembalikan (queue, thread).

    Target signature: target(*args, queue) -> meletakkan (status, value) di queue.
    """
    import queue as _q
    q = _q.Queue()
    real_args = tuple(args) + (q,)

    def runner():
        try:
            target(*real_args)
        except Exception as e:
            try:
                q.put(("error", str(e)))
            except Exception:
                pass

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return q, t


def _build_claude_command(env):
    """Bangun perintah PowerShell untuk launch Claude Code dengan env vars inline."""
    parts = []
    for k, v in env.items():
        if k.startswith("ANTHROPIC_") or k.startswith("CLAUDE_CODE_"):
            # Escape single quote untuk PowerShell string literal
            safe_v = str(v).replace("'", "''")
            parts.append(f"$env:{k} = '{safe_v}';")
    parts.append("claude")
    return " ".join(parts)


class Api:
    """API class yang diekspose ke JavaScript frontend via pywebview."""

    def load_config(self):
        cfg = _load_config_raw()
        terminal = cfg.get("TERMINAL", DEFAULT_CONFIG["TERMINAL"]).strip().lower()
        if terminal == "cmd":
            terminal = "windows_terminal"
        print("[load_config] API key present:", bool(cfg.get("OLLAMA_API_KEY")))
        return {
            "api_key": cfg.get("OLLAMA_API_KEY", ""),
            "base_url": cfg.get("ANTHROPIC_BASE_URL", DEFAULT_CONFIG["ANTHROPIC_BASE_URL"]),
            "model_default": cfg.get("ANTHROPIC_MODEL", DEFAULT_CONFIG["ANTHROPIC_MODEL"]),
            "model_opus": cfg.get("ANTHROPIC_DEFAULT_OPUS_MODEL", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_OPUS_MODEL"]),
            "model_sonnet": cfg.get("ANTHROPIC_DEFAULT_SONNET_MODEL", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_SONNET_MODEL"]),
            "model_haiku": cfg.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_HAIKU_MODEL"]),
            "model_subagent": cfg.get("CLAUDE_CODE_SUBAGENT_MODEL", DEFAULT_CONFIG["CLAUDE_CODE_SUBAGENT_MODEL"]),
            "max_context_tokens": int(cfg.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS", DEFAULT_CONFIG["CLAUDE_CODE_MAX_CONTEXT_TOKENS"])),
            "max_output_tokens": int(cfg.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS", DEFAULT_CONFIG["CLAUDE_CODE_MAX_OUTPUT_TOKENS"])),
            "terminal": terminal,
        }

    def save_config(self, data: dict):
        """Simpan seluruh parameter dari UI ke config.json."""
        cfg = _load_config_raw()
        cfg["OLLAMA_API_KEY"] = data.get("api_key", "").strip()
        cfg["ANTHROPIC_BASE_URL"] = data.get("base_url", DEFAULT_CONFIG["ANTHROPIC_BASE_URL"]).strip()
        cfg["ANTHROPIC_MODEL"] = data.get("model_default", DEFAULT_CONFIG["ANTHROPIC_MODEL"]).strip()
        cfg["ANTHROPIC_DEFAULT_OPUS_MODEL"] = data.get("model_opus", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_OPUS_MODEL"]).strip()
        cfg["ANTHROPIC_DEFAULT_SONNET_MODEL"] = data.get("model_sonnet", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_SONNET_MODEL"]).strip()
        cfg["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = data.get("model_haiku", DEFAULT_CONFIG["ANTHROPIC_DEFAULT_HAIKU_MODEL"]).strip()
        cfg["CLAUDE_CODE_SUBAGENT_MODEL"] = data.get("model_subagent", DEFAULT_CONFIG["CLAUDE_CODE_SUBAGENT_MODEL"]).strip()
        try:
            cfg["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = int(data.get("max_context_tokens", DEFAULT_CONFIG["CLAUDE_CODE_MAX_CONTEXT_TOKENS"]))
        except (ValueError, TypeError):
            cfg["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = DEFAULT_CONFIG["CLAUDE_CODE_MAX_CONTEXT_TOKENS"]
        try:
            cfg["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = int(data.get("max_output_tokens", DEFAULT_CONFIG["CLAUDE_CODE_MAX_OUTPUT_TOKENS"]))
        except (ValueError, TypeError):
            cfg["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = DEFAULT_CONFIG["CLAUDE_CODE_MAX_OUTPUT_TOKENS"]
        terminal = data.get("terminal", DEFAULT_CONFIG["TERMINAL"]).strip().lower()
        if terminal == "cmd":
            terminal = "windows_terminal"
        if terminal not in ("auto", "hyper", "warp", "powershell", "windows_terminal"):
            terminal = DEFAULT_CONFIG["TERMINAL"]
        cfg["TERMINAL"] = terminal
        _save_config_raw(cfg)
        return "Config saved."

    def launch_claude(self, terminal_override=None):
        """Launch Claude Code di workspace saat ini (dari workspaces.json).

        Args:
            terminal_override: pilihan terminal langsung dari dropdown UI.
                Jika diberikan dan valid, dipakai; kalau tidak, baca dari config.
                Nilai valid: auto, hyper, warp, powershell, windows_terminal.

        Env vars dimasukkan inline lewat _build_claude_command(env) sehingga
        Claude bisa jalan tanpa harus klik "Enable Global Env" terlebih dulu.
        Kalau workspace kosong/tidak valid, fallback ke REPO_DIR.
        """
        cfg = _load_config_raw()
        api_key = cfg.get("OLLAMA_API_KEY", "")
        if not api_key:
            return "ERROR: OLLAMA_API_KEY is empty. Fill it in the config and save."

        # Tentukan cwd dari current workspace
        data = _load_workspaces()
        cwd = data.get("current") or str(REPO_DIR)
        if not Path(cwd).exists():
            cwd = str(REPO_DIR)
        _add_recent_workspace(cwd)  # pastikan tercatat di recent

        # Skip onboarding
        try:
            claude_cfg = {}
            if CLAUDE_CONFIG_FILE.exists():
                claude_cfg = json.loads(CLAUDE_CONFIG_FILE.read_text(encoding="utf-8"))
            claude_cfg["hasCompletedOnboarding"] = True
            CLAUDE_CONFIG_FILE.write_text(json.dumps(claude_cfg, indent=2), encoding="utf-8")
        except Exception as e:
            return f"Onboarding skip failed: {e}"

        # Tentukan terminal: override dari UI > config.json > default
        valid_terminals = ("auto", "hyper", "warp", "powershell", "windows_terminal", "cmd")
        if isinstance(terminal_override, str):
            terminal_override = terminal_override.strip().lower()
        if terminal_override in valid_terminals:
            terminal = terminal_override
        else:
            terminal = (
                cfg.get("TERMINAL", DEFAULT_CONFIG["TERMINAL"]).strip().lower()
            )
            if terminal not in valid_terminals:
                terminal = DEFAULT_CONFIG["TERMINAL"]
        if terminal == "cmd":
            terminal = "windows_terminal"
        if terminal == "auto":
            terminal = _detect_terminal()

        # Bangun env lengkap dari config (sama dengan yg di-set di Enable Global Env)
        # lalu buat command PowerShell yang set env inline + jalankan 'claude'.
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = cfg.get(
            "ANTHROPIC_BASE_URL", DEFAULT_CONFIG["ANTHROPIC_BASE_URL"]
        )
        env["ANTHROPIC_AUTH_TOKEN"] = cfg.get("OLLAMA_API_KEY", "")
        env["ANTHROPIC_API_KEY"] = ""
        model_map = _model_map_from_config(cfg)
        env["ANTHROPIC_MODEL"] = model_map["default"]
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_map["opus"]
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model_map["sonnet"]
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model_map["haiku"]
        env["CLAUDE_CODE_SUBAGENT_MODEL"] = cfg.get(
            "CLAUDE_CODE_SUBAGENT_MODEL",
            DEFAULT_CONFIG["CLAUDE_CODE_SUBAGENT_MODEL"],
        )
        env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(
            cfg.get(
                "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
                DEFAULT_CONFIG["CLAUDE_CODE_MAX_CONTEXT_TOKENS"],
            )
        )
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(
            cfg.get(
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
                DEFAULT_CONFIG["CLAUDE_CODE_MAX_OUTPUT_TOKENS"],
            )
        )
        cmd = _build_claude_command(env)

        _run_background(_do_launch_claude, (terminal, cmd, cwd))
        return f"Launching Claude Code in {terminal} at: {cwd}"

    def enable_global(self):
        """Set env vars global via Windows registry (User)."""
        cfg = _load_config_raw()
        api_key = cfg.get("OLLAMA_API_KEY", "")
        if not api_key:
            return "ERROR: OLLAMA_API_KEY is empty. Fill it in the config and save."

        base_url = cfg.get("ANTHROPIC_BASE_URL", DEFAULT_CONFIG["ANTHROPIC_BASE_URL"])
        model_map = _model_map_from_config(cfg)

        _set_user_env("ANTHROPIC_BASE_URL", base_url)
        _set_user_env("ANTHROPIC_AUTH_TOKEN", api_key)
        _set_user_env("ANTHROPIC_API_KEY", "")
        _set_user_env("ANTHROPIC_MODEL", model_map["default"])
        _set_user_env("ANTHROPIC_DEFAULT_OPUS_MODEL", model_map["opus"])
        _set_user_env("ANTHROPIC_DEFAULT_SONNET_MODEL", model_map["sonnet"])
        _set_user_env("ANTHROPIC_DEFAULT_HAIKU_MODEL", model_map["haiku"])
        _set_user_env("CLAUDE_CODE_SUBAGENT_MODEL", cfg.get("CLAUDE_CODE_SUBAGENT_MODEL", DEFAULT_CONFIG["CLAUDE_CODE_SUBAGENT_MODEL"]))
        _set_user_env("CLAUDE_CODE_MAX_CONTEXT_TOKENS", str(cfg.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS", DEFAULT_CONFIG["CLAUDE_CODE_MAX_CONTEXT_TOKENS"])))
        _set_user_env("CLAUDE_CODE_MAX_OUTPUT_TOKENS", str(cfg.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS", DEFAULT_CONFIG["CLAUDE_CODE_MAX_OUTPUT_TOKENS"])))
        return "Global environment variables set. Log Off and Log On to apply."

    def disable_global(self):
        """Hapus env vars global dari Windows registry (User)."""
        for key in ENV_VARS:
            _remove_user_env(key)
        # Hapus juga legacy var
        _remove_user_env("ENABLE_TOOL_SEARCH")
        return "Global environment variables removed."

    def check_env(self):
        """Cek status env vars (User) dan kembalikan array untuk tabel UI."""
        result = []
        for key in ENV_VARS:
            val = _get_user_env(key)
            if val:
                display = val
                if key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY") and len(val) > 10:
                    display = _mask_token(val)
                result.append({"key": key, "value": display, "set": True})
            else:
                result.append({"key": key, "value": "(tidak di-set)", "set": False})

        # Cek legacy
        legacy = _get_user_env("ENABLE_TOOL_SEARCH")
        if legacy:
            result.append(
                {
                    "key": "ENABLE_TOOL_SEARCH",
                    "value": legacy + " (sebaiknya dihapus)",
                    "set": True,
                }
            )
        return result

    def skip_onboarding(self):
        try:
            claude_cfg = {}
            if CLAUDE_CONFIG_FILE.exists():
                claude_cfg = json.loads(CLAUDE_CONFIG_FILE.read_text(encoding="utf-8"))
            claude_cfg["hasCompletedOnboarding"] = True
            CLAUDE_CONFIG_FILE.write_text(json.dumps(claude_cfg, indent=2), encoding="utf-8")
            return "Onboarding skipped (~/.claude.json updated)."
        except Exception as e:
            return f"Failed: {e}"

    # ------------------------------------------------------------------
    # Workspace API
    # ------------------------------------------------------------------
    def load_workspaces(self):
        """Muat daftar workspace."""
        return _load_workspaces()

    def set_current_workspace(self, path: str):
        """Set workspace aktif dan pindahkan ke atas recent."""
        try:
            data = _add_recent_workspace(path)
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def add_workspace(self, path: str):
        """Tambah workspace baru ke recent list."""
        try:
            data = _add_recent_workspace(path)
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove_workspace(self, path: str):
        """Hapus workspace dari recent list."""
        try:
            data = _load_workspaces()
            recent = data.get("recent", [])
            if path in recent:
                recent.remove(path)
            data["recent"] = recent
            _save_workspaces(data)
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_warp(self, path: str = None):
        """Buka Warp di workspace path (background thread agar UI tidak stuck)."""
        if not path:
            data = _load_workspaces()
            path = data.get("current", str(REPO_DIR))
        _add_recent_workspace(path)
        _run_background(_open_warp_and_log, (path,))
        return f"Opening Warp at {path} in background..."

    def browse_folder(self):
        """Buka folder picker dialog di background thread (tkinter)."""
        try:
            q, t = _run_background_with_result(
                _browse_folder_worker, (str(_load_workspaces().get("current", str(REPO_DIR))),)
            )
            t.join(timeout=60)  # tunggu user memilih folder, maksimal 60 detik
            if not t.is_alive():
                status, value = q.get_nowait()
                if status == "ok" and value:
                    return {"ok": True, "path": value}
                elif status == "ok":
                    return {"ok": False, "path": "", "error": "No folder selected"}
                else:
                    return {"ok": False, "error": str(value)}
            # Kalau timeout, dialog masih terbuka; kembalikan error agar tidak hang
            return {"ok": False, "error": "Folder dialog timed out"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def _detect_terminal():
    """Deteksi terminal yang tersedia untuk mode 'auto'.

    Prioritas: Windows Terminal > hyper > warp > powershell.
    """
    if _which("wt.exe") or _which("wt"):
        return "windows_terminal"

    if _which("hyper.cmd") or _which("hyper"):
        return "hyper"

    # Cek apakah URI scheme warp:// terdaftar di registry
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "warp", 0, winreg.KEY_READ) as key:
            # Jika key ada, Warp terdaftar
            return "warp"
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Fallback terakhir ke PowerShell (selalu ada di Windows modern)
    return "powershell"


def _windows_terminal_geometry(width_ratio=0.70, height_ratio=0.90):
    """Hitung geometri pixel workarea + estimasi cols/rows Windows Terminal."""
    from ctypes import wintypes

    SPI_GETWORKAREA = 0x0030

    rect = wintypes.RECT()
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETWORKAREA,
        0,
        ctypes.byref(rect),
        0,
    )
    if ok:
        left, top = rect.left, rect.top
        work_width = rect.right - rect.left
        work_height = rect.bottom - rect.top
    else:
        left, top = 0, 0
        work_width = ctypes.windll.user32.GetSystemMetrics(0)
        work_height = ctypes.windll.user32.GetSystemMetrics(1)

    target_width = max(640, int(work_width * width_ratio))
    target_height = max(480, int(work_height * height_ratio))
    x = left + max(0, (work_width - target_width) // 2)
    y = top + max(0, (work_height - target_height) // 2)

    # Estimasi cell Windows Terminal default. `--size` memakai chars.
    # Ini hanya initial hint; posisi/ukuran final diset lagi secara pixel-exact
    # oleh wrapper elevated via SetWindowPos.
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
    except Exception:
        dpi = 96
    scale = max(1.0, dpi / 96)
    cols = max(80, int(target_width / (9 * scale)))
    rows = max(24, int(target_height / (20 * scale)))

    return {
        "x": x,
        "y": y,
        "width": target_width,
        "height": target_height,
        "cols": cols,
        "rows": rows,
    }


def _windows_terminal_geometry_args(width_ratio=0.70, height_ratio=0.90):
    """Hitung argumen wt.exe agar window kira-kira 70% x 90% dan center.

    Catatan: Windows Terminal menerima posisi dalam pixel (`--pos`) tetapi
    ukuran dalam kolom/baris (`--size`), bukan pixel. Jadi width/height pixel
    dikonversi ke cols/rows dengan estimasi cell default.
    """
    try:
        geom = _windows_terminal_geometry(width_ratio, height_ratio)
        return [
            "--pos",
            f"{geom['x']},{geom['y']}",
            "--size",
            f"{geom['cols']},{geom['rows']}",
        ]
    except Exception as e:
        _debug_log(f"_windows_terminal_geometry_args error: {e}")
        return []


def _ps_single_quote(value):
    """Escape value untuk PowerShell single-quoted literal."""
    return str(value).replace("'", "''")


def _write_windows_terminal_admin_wrapper(wt_path, cwd, script_path, geometry, title):
    """Tulis wrapper elevated yang launch wt lalu resize pixel-exact center."""
    temp_dir = Path(tempfile.gettempdir()) / "ClaudeOllamaLauncher"
    temp_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = temp_dir / f"launch-wt-admin-{os.getpid()}-{int(time.time() * 1000)}.ps1"
    wt_args = [
        "--pos",
        f"{geometry['x']},{geometry['y']}",
        "--size",
        f"{geometry['cols']},{geometry['rows']}",
        "new-tab",
        "--title",
        title,
        "--suppressApplicationTitle",
        "-d",
        str(cwd),
        "powershell.exe",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    ps_array = "@(" + ", ".join(f"'{_ps_single_quote(arg)}'" for arg in wt_args) + ")"
    content = f"""$ErrorActionPreference = 'Continue'
$wtPath = '{_ps_single_quote(wt_path)}'
$cwd = '{_ps_single_quote(cwd)}'
$title = '{_ps_single_quote(title)}'
$targetX = {int(geometry['x'])}
$targetY = {int(geometry['y'])}
$targetW = {int(geometry['width'])}
$targetH = {int(geometry['height'])}
$wtArgs = {ps_array}

Set-Location -LiteralPath $cwd
& $wtPath @wtArgs | Out-Null

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ClaudeOllamaWin32 {{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
}}
'@

$target = $null
$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline) {{
    $target = Get-Process -Name WindowsTerminal -ErrorAction SilentlyContinue |
        Where-Object {{ $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "*$title*" }} |
        Sort-Object StartTime -Descending |
        Select-Object -First 1
    if ($target) {{ break }}
    Start-Sleep -Milliseconds 200
}}

if ($target) {{
    $SWP_NOZORDER = 0x0004
    $SWP_SHOWWINDOW = 0x0040
    [ClaudeOllamaWin32]::SetWindowPos($target.MainWindowHandle, [IntPtr]::Zero, $targetX, $targetY, $targetW, $targetH, ($SWP_NOZORDER -bor $SWP_SHOWWINDOW)) | Out-Null
}}

Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""
    wrapper_path.write_text(content, encoding="utf-8-sig")
    return wrapper_path


def _launch_windows_terminal(cwd, ps_cmd):
    """Buka Windows Terminal elevated/admin dan jalankan Claude via PowerShell tab."""
    wt_path = _which("wt.exe") or _which("wt")
    if not wt_path:
        return None

    script_path = _write_claude_temp_script(cwd, ps_cmd)
    width_ratio = 0.70
    height_ratio = 0.90
    geometry = _windows_terminal_geometry(width_ratio, height_ratio)
    title = f"ClaudeOllama-{os.getpid()}-{int(time.time() * 1000)}"
    wrapper_path = _write_windows_terminal_admin_wrapper(
        wt_path,
        cwd,
        script_path,
        geometry,
        title,
    )

    # Request Administrator/UAC. Pakai ShellExecuteW + verb "runas" agar
    # Windows Terminal selalu elevated saat dipilih dari launcher.
    try:
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        shell32.ShellExecuteW.argtypes = [
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.c_int,
        ]
        shell32.ShellExecuteW.restype = wintypes.HINSTANCE
        params = subprocess.list2cmdline([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(wrapper_path),
        ])
        result = shell32.ShellExecuteW(
            None,
            "runas",
            "powershell.exe",
            params,
            str(cwd),
            1,  # SW_SHOWNORMAL
        )
        if int(result) <= 32:
            return f"ERROR launching Windows Terminal as Administrator (ShellExecuteW={int(result)})."
    except Exception as e:
        _debug_log(f"_launch_windows_terminal elevated error: {e}")
        return f"ERROR launching Windows Terminal as Administrator: {e}"

    return (
        "Claude Code launched in Windows Terminal as Administrator "
        f"({int(width_ratio * 100)}% x {int(height_ratio * 100)}%, centered) at: {cwd}"
    )


def _do_launch_claude(terminal, ps_cmd, cwd):
    """Worker function untuk launch Claude di background thread.

    Membuka terminal di cwd (current workspace) lalu menjalankan claude dari sana.
    """
    try:
        # Pastikan cwd valid; fallback ke REPO_DIR kalau tidak ada
        if not cwd or not Path(cwd).exists():
            cwd = str(REPO_DIR)

        if terminal == "hyper":
            result = _launch_hyper(
                cwd,
                _build_hyper_launcher_command(cwd, ps_cmd),
            )
            if result is None:
                terminal = "powershell"
            else:
                return result

        if terminal == "warp":
            return _launch_warp(cwd, ps_cmd)

        if terminal == "windows_terminal":
            result = _launch_windows_terminal(cwd, ps_cmd)
            if result is None:
                terminal = "powershell"
            else:
                return result

        if terminal in ("powershell", "auto"):
            subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", ps_cmd],
                env=os.environ.copy(),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(cwd),
            )
            return f"Claude Code launched in {terminal} terminal at: {cwd}"

        return f"Unknown terminal: {terminal}"
    except FileNotFoundError:
        return (
            "ERROR: terminal or 'claude' not found in PATH.\n"
            "Install Claude Code: npm install -g @anthropic-ai/claude-code"
        )
    except Exception as e:
        return f"ERROR launching claude: {e}"


def _center_window_position(width, height):
    """Hitung posisi x/y agar window utama center di workarea monitor utama."""
    try:
        from ctypes import wintypes

        SPI_GETWORKAREA = 0x0030
        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETWORKAREA,
            0,
            ctypes.byref(rect),
            0,
        )
        if ok:
            left, top = rect.left, rect.top
            work_width = rect.right - rect.left
            work_height = rect.bottom - rect.top
        else:
            left, top = 0, 0
            work_width = ctypes.windll.user32.GetSystemMetrics(0)
            work_height = ctypes.windll.user32.GetSystemMetrics(1)

        x = left + max(0, (work_width - int(width)) // 2)
        y = top + max(0, (work_height - int(height)) // 2)
        return x, y
    except Exception as e:
        _debug_log(f"_center_window_position error: {e}")
        return None, None


def main():
    import webview

    try:
        ui_dir = _BUNDLE_DIR / "ui"
        index_html = ui_dir / "index.html"

        if not index_html.exists():
            raise FileNotFoundError(f"UI file not found: {index_html}")

        # Use absolute file URL agar resource loading aman
        url = index_html.resolve().as_uri()

        api = Api()
        window_width = 1080
        window_height = 820
        window_x, window_y = _center_window_position(window_width, window_height)
        _set_window(
            webview.create_window(
                "Claude + Ollama Cloud Launcher",
                url,
                width=window_width,
                height=window_height,
                x=window_x,
                y=window_y,
                min_size=(900, 700),
                js_api=api,
            )
        )
        webview.start(gui="edgechromium")
    except Exception as e:
        log_path = Path.home() / "claude-ollama-launcher-error.log"
        with open(log_path, "a", encoding="utf-8") as f:
            import traceback
            f.write(f"[{__file__}] ERROR: {e}\n")
            traceback.print_exc(file=f)
        # Also show message box if possible
        try:
            ctypes.windll.user32.MessageBoxW(0, str(e), "ClaudeOllamaLauncher Error", 0x10)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
