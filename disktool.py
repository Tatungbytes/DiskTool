#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DiskTool v1.0
Compatibility update:
- Accepts legacy placeholders {sugar} and {gw}; maps to 'SugarConvDsk' and 'gw' automatically
- Clear error message if a template contains an unknown placeholder
"""

import shlex
import subprocess
import threading
import hashlib
import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

import tkinter as tk
from tkinter import ttk, messagebox

DEFAULT_DRIVE_INDEX = 0
DEFAULT_TRACKS_ARG = "c=0-39:h=0"
DEFAULT_REVS = 3
DEFAULT_BASENAME_PREFIX = "TatungBytes"
CONFIG_PATH = Path.home() / ".disktool_config.json"

def desktop_path() -> Path:
    d = Path.home() / "Desktop"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        return Path.home()
    return d

def ts_string() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def detect_converted_output(expected_primary: Path, base: str) -> Optional[Path]:
    if expected_primary.exists():
        return expected_primary
    desk = expected_primary.parent
    for p in [
        desk / f"{base}.DSK", desk / f"{base}.dsk",
        desk / f"{base}.EDSK", desk / f"{base}.edsk",
        desk / f"{base}.dsk.DSK", desk / f"{base}.edsk.EDSK", desk / f"{base}.DSK.DSK",
    ]:
        if p.exists():
            return p
    for p in desk.glob(f"{base}*"):
        s = str(p).lower()
        if p.is_file() and (s.endswith(".dsk") or s.endswith(".edsk") or s.endswith(".dsk.dsk") or s.endswith(".edsk.edsk")):
            return p
    return None

def save_basic_config(cfg: Dict[str, str]) -> None:
    try:
        import json
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass

def load_basic_config() -> Dict[str, str]:
    try:
        import json
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def run_and_log(cmd_list, log_path: Path) -> int:
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n$ {' '.join(shlex.quote(x) for x in cmd_list)}\n")
        log.flush()
        try:
            proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError as e:
            log.write(f"Executable not found: {cmd_list[0]}\n{e}\n")
            return 127
        except PermissionError as e:
            log.write(f"Permission denied running: {cmd_list[0]}\n{e}\n")
            return 126
        except Exception as e:
            log.write(f"Error launching {cmd_list!r}: {e}\n")
            return 1
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
        proc.wait()
        log.write(f"[exit code: {proc.returncode}]\n")
        return proc.returncode

def quick_check(cmd: str, args=None) -> Tuple[bool, str]:
    args = args or []
    try:
        p = subprocess.run([cmd] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return (p.returncode == 0 or ("Usage" in p.stdout) or ("help" in p.stdout.lower())), p.stdout
    except FileNotFoundError:
        return False, f"{cmd} not found on PATH"
    except Exception as e:
        return False, str(e)

class ImagerApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master); self.master = master
        self.cfg = self._defaults()
        self._setup_style()
        self._build_ui()
        self.master.after(50, self._centre_and_lock)
        self.master.after(150, self.run_startup_check)

    def _defaults(self) -> Dict[str, str]:
        cfg = load_basic_config()
        cfg.setdefault("drive", str(DEFAULT_DRIVE_INDEX))
        cfg.setdefault("tracks", DEFAULT_TRACKS_ARG)
        cfg.setdefault("revs", str(DEFAULT_REVS))
        cfg.setdefault("basename", f"{DEFAULT_BASENAME_PREFIX}_{ts_string()}")
        cfg.setdefault("read_cmd", "gw read --drive={drive} --tracks={tracks} --revs={revs} {scp}")
        cfg.setdefault("convert_cmd", "SugarConvDsk {scp} {dsk} -o=EDSK")
        return cfg

    def _setup_style(self):
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass
        style.configure("Primary.TButton",
                        font=("TkDefaultFont", 11, "bold"),
                        padding=(18, 12),
                        foreground="#ffffff",
                        background="#16a34a")
        style.map("Primary.TButton",
                  background=[("pressed", "#15803d"), ("active", "#16a34a")],
                  foreground=[("pressed", "#ffffff"), ("active", "#ffffff")])

    def _build_ui(self):
        root = self.master
        root.title("TatungBytes Imager")

        container = ttk.Frame(root, padding=(12, 12, 12, 8))
        container.grid(row=0, column=0, sticky="nw")
        container.grid_columnconfigure(0, weight=0)
        container.grid_columnconfigure(1, weight=0)

        entry_wide = 34
        entry_narrow = 12

        ttk.Label(container, text="Base name").grid(row=0, column=0, sticky="e", padx=(0,8), pady=(2,2))
        self.basename_var = tk.StringVar(value=self.cfg["basename"])
        ttk.Entry(container, textvariable=self.basename_var, width=entry_wide).grid(row=0, column=1, sticky="w", pady=(2,2))

        ttk.Label(container, text="Drive").grid(row=1, column=0, sticky="e", padx=(0,8), pady=(2,2))
        self.drive_var = tk.StringVar(value=self.cfg["drive"])
        ttk.Entry(container, textvariable=self.drive_var, width=entry_narrow).grid(row=1, column=1, sticky="w", pady=(2,2))

        ttk.Label(container, text="Tracks").grid(row=2, column=0, sticky="e", padx=(0,8), pady=(2,2))
        self.tracks_var = tk.StringVar(value=self.cfg["tracks"])
        ttk.Entry(container, textvariable=self.tracks_var, width=entry_wide).grid(row=2, column=1, sticky="w", pady=(2,2))

        ttk.Label(container, text="Revs").grid(row=3, column=0, sticky="e", padx=(0,8), pady=(2,2))
        self.revs_var = tk.StringVar(value=self.cfg["revs"])
        ttk.Entry(container, textvariable=self.revs_var, width=entry_narrow).grid(row=3, column=1, sticky="w", pady=(2,2))

        ttk.Label(container, text="Read command").grid(row=4, column=0, sticky="e", padx=(0,8), pady=(8,2))
        self.read_cmd_var = tk.StringVar(value=self.cfg["read_cmd"])
        ttk.Entry(container, textvariable=self.read_cmd_var, width=entry_wide).grid(row=4, column=1, sticky="w", pady=(8,2))

        ttk.Label(container, text="Convert command").grid(row=5, column=0, sticky="e", padx=(0,8), pady=(2,2))
        self.conv_cmd_var = tk.StringVar(value=self.cfg["convert_cmd"])
        ttk.Entry(container, textvariable=self.conv_cmd_var, width=entry_wide).grid(row=5, column=1, sticky="w", pady=(2,2))

        # Bottom row
        status_row = ttk.Frame(container)
        status_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10,0))
        status_row.grid_columnconfigure(0, weight=0)
        status_row.grid_columnconfigure(1, weight=1)
        status_row.grid_columnconfigure(2, weight=0)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_row, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        self.image_btn = ttk.Button(status_row, text="Image disk", command=self.on_image_clicked, style="Primary.TButton")
        self.image_btn.grid(row=0, column=2, sticky="e", padx=(0, 2))

    def _centre_and_lock(self):
        self.master.update_idletasks()
        req_w = self.master.winfo_reqwidth()
        req_h = self.master.winfo_reqheight()
        w = req_w + 10
        h = req_h + 10
        sw = self.master.winfo_screenwidth()
        sh = self.master.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.master.geometry(f"{w}x{h}+{x}+{y}")
        self.master.resizable(False, False)

    # ---- Logic ----

    def run_startup_check(self):
        self.image_btn.configure(state=tk.DISABLED); self.status_var.set("Running checks")
        def task():
            ok, msg = self._preflight()
            self.after(0, self.status_var.set, "Ready" if ok else "Checks failed")
            self.after(0, self.image_btn.configure, {"state": tk.NORMAL if ok else tk.DISABLED})
            if not ok:
                self.after(0, messagebox.showerror, "Preflight failed", msg)
        threading.Thread(target=task, daemon=True).start()

    def _preflight(self) -> Tuple[bool, str]:
        ok_gw, out_gw = quick_check("gw", ["--help"])
        if not ok_gw:
            return False, f"'gw' not runnable: {out_gw}"
        ok_info, _ = quick_check("gw", ["info"])
        if not ok_info:
            return False, "'gw info' failed. Ensure the device is connected and you have permissions."

        ok_sugar, out_sugar = quick_check("SugarConvDsk", ["--help"])
        if not ok_sugar:
            return False, f"'SugarConvDsk' not runnable: {out_sugar}"
        return True, "ok"

    def on_image_clicked(self):
        self.image_btn.configure(state=tk.DISABLED); self.status_var.set("Imaging, please wait")
        def task():
            try:
                self._do_image()
                self.after(0, self.status_var.set, "Completed successfully, see log on Desktop")
                self.after(0, messagebox.showinfo, "Done", "Imaging complete, see log on Desktop")
            except Exception as e:
                self.after(0, self.status_var.set, "Failed")
                self.after(0, messagebox.showerror, "Error", str(e))
            finally:
                self.after(0, self.image_btn.configure, {"state": tk.NORMAL})
        threading.Thread(target=task, daemon=True).start()

    def _format_or_explain(self, template: str, subs: Dict[str, str]) -> str:
        # Back-compat: allow {sugar} and {gw}
        subs_bc = dict(subs)
        subs_bc.setdefault("sugar", "SugarConvDsk")
        subs_bc.setdefault("gw", "gw")
        try:
            return template.format(**subs_bc)
        except KeyError as e:
            unknown = str(e).strip("'")
            raise RuntimeError(
                f"Unknown placeholder '{{{unknown}}}' in command template.\n"
                f"Allowed placeholders: {{drive}} {{tracks}} {{revs}} {{scp}} {{dsk}} (and legacy {{gw}} {{sugar}})."
            )

    def _do_image(self):
        desk = desktop_path()
        base = self.basename_var.get().strip() or f"{DEFAULT_BASENAME_PREFIX}_{ts_string()}"
        scp_path = desk / f"{base}.scp"
        out_base = desk / base
        expected_primary = desk / f"{base}.DSK"
        log_path = desk / f"{base}.log"

        drive = self.drive_var.get().strip() or str(DEFAULT_DRIVE_INDEX)
        tracks = self.tracks_var.get().strip() or DEFAULT_TRACKS_ARG
        revs = self.revs_var.get().strip() or str(DEFAULT_REVS)

        with open(log_path, "w", encoding="utf-8") as log:
            log.write(f"TatungBytes Imager log for {base}\n")
            log.write(f"Started: {datetime.datetime.now().isoformat(timespec='seconds')}\n")
            log.write(f"Desktop: {desk}\n")

        subs = {"scp": str(scp_path), "dsk": str(out_base), "drive": drive, "tracks": tracks, "revs": revs}
        read_cmd = shlex.split(self._format_or_explain(self.read_cmd_var.get(), subs))
        conv_cmd = shlex.split(self._format_or_explain(self.conv_cmd_var.get(), subs))

        rc_read = run_and_log(read_cmd, log_path)
        if rc_read != 0 or not scp_path.exists():
            raise RuntimeError("Read failed, see log file")

        rc_conv = run_and_log(conv_cmd, log_path)
        actual_dsk = detect_converted_output(expected_primary, base)
        if rc_conv != 0 or actual_dsk is None:
            raise RuntimeError("Conversion failed, see log file")

        scp_md5 = file_md5(scp_path)
        dsk_md5 = file_md5(actual_dsk)

        with open(log_path, "a", encoding="utf-8") as log:
            log.write("\n===== Summary =====\n")
            log.write(f"SCP: {scp_path}\n")
            log.write(f"DSK: {actual_dsk}\n")
            log.write(f"SCP MD5: {scp_md5}\n")
            log.write(f"DSK MD5: {dsk_md5}\n")
            log.write("===================\n")
            log.write(f"Finished: {datetime.datetime.now().isoformat(timespec='seconds')}\n")

        save_basic_config({
            "drive": drive, "tracks": tracks, "revs": revs, "basename": base,
            "read_cmd": self.read_cmd_var.get(), "convert_cmd": self.conv_cmd_var.get(),
        })

def main():
    root = tk.Tk()
    app = ImagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

