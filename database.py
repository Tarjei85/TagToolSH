"""
Database and settings manager for TagToolSH!.
Handles persistence of user settings and custom UID-to-Action mappings.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "auto_launch": True,
    "confirm_exe": False,
    "debounce_seconds": 2.5,
    "buzzer_on_tap": True,
    "buzzer_on_write": True,
    "preferred_reader": "",
    "minimize_to_tray": True,
    "launch_on_boot": False,
    "kill_on_removal": False,
    "kill_all_on_shutdown": False,
    "read_only_mode": False,
    "bsod_on_kill": True,
    "bsod_duration_seconds": 60,
    "start_maximized": True,
    # Auto-detection of launcher-spawned game processes
    "auto_detect_enabled": True,
    "auto_detect_delay_seconds": 15,
}


class DatabaseManager:
    def __init__(self, base_dir: Optional[str] = None, internal_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir
        self.internal_dir = internal_dir or base_dir

        self.app_data_dir = os.path.join(self.base_dir, "app_data")
        os.makedirs(self.app_data_dir, exist_ok=True)

        self.config_path = os.path.join(self.app_data_dir, "config.json")
        self.tags_db_path = os.path.join(self.app_data_dir, "tags_db.json")

        self._migrate_legacy_files()

        self.config: Dict[str, Any] = {}
        self.tags: Dict[str, Dict[str, Any]] = {}

        self.load_all()

    def _migrate_legacy_files(self):
        old_config = os.path.join(self.base_dir, "config.json")
        if os.path.exists(old_config) and not os.path.exists(self.config_path):
            try:
                import shutil
                shutil.move(old_config, self.config_path)
            except Exception:
                pass

        old_tags = os.path.join(self.base_dir, "tags_db.json")
        if os.path.exists(old_tags) and not os.path.exists(self.tags_db_path):
            try:
                import shutil
                shutil.move(old_tags, self.tags_db_path)
            except Exception:
                pass

    def load_all(self):
        self.load_config()
        self.load_tags()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = {**DEFAULT_CONFIG, **data}
            except Exception as e:
                print(f"[DB] Error loading config: {e}. Using defaults.")
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[DB] Error saving config: {e}")

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set_setting(self, key: str, value: Any):
        self.config[key] = value
        self.save_config()

    def load_tags(self):
        if os.path.exists(self.tags_db_path):
            try:
                with open(self.tags_db_path, "r", encoding="utf-8") as f:
                    self.tags = json.load(f)
            except Exception as e:
                print(f"[DB] Error loading tags DB: {e}")
                self.tags = {}
        else:
            self.tags = {}
            self.save_tags()

    def save_tags(self):
        try:
            with open(self.tags_db_path, "w", encoding="utf-8") as f:
                json.dump(self.tags, f, indent=2)
        except Exception as e:
            print(f"[DB] Error saving tags DB: {e}")

    def normalize_uid(self, uid: str) -> str:
        clean = uid.replace(":", "").replace(" ", "").replace("-", "").upper()
        if len(clean) % 2 == 0:
            return ":".join(clean[i:i+2] for i in range(0, len(clean), 2))
        return uid.upper()

    def get_tag_mapping(self, uid: str) -> Optional[Dict[str, Any]]:
        norm_uid = self.normalize_uid(uid)
        return self.tags.get(norm_uid)

    def save_tag_mapping(self, uid: str, tag_data: Dict[str, Any]):
        norm_uid = self.normalize_uid(uid)
        now_str = datetime.now().isoformat()
        if norm_uid not in self.tags:
            tag_data["created_at"] = now_str
        tag_data["updated_at"] = now_str
        tag_data.setdefault("kill_on_removal", False)
        tag_data.setdefault("auto_detected_process", "")
        self.tags[norm_uid] = tag_data
        self.save_tags()

    def record_tag_used(self, uid: str):
        norm_uid = self.normalize_uid(uid)
        if norm_uid in self.tags:
            self.tags[norm_uid]["last_used"] = datetime.now().isoformat()
            self.save_tags()

    def set_auto_detected_process(self, uid: str, process_name: str):
        """
        Records an auto-detected game process name for this UID.
        Never touches process_to_kill (manual override).
        """
        norm_uid = self.normalize_uid(uid)
        if norm_uid not in self.tags:
            # Create a minimal stub so auto-detection persists even without a
            # full library entry. The user can edit it later.
            self.tags[norm_uid] = {
                "uid": norm_uid,
                "name": "Auto-detected tag",
                "action_type": "uri",
                "target": "",
                "args": "",
                "process_to_kill": "",
                "auto_detected_process": process_name,
                "kill_on_removal": False,
                "created_at": datetime.now().isoformat(),
            }
        else:
            self.tags[norm_uid]["auto_detected_process"] = process_name
        self.tags[norm_uid]["updated_at"] = datetime.now().isoformat()
        self.save_tags()

    def delete_tag_mapping(self, uid: str) -> bool:
        norm_uid = self.normalize_uid(uid)
        if norm_uid in self.tags:
            del self.tags[norm_uid]
            self.save_tags()
            return True
        return False

    def get_all_tags(self) -> Dict[str, Dict[str, Any]]:
        return self.tags.copy()
