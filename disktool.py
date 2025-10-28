#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskTool  –  v4.5
─────────────────────────────
 • Works on Windows 11 & Linux (Tkinter GUI)
 • Uses the *full* {gw} placeholder, so “gw.exe” paths work on Windows
 • Layout tweaks (no huge right-hand gap on wide Windows windows)
 • Success summary goes to the Live-output pane (no popup)
 • Avoids double “.dsk.DSK” by passing a base-name to SugarConvDsk
 • Default fallback SugarConvDsk:
     ~/Desktop/SugarConvDsk/build/SugarConvDsk/SugarConvDsk
"""

__VERSION__ = "4.5"

# ───────── imports ─────────
import os, sys, json, shlex, hashlib, time, subprocess, threading, datetime, shutil
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter.font as tkfont
# ───────────────────────────

# ───────── constants ───────
DEFAULT_DRIVE_INDEX   = 0
DEFAULT_TRACKS_ARG    = "c=0-39:h=0"
DEFAULT_REVS          = 3
DEFAULT_BASENAME_PRE  = "Einstein"
CONFIG_PATH           = Path.home() / ".einstein_imager_config.json"

SUGAR_FALLBACKS = [
    Path.home() / "Desktop/SugarConvDsk/build/SugarConvDsk/SugarConvDsk",
    Path.home() / "Desktop/SugarConvDsk/build/SugarConvDsk/SugarConvDsk.exe",
    Path.home() / "Desktop/SugarConvDsk/build/SugarConvDsk",
    Path.home() / "Desktop/SugarConvDsk/SugarConvDsk",
    Path.home() / "Desktop/SugarConvDsk/SugarConvDsk.exe",
]

# ───────────────────────────

# ───────── helpers ─────────
def split_cmd(s: str):
    # Use Windows-friendly splitting to avoid backslashes being eaten
    return shlex.split(s, posix=(os.name != "nt"))

def _maybe_exe(p: Path) -> Path:
    try:
        if os.name == "nt" and p.suffix == "" and (p.with_suffix(".exe")).exists():
            return p.with_suffix(".exe")
    except Exception:
        pass
    return p

def desktop_path() -> Path:
    try:
        p = Path.home() / "Desktop";  p.mkdir(exist_ok=True)
        return p
    except Exception:
        return Path.home()

def ts_string() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def load_cfg() -> dict:
    if CONFIG_PATH.exists():
        try:  return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:  pass
    return {}

def save_cfg(cfg: dict) -> None:
    try: CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception: pass

def shjoin(parts: List[str]) -> str:       # for display only
    return " ".join(shlex.quote(p) for p in parts)

def file_hashes(p: Path) -> Dict[str,str]:
    md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            md5.update(chunk);  sha1.update(chunk);  sha256.update(chunk)
    return dict(md5=md5.hexdigest(), sha1=sha1.hexdigest(), sha256=sha256.hexdigest())

def run_stream(cmd: List[str], cb, env=None) -> int:
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env)
    except FileNotFoundError as e:
        cb(f"Executable not found: {cmd[0]}\n{e}"); return 127
    except Exception as e:
        cb(f"Launch error {cmd!r}: {e}");           return 1
    for line in proc.stdout:  cb(line.rstrip("\n"))
    proc.wait();  return proc.returncode

def run_cap(cmd: List[str]) -> Tuple[int,str]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, check=False)
        return p.returncode, p.stdout
    except Exception as e:
        return 1, str(e)

def help_ok(out: str) -> bool:
    return any(k in out for k in ("Usage:", "Actions:", "Greaseweazle"))

def detect_output(exp: Path, base: str) -> Optional[Path]:
    if exp.exists(): return exp
    desk = exp.parent
    for suf in (".DSK",".dsk",".EDSK",".edsk",".dsk.DSK",".edsk.EDSK"):
        p = desk / f"{base}{suf}"
        if p.exists(): return p
    for p in desk.glob(f"{base}*"):
        if p.is_file() and any(x in p.suffix.lower() for x in ("dsk","edsk")):
            return p
    return None
# ───────────────────────────

class Imager(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.cfg = self._defaults(load_cfg())
        self._ui()
        self.append("Einstein Disk Imager v" + __VERSION__)
        self.master.after(200, self.run_checks)

    # ---------- config ----------
    def _defaults(self, c: dict) -> dict:
        c.setdefault("custom_gw","")
        c.setdefault("custom_sugar", str(SUGAR_FALLBACKS[0]))
        c.setdefault("drive", DEFAULT_DRIVE_INDEX)
        c.setdefault("tracks", DEFAULT_TRACKS_ARG)
        c.setdefault("revs",  DEFAULT_REVS)
        c.setdefault("basename", f"{DEFAULT_BASENAME_PRE}_{ts_string()}")
        # upgrade old read template
        read_tmpl = c.get("read_cmd","gw read --drive={drive} --tracks={tracks} --revs={revs} {scp}")
        if read_tmpl.startswith("gw read "):
            read_tmpl = "{gw} " + read_tmpl[3:]
        c["read_cmd"] = read_tmpl
        c.setdefault("convert_cmd", "{sugar} {scp} {dsk} -o=EDSK")
        return c

    # ---------- UI ----------
    def _ui(self):
        self.master.title(f"Einstein Disk Imager v{__VERSION__}")
        style = ttk.Style()
        if "vista" in style.theme_names():  style.theme_use("vista")
        self.master.geometry("900x720"); self.master.minsize(860,640)

        f = ttk.Frame(self, padding=8);  f.pack(fill="both", expand=True)
        f.columnconfigure(0, weight=1)
        # Executables
        g = ttk.LabelFrame(f, text="Executables"); g.grid(row=0,column=0,sticky="ew")
        for col in (1,): g.columnconfigure(col, weight=1)
        self.gw_lab  = tk.StringVar();  self.sugar_lab = tk.StringVar()
        ttk.Label(g,text="Resolved gw").grid(row=0,column=0,sticky="w"); ttk.Label(g,textvariable=self.gw_lab).grid(row=0,column=1,sticky="w")
        ttk.Label(g,text="Resolved SugarConvDsk").grid(row=1,column=0,sticky="w"); ttk.Label(g,textvariable=self.sugar_lab).grid(row=1,column=1,sticky="w")
        ttk.Label(g,text="Custom gw path (optional)").grid(row=2,column=0,sticky="w",pady=4)
        self.custom_gw = tk.StringVar(value=self.cfg["custom_gw"])
        ttk.Entry(g,textvariable=self.custom_gw).grid(row=2,column=1,sticky="ew"); ttk.Button(g,text="Browse…",command=self.browse_gw).grid(row=2,column=2)
        ttk.Label(g,text="Custom SugarConvDsk path (optional)").grid(row=3,column=0,sticky="w")
        self.custom_sugar = tk.StringVar(value=self.cfg["custom_sugar"])
        ttk.Entry(g,textvariable=self.custom_sugar).grid(row=3,column=1,sticky="ew"); ttk.Button(g,text="Browse…",command=self.browse_sugar).grid(row=3,column=2)
        ttk.Button(g,text="Recheck",command=self.run_checks).grid(row=4,column=0,sticky="w",pady=6)

        # Parameters
        p = ttk.LabelFrame(f,text="Output and parameters"); p.grid(row=1,column=0,sticky="ew",pady=6)
        p.columnconfigure(1, weight=1)
        ttk.Label(p,text="Base name").grid(row=0,column=0,sticky="e")
        self.basename = tk.StringVar(value=self.cfg["basename"])
        ttk.Entry(p,textvariable=self.basename).grid(row=0,column=1,columnspan=5,sticky="ew")
        ttk.Label(p,text="Drive").grid(row=1,column=0,sticky="e",pady=4)
        self.drive = tk.StringVar(value=str(self.cfg["drive"])); ttk.Entry(p,textvariable=self.drive,width=8).grid(row=1,column=1,sticky="w")
        ttk.Label(p,text="Tracks").grid(row=1,column=2,sticky="e")
        self.tracks=tk.StringVar(value=self.cfg["tracks"]); ttk.Entry(p,textvariable=self.tracks,width=16).grid(row=1,column=3,sticky="w")
        ttk.Label(p,text="Revs").grid(row=1,column=4,sticky="e")
        self.revs  = tk.StringVar(value=str(self.cfg["revs"])); ttk.Entry(p,textvariable=self.revs,width=8).grid(row=1,column=5,sticky="w")

        # Commands
        c = ttk.LabelFrame(f,text="Commands (editable)"); c.grid(row=2,column=0,sticky="ew")
        c.columnconfigure(1, weight=1)
        ttk.Label(c,text="Read").grid(row=0,column=0,sticky="e")
        self.read_cmd = tk.StringVar(value=self.cfg["read_cmd"])
        ttk.Entry(c,textvariable=self.read_cmd).grid(row=0,column=1,sticky="ew")
        ttk.Label(c,text="Convert").grid(row=1,column=0,sticky="e",pady=4)
        self.conv_cmd = tk.StringVar(value=self.cfg["convert_cmd"])
        ttk.Entry(c,textvariable=self.conv_cmd).grid(row=1,column=1,sticky="ew",pady=4)
        ttk.Label(f,text="Placeholders: {gw} {sugar} {scp} {dsk} (no ext) {drive} {tracks} {revs}",foreground="#555")\
            .grid(row=3,column=0,sticky="w",pady=(0,4))

        # Status + button
        sbar = ttk.Frame(f); sbar.grid(row=4,column=0,sticky="ew"); sbar.columnconfigure(0,weight=1)
        self.status = tk.StringVar(value="…"); ttk.Label(sbar,textvariable=self.status).grid(row=0,column=0,sticky="w")
        self.btn = ttk.Button(sbar,text="Image Disk",command=self.image_disk); self.btn.grid(row=0,column=1,sticky="e",padx=4)

        # Log
        l = ttk.LabelFrame(f,text="Live output"); l.grid(row=5,column=0,sticky="nsew"); f.rowconfigure(5,weight=1)
        self.log = scrolledtext.ScrolledText(l,wrap=tk.WORD,height=12); self.log.pack(fill="both",expand=True,padx=6,pady=6)

    # ---------- helpers ----------
    def browse_gw(self):
        p = filedialog.askopenfilename(title="Select gw executable")
        if p:
            self.custom_gw.set(p)
            self._save_current_cfg()

    def browse_sugar(self):
        p = filedialog.askopenfilename(title="Select SugarConvDsk executable")
        if p:
            self.custom_sugar.set(p)
            self._save_current_cfg()

    def append(self,text:str):
        self.log.configure(state=tk.NORMAL)
        self.log.insert("end",text+"\n"); self.log.see("end"); self.log.configure(state=tk.DISABLED)

    def _save_current_cfg(self):
        cfg = {
            **self.cfg,
            "custom_gw":    self.custom_gw.get().strip(),
            "custom_sugar": self.custom_sugar.get().strip(),
            "drive":        self.drive.get().strip(),
            "tracks":       self.tracks.get().strip(),
            "revs":         self.revs.get().strip(),
            "basename":     self.basename.get().strip(),
            "read_cmd":     self.read_cmd.get().strip(),
            "convert_cmd":  self.conv_cmd.get().strip(),
        }
        save_cfg(self._defaults(cfg))

    def run_checks(self):
        self._save_current_cfg()
        self.btn.state(["disabled"]); self.status.set("Pre-flight…")

        self.log.configure(state=tk.NORMAL); self.log.delete("1.0","end"); self.log.configure(state=tk.DISABLED)
        threading.Thread(target=self._checks_thread,daemon=True).start()

    def _resolve(self,name:str,custom:str)->Tuple[Optional[str],str]:
        msgs=[]
        p = shutil.which(name)
        if p:
            msgs.append(f"✅ {name} found on PATH: {p}")
            return p, msgs[-1]
        if name=="SugarConvDsk" and not custom:
            for c in SUGAR_FALLBACKS:
                c = _maybe_exe(Path(c))
                if c.exists() and os.access(str(c), os.X_OK):
                    msgs.append(f"✅ {name} resolved via fallback: {c}")
                    return str(c), msgs[-1]
        if custom:
            cp = _maybe_exe(Path(custom).expanduser())
            if cp.exists() and os.access(str(cp), os.X_OK):
                msgs.append(f"✅ {name} resolved via custom path: {cp}")
                return str(cp), msgs[-1]
            msgs.append(f"❌ custom path for {name} is not executable: {cp}")
        else:
            msgs.append(f"❌ {name} not found. Provide a path.")
        return None, msgs[-1]


    def _checks_thread(self):
        ok=True; msgs=[]
        gw, m = self._resolve("gw", self.custom_gw.get()); msgs.append(m)
        self.gw_lab.set(gw or "(not resolved)")
        if not gw: ok=False
        else:
            rc,out = run_cap([gw,"--help"])
            if not help_ok(out): ok=False; msgs.append("❌ 'gw --help' failed")
            else:
                rc,out2=run_cap([gw,"info"])
                if rc!=0: ok=False; msgs.append("❌ 'gw info' failed (device?)")
        sugar,m = self._resolve("SugarConvDsk", self.custom_sugar.get()); msgs.append(m)
        self.sugar_lab.set(sugar or "(not resolved)")
        if not sugar: ok=False
        self.append("\n".join(msgs))
        self.status.set("Ready." if ok else "Pre-flight failed"); 
        if ok: self.btn.state(["!disabled"])

    # ---------- main imaging ----------
    def image_disk(self):
        self.btn.state(["disabled"]); self.status.set("Imaging…")
        threading.Thread(target=self._img_thread,daemon=True).start()

    def _img_thread(self):
        gw,_ = self._resolve("gw", self.custom_gw.get()); sugar,_ = self._resolve("SugarConvDsk", self.custom_sugar.get())
        if not (gw and sugar):
            self.append("Executables unresolved."); self.status.set("Pre-flight failed"); return
        # paths & subs
        desk=desktop_path(); base=self.basename.get().strip() or f"{DEFAULT_BASENAME_PRE}_{ts_string()}"
        scp=desk/f"{base}.scp"; outbase=desk/base; exp_dsk=desk/f"{base}.DSK"
        subs=dict(gw=gw,sugar=sugar,scp=str(scp),dsk=str(outbase),
                  drive=self.drive.get().strip() or DEFAULT_DRIVE_INDEX,
                  tracks=self.tracks.get().strip() or DEFAULT_TRACKS_ARG,
                  revs=self.revs.get().strip() or DEFAULT_REVS)
        read_cmd=[gw,"read","--drive="+str(subs["drive"]),
                  "--tracks="+subs["tracks"],"--revs="+str(subs["revs"]), str(scp)]
        # honour custom template
        read_cmd=split_cmd(self.read_cmd.get().format(**subs))
        conv_cmd=split_cmd(self.conv_cmd.get().format(**subs))
        self.append(f"\nRunning (read): {shjoin(read_cmd)}")
        t0=time.time(); rc=run_stream(read_cmd,self.append); t1=time.time(); self.append(f"[exit {rc} in {t1-t0:.1f}s]")
        if rc or not scp.exists(): self.append("Read failed."); self.status.set("Read failed"); return
        self.append(f"\nRunning (convert): {shjoin(conv_cmd)}")
        rc2=run_stream(conv_cmd,self.append); t2=time.time(); self.append(f"[exit {rc2} in {t2-t1:.1f}s]")
        dsk=detect_output(exp_dsk,base)
        if rc2 or not dsk: self.append("Convert failed."); self.status.set("Convert failed"); return
        # hashes + summary
        h_scp=file_hashes(scp); h_dsk=file_hashes(dsk)
        def fmt(n,h): return f"{n}\n  MD5 {h['md5']}\n  SHA1 {h['sha1']}\n  SHA256 {h['sha256']}\n"
        self.append("\n"+fmt("SCP",h_scp)+fmt("DSK",h_dsk))
        self.append("===== Imaging complete ====="); self.status.set("Done"); self.btn.state(["!disabled"])
        # save session
        sess={"version":__VERSION__,"scp":str(scp),"dsk":str(dsk),"hashes":{"scp":h_scp,"dsk":h_dsk}}
        (desk/f"{base}_session.json").write_text(json.dumps(sess,indent=2))

# ──────────── run ───────────
if __name__ == "__main__":
    root = tk.Tk()
    app = Imager(root)
    app.pack(fill="both", expand=True)
    def _on_close():
        try:
            app._save_current_cfg()
        except Exception:
            pass
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()
