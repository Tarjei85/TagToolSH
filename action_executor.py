"""
Action executor for TagToolSH!.
Executes URIs (Spotify, Steam, Epic, Web) and local executables.
Handles per-tag kill-on-removal, taskkill on tag removal, and auto-detection
of game processes spawned by launchers and wrapper scripts.

Policy summary:
  - Spotify actions are HARD-EXCLUDED from tracking/killing.
  - Auto-detection runs for launcher URIs (steam, epic, generic uri/url) AND
    for .bat / .cmd / .lnk targets, since those are wrappers whose real game
    process cannot be derived from the tag content alone.
  - Direct .exe targets are tracked by image name immediately, no detection.
  - Manual override (process_to_kill) always wins over auto-detection.
  - process_to_kill == "none" or "off" disables tracking for that tag entirely.
  - Auto-detected names are stored back in the library (auto_detected_process).
"""

import os
import shlex
import subprocess
import time
from typing import Optional, Tuple, Dict, Any, Callable, List

from ndef_handler import NdefAction

import psutil


# Action types that can NEVER be tracked for taskkill on removal
TASKKILL_HARD_EXCLUDED_TYPES = {"spotify"}

# URI-style action types that support auto-detection
AUTO_DETECT_ELIGIBLE_URI_TYPES = {"steam", "epic", "uri", "url"}

# Executable extensions that require auto-detection (wrappers)
AUTO_DETECT_WRAPPER_EXTENSIONS = {".bat", ".cmd", ".lnk"}

# Launcher shells whose children we trust as game candidates
LAUNCHER_IMAGE_BLOCKLIST = {
    "steam.exe",
    "steamwebhelper.exe",
    "steamservice.exe",
    "epicgameslauncher.exe",
    "epicwebhelper.exe",
    "galaxyclient.exe",
    "goggalaxy.exe",
    "galaxyclientservice.exe",
    "uplay.exe",
    "ubisoftconnect.exe",
    "upc.exe",
    "battle.net.exe",
    "agent.exe",
    "origin.exe",
    "eadesktop.exe",
    "riotclientservices.exe",
    "riotclientcrashhandler.exe",
    "cmd.exe",
    "conhost.exe",
    "windowsterminal.exe",
    "wt.exe",
    "powershell.exe",
    "pwsh.exe",
}

# Processes that are never a valid game target even if they look new
GAME_CANDIDATE_BLOCKLIST = LAUNCHER_IMAGE_BLOCKLIST | {
    "msedge.exe",
    "msedgewebview2.exe",
    "chrome.exe",
    "firefox.exe",
    "opera.exe",
    "brave.exe",
    "iexplore.exe",
    "explorer.exe",
    "dllhost.exe",
    "svchost.exe",
    "runtimebroker.exe",
    "searchindexer.exe",
    "taskhostw.exe",
    "sihost.exe",
    "ctfmon.exe",
    "fontdrvhost.exe",
    "dwm.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "textinputhost.exe",
    "applicationframehost.exe",
    "systemsettings.exe",
    "wmiprvse.exe",
    "audiodg.exe",
    "spoolsv.exe",
    "lsass.exe",
    "services.exe",
    "wininit.exe",
    "csrss.exe",
    "smss.exe",
    "winlogon.exe",
    "taskmgr.exe",
    "mmc.exe",
    "regedit.exe",
    "notepad.exe",
    "calculator.exe",
    "msmpeng.exe",
    "nissrv.exe",
    "securityhealthservice.exe",
    "securityhealthsystray.exe",
    "avp.exe",
    "avastui.exe",
    "avgnt.exe",
    "mbam.exe",
    "malwarebytes.exe",
}

# Sentinel values for process_to_kill that mean "do not track"
NO_TRACK_SENTINELS = {"none", "off", "disable", "disabled"}

# Minimum RSS (bytes) for a candidate to be considered a real game
MIN_CANDIDATE_RSS = 50 * 1024 * 1024


class ActionExecutor:
    def __init__(self, debounce_seconds: float = 2.5):
        self.debounce_seconds = debounce_seconds
        self.last_executed_uid: Optional[str] = None
        self.last_executed_time: float = 0.0
        self.current_present_uid: Optional[str] = None
        self.active_processes: Dict[str, str] = {}
        self.active_pids: Dict[str, int] = {}
        self.active_paths: Dict[str, str] = {}

        # Auto-detection state
        self.auto_detect_enabled: bool = True
        self.auto_detect_delay_seconds: int = 15
        self._on_auto_detected: Optional[Callable[[str, str], None]] = None
        self._on_detection_log: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def set_auto_detect_callback(self, cb: Callable[[str, str], None]):
        self._on_auto_detected = cb

    def set_log_callback(self, cb: Callable[[str], None]):
        self._on_detection_log = cb

    def _log(self, msg: str):
        if self._on_detection_log:
            try:
                self._on_detection_log(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Tag presence
    # ------------------------------------------------------------------ #
    def on_tag_placed(self, uid: str):
        self.current_present_uid = uid

    def on_tag_removed(self, uid: str) -> Tuple[bool, str]:
        if self.current_present_uid == uid:
            self.current_present_uid = None

        if uid in self.active_processes or uid in self.active_pids:
            tracked = self.active_processes.get(uid) or f"PID {self.active_pids.get(uid)}"
            return True, f"Tag {uid} had tracked process: {tracked}"
        return False, "No tracked process for this tag."

    # ------------------------------------------------------------------ #
    # Debounce
    # ------------------------------------------------------------------ #
    def can_execute(self, uid: str) -> Tuple[bool, str]:
        now = time.time()
        elapsed = now - self.last_executed_time

        if uid == self.last_executed_uid and elapsed < self.debounce_seconds:
            return False, f"Debounce active ({elapsed:.1f}s / {self.debounce_seconds:.1f}s)"

        return True, "OK"

    # ------------------------------------------------------------------ #
    # Which actions need auto-detection?
    # ------------------------------------------------------------------ #
    @staticmethod
    def _needs_auto_detection(action_type: str, target: str) -> bool:
        if action_type in AUTO_DETECT_ELIGIBLE_URI_TYPES:
            return True
        if action_type == "executable":
            ext = os.path.splitext(target.lower())[1]
            return ext in AUTO_DETECT_WRAPPER_EXTENSIONS
        return False

    # ------------------------------------------------------------------ #
    # Process list snapshotting
    # ------------------------------------------------------------------ #
    @staticmethod
    def _snapshot_processes() -> Dict[int, Dict[str, Any]]:
        snapshot: Dict[int, Dict[str, Any]] = {}
        for p in psutil.process_iter(["pid", "name", "ppid", "memory_info"]):
            try:
                info = p.info
                pid = info.get("pid")
                if pid is None:
                    continue
                rss = 0
                mem = info.get("memory_info")
                if mem is not None:
                    rss = getattr(mem, "rss", 0) or 0
                snapshot[pid] = {
                    "name": (info.get("name") or "").lower(),
                    "ppid": info.get("ppid") or 0,
                    "rss": rss,
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return snapshot

    # ------------------------------------------------------------------ #
    # Candidate filtering
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_descendant_of(pid: int, ancestor_pid: int,
                          snapshot: Dict[int, Dict[str, Any]],
                          max_depth: int = 10) -> bool:
        current = pid
        for _ in range(max_depth):
            info = snapshot.get(current)
            if not info:
                return False
            parent = info.get("ppid", 0)
            if parent == 0:
                return False
            if parent == ancestor_pid:
                return True
            current = parent
        return False

    def _collect_descendants(self, ancestor_pid: int,
                             snapshot: Dict[int, Dict[str, Any]]) -> List[int]:
        descendants = []
        for pid in snapshot.keys():
            if pid == ancestor_pid:
                continue
            if self._is_descendant_of(pid, ancestor_pid, snapshot):
                descendants.append(pid)
        return descendants

    def _pick_game_process(
        self,
        before: Dict[int, Dict[str, Any]],
        after: Dict[int, Dict[str, Any]],
        launch_pid: Optional[int] = None,
    ) -> Optional[str]:
        """
        Chooses the best candidate game process. Instrumented with
        diagnostic logging that reports every branch reached.
        """
        new_pids = [pid for pid in after.keys() if pid not in before]
        self._log(f"[PICK] before={len(before)} after={len(after)} "
                  f"new={len(new_pids)} launch_pid={launch_pid}")

        if not new_pids:
            self._log("[PICK] no new processes appeared")
            return None

        # Log every new process so we can see what showed up.
        for p in new_pids:
            info = after.get(p)
            if not info:
                continue
            self._log(
                f"[PICK]   new pid={p} name={info['name']} "
                f"ppid={info['ppid']} rss={info['rss'] // (1024*1024)}MB"
            )

        # ---- Tier 1: strict PID ancestry ---- #
        if launch_pid is not None:
            if launch_pid in after:
                self._log(f"[PICK] Tier 1 active: launch_pid={launch_pid} is in after snapshot")
                descendants = set(self._collect_descendants(launch_pid, after))
                self._log(f"[PICK] descendants of launch_pid: {sorted(descendants)}")

                if after[launch_pid]["name"] not in LAUNCHER_IMAGE_BLOCKLIST:
                    descendants.add(launch_pid)

                strict_candidates = []
                for pid in descendants:
                    info = after.get(pid)
                    if not info:
                        continue
                    name = info["name"]
                    if not name:
                        self._log(f"[PICK]   skip pid={pid} (no name)")
                        continue
                    if name in GAME_CANDIDATE_BLOCKLIST:
                        self._log(f"[PICK]   skip pid={pid} name={name} (blocklisted)")
                        continue
                    strict_candidates.append({
                        "pid": pid,
                        "name": name,
                        "rss": info["rss"],
                    })
                    self._log(
                        f"[PICK]   strict candidate pid={pid} name={name} "
                        f"rss={info['rss'] // (1024*1024)}MB"
                    )

                if strict_candidates:
                    strict_candidates.sort(key=lambda c: c["rss"], reverse=True)
                    winner = strict_candidates[0]
                    if winner["rss"] >= MIN_CANDIDATE_RSS:
                        self._log(f"[PICK] Tier 1 winner: {winner['name']} "
                                  f"({winner['rss'] // (1024*1024)} MB)")
                        return winner["name"]
                    else:
                        self._log(
                            f"[PICK] Tier 1 winner too small: {winner['name']} "
                            f"only {winner['rss'] // (1024*1024)} MB"
                        )
                else:
                    self._log("[PICK] Tier 1 had no strict candidates")
            else:
                self._log(f"[PICK] launch_pid={launch_pid} not in after snapshot; "
                          "cmd.exe already exited")

        # ---- Tier 2: launcher-shell heuristic ---- #
        launcher_pids = set()
        for pid, info in after.items():
            if info["name"] in LAUNCHER_IMAGE_BLOCKLIST:
                launcher_pids.add(pid)

        self._log(f"[PICK] Tier 2 launcher_pids={sorted(launcher_pids)}")

        if not launcher_pids:
            self._log("[PICK] no known launcher process present")
            return None

        launcher_descendants = set()
        for lp in launcher_pids:
            launcher_descendants.update(self._collect_descendants(lp, after))

        self._log(f"[PICK] Tier 2 launcher descendants: {sorted(launcher_descendants)}")

        candidates = []
        for pid in new_pids:
            info = after.get(pid)
            if not info:
                continue
            name = info["name"]
            if not name:
                continue
            if name in GAME_CANDIDATE_BLOCKLIST:
                self._log(f"[PICK]   skip pid={pid} name={name} (blocklisted)")
                continue
            if pid in launcher_pids:
                self._log(f"[PICK]   skip pid={pid} name={name} (is a launcher)")
                continue
            if pid not in launcher_descendants:
                self._log(f"[PICK]   skip pid={pid} name={name} (not a launcher descendant)")
                continue
            candidates.append({
                "pid": pid,
                "name": name,
                "rss": info["rss"],
            })
            self._log(
                f"[PICK]   Tier 2 candidate pid={pid} name={name} "
                f"rss={info['rss'] // (1024*1024)}MB"
            )

        if not candidates:
            self._log("[PICK] no candidate passed Tier 2 filters")
            return None

        candidates.sort(key=lambda c: c["rss"], reverse=True)
        winner = candidates[0]

        if winner["rss"] < MIN_CANDIDATE_RSS:
            self._log(
                f"[PICK] Tier 2 winner too small: {winner['name']} "
                f"only {winner['rss'] // (1024*1024)} MB"
            )
            return None

        self._log(f"[PICK] Tier 2 winner: {winner['name']} "
                  f"({winner['rss'] // (1024*1024)} MB)")
        return winner["name"]

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def execute_action(
        self,
        action: NdefAction,
        uid: Optional[str] = None,
        force: bool = False,
        read_only: bool = False,
        kill_on_removal: bool = False,
        stored_auto_process: str = "",
    ) -> Tuple[bool, str]:
        if uid and not force:
            can_run, reason = self.can_execute(uid)
            if not can_run:
                return False, reason

        action_type = action.action_type.lower()
        target = action.target.strip()
        args = action.args.strip() if hasattr(action, 'args') and action.args else ""

        if read_only:
            if action_type == "text":
                return True, f"[READ-ONLY] Text content: {target}"
            preview = target
            if args:
                preview += f" {args}"
            return True, f"[READ-ONLY] Would execute: {preview}"

        manual = getattr(action, "process_to_kill", "") or ""
        manual = manual.strip()
        if manual.lower() in NO_TRACK_SENTINELS:
            self._log(f"Tracking disabled by sentinel for uid={uid}")
            manual = "__DISABLED__"

        track_this = (
            bool(uid)
            and bool(kill_on_removal)
            and action_type not in TASKKILL_HARD_EXCLUDED_TYPES
            and manual != "__DISABLED__"
        )

        try:
            # -------------------- URI-style actions -------------------- #
            if action_type in ("spotify", "steam", "epic", "uri", "url"):
                os.startfile(target)
                msg = f"Launched {action.display_name} -> {target}"

                if track_this:
                    if manual:
                        image_name = os.path.basename(manual).strip()
                        if image_name:
                            self.active_processes[uid] = image_name
                            self.active_paths[uid] = target
                            self._log(f"Manual kill target: {image_name}")
                    elif stored_auto_process:
                        image_name = os.path.basename(stored_auto_process).strip()
                        if image_name:
                            self.active_processes[uid] = image_name
                            self.active_paths[uid] = target
                            self._log(f"Reusing auto-detected target: {image_name}")
                    elif (
                        self.auto_detect_enabled
                        and self._needs_auto_detection(action_type, target)
                    ):
                        self._schedule_auto_detection(uid, target, launch_pid=None)

            # -------------------- Direct executable -------------------- #
            elif action_type == "executable":
                if not os.path.exists(target):
                    return False, f"Executable file not found: {target}"

                working_dir = os.path.dirname(os.path.abspath(target))
                pid: Optional[int] = None
                is_wrapper = self._needs_auto_detection(action_type, target)

                if is_wrapper:
                    cmd_list = ["cmd", "/c", target]
                    if args:
                        cmd_list += shlex.split(args)
                    proc = subprocess.Popen(
                        cmd_list,
                        cwd=working_dir,
                        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                    )
                    pid = proc.pid
                elif target.lower().endswith(".lnk") or not args:
                    os.startfile(target)
                else:
                    cmd_list = [target] + shlex.split(args)
                    proc = subprocess.Popen(
                        cmd_list,
                        cwd=working_dir,
                        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                    )
                    pid = proc.pid

                msg = f"Launched executable: {os.path.basename(target)}"
                if args:
                    msg += f" with args [{args}]"

                if track_this:
                    if is_wrapper:
                        if manual:
                            image_name = os.path.basename(manual).strip()
                            if image_name:
                                self.active_processes[uid] = image_name
                                self.active_paths[uid] = target
                                self._log(f"Manual kill target: {image_name}")
                        elif stored_auto_process:
                            image_name = os.path.basename(stored_auto_process).strip()
                            if image_name:
                                self.active_processes[uid] = image_name
                                self.active_paths[uid] = target
                                self._log(f"Reusing auto-detected target: {image_name}")
                        elif self.auto_detect_enabled:
                            self._schedule_auto_detection(uid, target, launch_pid=pid)
                    else:
                        image_name = manual or os.path.basename(target)
                        self.active_processes[uid] = image_name
                        self.active_paths[uid] = target
                        if pid is not None:
                            self.active_pids[uid] = pid

            # -------------------- Shell command -------------------- #
            elif action_type in ("command", "cmd"):
                cmd_str = f'"{target}" {args}'.strip() if args else target
                proc = subprocess.Popen(cmd_str, shell=True)
                msg = f"Executed command: {cmd_str}"
                if track_this:
                    image_name = manual or os.path.basename(target) or target
                    self.active_processes[uid] = image_name
                    self.active_pids[uid] = proc.pid

            elif action_type == "text":
                return False, f"NFC tag contains text only (no action): '{target}'"

            else:
                if "://" in target or target.startswith("spotify:"):
                    os.startfile(target)
                    msg = f"Launched URI: {target}"
                elif os.path.exists(target):
                    os.startfile(target)
                    msg = f"Opened file: {target}"
                else:
                    return False, f"Unknown action type or unrecognized target: {target}"

            if uid:
                self.last_executed_uid = uid
                self.last_executed_time = time.time()

            return True, msg

        except Exception as e:
            return False, f"Execution failed: {str(e)}"

    # ------------------------------------------------------------------ #
    # Auto-detection scheduler
    # ------------------------------------------------------------------ #
    def _schedule_auto_detection(self, uid: str, target: str,
                                 launch_pid: Optional[int] = None):
        import threading

        before = self._snapshot_processes()
        delay = max(1, int(self.auto_detect_delay_seconds))

        self._log(f"Auto-detect scheduled for uid={uid} in {delay}s "
                  f"(launch_pid={launch_pid})")

        def _worker():
            time.sleep(delay)

            if self.current_present_uid != uid:
                self._log(f"Auto-detect cancelled: tag {uid} lifted before detection finished.")
                return

            after = self._snapshot_processes()
            winner = self._pick_game_process(before, after, launch_pid=launch_pid)
            if not winner:
                self._log("Auto-detect found no candidate process.")
                return

            self._log(f"Auto-detect resolved: {winner}")

            if self.current_present_uid != uid:
                self._log(f"Auto-detect discarded: tag {uid} lifted.")
                return

            self.active_processes[uid] = winner
            self.active_paths[uid] = target

            if self._on_auto_detected:
                try:
                    self._on_auto_detected(uid, winner)
                except Exception:
                    pass

        t = threading.Thread(target=_worker, name=f"autodetect-{uid}", daemon=True)
        t.start()

    # ------------------------------------------------------------------ #
    # Process termination
    # ------------------------------------------------------------------ #
    def kill_process_for_tag(
        self,
        uid: str,
        custom_process: Optional[str] = None,
        use_pid: bool = False,
    ) -> Tuple[bool, str]:
        image_name = custom_process or self.active_processes.get(uid)
        pid = self.active_pids.get(uid)

        if use_pid and pid is not None:
            try:
                cmd = ["taskkill", "/F", "/PID", str(pid), "/T"]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    self._clear_tracking(uid)
                    return True, f"Terminated PID {pid} (taskkill /F /PID {pid} /T)"
                err = res.stderr.strip() or res.stdout.strip()
                if not image_name:
                    return False, f"taskkill: {err}"
            except Exception as e:
                if not image_name:
                    return False, f"Error running taskkill: {e}"

        if not image_name:
            return False, "No active process recorded for this tag."

        image_name = os.path.basename(image_name).strip()
        if not image_name:
            return False, "Invalid process name."

        try:
            cmd = ["taskkill", "/F", "/IM", image_name, "/T"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                self._clear_tracking(uid)
                return True, f"Terminated {image_name} (taskkill /F /IM {image_name} /T)"
            else:
                err = res.stderr.strip() or res.stdout.strip()
                return False, f"taskkill: {err}"
        except Exception as e:
            return False, f"Error running taskkill: {e}"

    def _clear_tracking(self, uid: str):
        self.active_processes.pop(uid, None)
        self.active_pids.pop(uid, None)
        self.active_paths.pop(uid, None)

    def kill_all_tracked(self) -> Tuple[int, int]:
        killed = 0
        failed = 0
        all_uids = set(self.active_processes.keys()) | set(self.active_pids.keys())
        for uid in list(all_uids):
            ok, _ = self.kill_process_for_tag(uid)
            if ok:
                killed += 1
            else:
                failed += 1
        return killed, failed

    def is_tracking(self, uid: str) -> bool:
        return uid in self.active_processes or uid in self.active_pids

    def tracked_processes(self) -> Dict[str, str]:
        return dict(self.active_processes)
