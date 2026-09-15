"""
NDEF message handler for NFC Card Launcher.
Encodes and decodes NFC Forum NDEF records and Type 2 TLV frames.
Specialized parser for Spotify URIs, Steam Game IDs, Executables, and Web URLs.
Supports an optional secondary "kill=1" text record for per-tag taskkill control.
"""

import os
import re
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional, Tuple

try:
    import ndef
except ImportError:
    ndef = None


KILL_FLAG_RECORD_TEXT = "kill=1"


class NdefAction:
    def __init__(
        self,
        action_type: str,
        target: str,
        display_name: str = "",
        args: str = "",
        raw_record: str = "",
        kill_on_removal: bool = False,
    ):
        self.action_type = action_type
        self.target = target
        self.args = args
        self.display_name = display_name or target
        self.raw_record = raw_record
        self.kill_on_removal = kill_on_removal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "args": self.args,
            "display_name": self.display_name,
            "raw_record": self.raw_record,
            "kill_on_removal": self.kill_on_removal,
        }

    def __repr__(self) -> str:
        return f"<NdefAction type={self.action_type} target={self.target} args={self.args} kill={self.kill_on_removal}>"


def parse_action_from_string(text: str) -> NdefAction:
    s = text.strip()

    # Spotify
    if s.lower().startswith("spotify:") or "open.spotify.com" in s.lower():
        if "open.spotify.com" in s.lower():
            name = "Spotify Web Link"
            if "/track/" in s:
                name = "Spotify Track"
            elif "/playlist/" in s:
                name = "Spotify Playlist"
            elif "/album/" in s:
                name = "Spotify Album"
            elif "/artist/" in s:
                name = "Spotify Artist"
            return NdefAction("spotify", s, display_name=name, raw_record=s)
        else:
            parts = s.split(":")
            category = parts[1].capitalize() if len(parts) > 1 else "Item"
            return NdefAction("spotify", s, display_name=f"Spotify {category}", raw_record=s)

    # Steam
    if s.lower().startswith("steam://"):
        m = re.search(r"rungameid/(\d+)", s, re.IGNORECASE)
        app_id = m.group(1) if m else ""
        name = f"Steam Game (App ID: {app_id})" if app_id else "Steam Action"
        return NdefAction("steam", s, display_name=name, raw_record=s)

    if "store.steampowered.com/app/" in s.lower():
        m = re.search(r"/app/(\d+)", s, re.IGNORECASE)
        if m:
            steam_uri = f"steam://rungameid/{m.group(1)}"
            return NdefAction("steam", steam_uri, display_name=f"Steam Game (App ID: {m.group(1)})", raw_record=s)

    # Executable / local file URI
    if s.lower().startswith("file:///"):
        parsed = urllib.parse.urlparse(s)
        file_path = urllib.request.url2pathname(parsed.path)
        if re.match(r"^\\+[a-zA-Z]:", file_path):
            file_path = file_path.lstrip("\\")
        file_path = os.path.normpath(file_path)
        base_name = os.path.basename(file_path)
        return NdefAction("executable", file_path, display_name=f"Run {base_name}", raw_record=s)

    if s.lower().startswith("file://"):
        file_path = s[7:]
        file_path = urllib.parse.unquote(file_path)
        if file_path.startswith("/") and len(file_path) > 2 and file_path[2] == ":":
            file_path = file_path[1:]
        file_path = os.path.normpath(file_path)
        base_name = os.path.basename(file_path)
        return NdefAction("executable", file_path, display_name=f"Run {base_name}", raw_record=s)

    if s.lower().startswith("file:/") or s.lower().startswith("file:\\"):
        file_path = s[5:].lstrip("/\\")
        file_path = urllib.parse.unquote(file_path)
        file_path = os.path.normpath(file_path)
        base_name = os.path.basename(file_path)
        return NdefAction("executable", file_path, display_name=f"Run {base_name}", raw_record=s)

    for prefix in ("launch:", "run:", "app:", "exe:"):
        if s.lower().startswith(prefix):
            remainder = s[len(prefix):].strip()
            parts = _split_path_and_args(remainder)
            base_name = os.path.basename(parts[0])
            return NdefAction("executable", parts[0], args=parts[1], display_name=f"Run {base_name}", raw_record=s)

    if _is_executable_string(s):
        exe_path, args = _split_path_and_args(s)
        base_name = os.path.basename(exe_path)
        return NdefAction("executable", exe_path, args=args, display_name=f"Run {base_name}", raw_record=s)

    # Generic URI
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
        parsed = urllib.parse.urlparse(s)
        scheme = parsed.scheme.lower()
        if scheme in ("http", "https"):
            name = f"Web Link: {parsed.netloc}"
            return NdefAction("uri", s, display_name=name, raw_record=s)
        else:
            return NdefAction("uri", s, display_name=f"{scheme.capitalize()} Link", raw_record=s)

    return NdefAction("text", s, display_name="Text Content", raw_record=s)


def _is_executable_string(s: str) -> bool:
    lower = s.lower()
    for ext in (".exe", ".bat", ".cmd", ".lnk", ".ps1", ".vbs"):
        if ext in lower:
            return True
    if re.match(r'^["]?[a-zA-Z]:[\\/]', s):
        return True
    return False


def _split_path_and_args(cmd: str) -> Tuple[str, str]:
    cmd = cmd.strip()
    if cmd.startswith('"'):
        end_idx = cmd.find('"', 1)
        if end_idx != -1:
            exe_path = cmd[1:end_idx]
            args = cmd[end_idx + 1:].strip()
            return exe_path, args

    if os.path.exists(cmd):
        return cmd, ""

    parts = cmd.split(" ", 1)
    if len(parts) == 2 and (os.path.exists(parts[0]) or any(parts[0].lower().endswith(x) for x in (".exe", ".bat", ".cmd", ".lnk"))):
        return parts[0], parts[1].strip()

    return cmd, ""


def extract_ndef_from_tag_bytes(raw_memory: bytes) -> Optional[bytes]:
    i = 0
    length_mem = len(raw_memory)
    while i < length_mem:
        tag_type = raw_memory[i]
        if tag_type == 0x00:
            i += 1
            continue
        elif tag_type == 0xFE:
            break
        elif tag_type == 0x03:
            if i + 1 >= length_mem:
                break
            len_byte = raw_memory[i + 1]
            if len_byte != 0xFF:
                ndef_len = len_byte
                start = i + 2
                end = start + ndef_len
                if end <= length_mem:
                    return raw_memory[start:end]
                else:
                    return raw_memory[start:]
            else:
                if i + 3 >= length_mem:
                    break
                ndef_len = (raw_memory[i + 2] << 8) | raw_memory[i + 3]
                start = i + 4
                end = start + ndef_len
                if end <= length_mem:
                    return raw_memory[start:end]
                else:
                    return raw_memory[start:]
        elif tag_type in (0x01, 0x02):
            if i + 1 >= length_mem:
                break
            tlv_len = raw_memory[i + 1]
            i += 2 + tlv_len
        else:
            if i + 1 < length_mem:
                tlv_len = raw_memory[i + 1]
                i += 2 + tlv_len
            else:
                break
    return None


def get_safe_record_uri(record) -> str:
    if hasattr(record, "iri"):
        try:
            val = record.iri
            if val:
                return val
        except Exception:
            pass
    try:
        return record.uri
    except Exception:
        pass
    return str(record)


def parse_ndef_message(ndef_bytes: bytes) -> List[NdefAction]:
    if not ndef:
        raise RuntimeError("ndeflib is not installed")

    actions: List[NdefAction] = []
    records = []
    try:
        records = list(ndef.message_decoder(ndef_bytes))
    except Exception as e:
        print(f"[NDEF] Error decoding NDEF message with ndeflib: {e}")
        return _fallback_parse_raw_ndef(ndef_bytes)

    kill_flag_seen = False

    for record in records:
        try:
            if isinstance(record, ndef.UriRecord):
                safe_uri = get_safe_record_uri(record)
                action = parse_action_from_string(safe_uri)
                action.raw_record = f"URI: {safe_uri}"
                actions.append(action)
            elif isinstance(record, ndef.TextRecord):
                text_val = (record.text or "").strip()
                if text_val.lower() == KILL_FLAG_RECORD_TEXT:
                    kill_flag_seen = True
                    continue
                action = parse_action_from_string(text_val)
                action.raw_record = f"Text: {text_val}"
                actions.append(action)
            else:
                rec_str = str(record)
                actions.append(NdefAction("unknown", rec_str, display_name=record.type, raw_record=rec_str))
        except Exception as rec_err:
            print(f"[NDEF] Error processing record: {rec_err}")

    if kill_flag_seen:
        for a in actions:
            a.kill_on_removal = True

    if not actions:
        return _fallback_parse_raw_ndef(ndef_bytes)

    return actions


def _fallback_parse_raw_ndef(ndef_bytes: bytes) -> List[NdefAction]:
    actions = []
    kill_flag_seen = False

    try:
        idx = 0
        while idx < len(ndef_bytes) - 3:
            if ndef_bytes[idx] in (0x54, 0x55) and idx > 0:
                type_char = chr(ndef_bytes[idx])
                payload_start = idx + 1
                raw_payload = ndef_bytes[payload_start:]
                if type_char == 'U' and len(raw_payload) > 1:
                    code = raw_payload[0]
                    prefixes = {
                        0: "", 1: "http://www.", 2: "https://www.", 3: "http://", 4: "https://",
                        0x1D: "file://", 0x1E: "file:///"
                    }
                    prefix = prefixes.get(code, "")
                    uri_str = prefix + raw_payload[1:].decode("utf-8", errors="ignore").split("\xfe")[0].split("\x00")[0]
                    if uri_str.strip():
                        act = parse_action_from_string(uri_str.strip())
                        act.raw_record = f"Raw URI: {uri_str.strip()}"
                        actions.append(act)
                elif type_char == 'T' and len(raw_payload) > 2:
                    status = raw_payload[0]
                    lang_len = status & 0x3F
                    text_bytes = raw_payload[1 + lang_len:].split(b"\xfe")[0].split(b"\x00")[0]
                    text_str = text_bytes.decode("utf-8", errors="ignore").strip()
                    if text_str.lower() == KILL_FLAG_RECORD_TEXT:
                        kill_flag_seen = True
                    elif text_str:
                        act = parse_action_from_string(text_str)
                        act.raw_record = f"Raw Text: {text_str}"
                        actions.append(act)
            idx += 1
    except Exception as ex:
        print(f"[NDEF] Fallback scanner error: {ex}")

    if kill_flag_seen:
        for a in actions:
            a.kill_on_removal = True

    if not actions:
        try:
            raw_text = ndef_bytes.decode("utf-8", errors="ignore").strip()
            if raw_text:
                actions.append(parse_action_from_string(raw_text))
        except Exception:
            pass

    return actions


def encode_action_to_type2_tlv(
    action_type: str,
    target: str,
    args: str = "",
    use_file_uri: bool = True,
    kill_on_removal: bool = False,
) -> bytes:
    if not ndef:
        raise RuntimeError("ndeflib is not installed")

    records = []
    target = target.strip()
    args = args.strip()

    if action_type == "spotify":
        records.append(ndef.UriRecord(target))

    elif action_type == "steam":
        if target.isdigit():
            target = f"steam://rungameid/{target}"
        elif "store.steampowered.com/app/" in target:
            m = re.search(r"/app/(\d+)", target)
            if m:
                target = f"steam://rungameid/{m.group(1)}"
        records.append(ndef.UriRecord(target))

    elif action_type == "executable":
        if use_file_uri and not args:
            clean_path = target.replace("\\", "/")
            if not clean_path.startswith("/"):
                clean_path = "/" + clean_path
            file_uri = f"file://{urllib.parse.quote(clean_path)}"
            records.append(ndef.UriRecord(file_uri))
        else:
            full_cmd = f'"{target}" {args}' if args else target
            records.append(ndef.TextRecord(full_cmd))

    elif action_type in ("uri", "url"):
        records.append(ndef.UriRecord(target))

    elif action_type in ("text", "command"):
        full_text = f"{target} {args}".strip() if args else target
        records.append(ndef.TextRecord(full_text))

    else:
        if "://" in target or target.startswith("spotify:"):
            records.append(ndef.UriRecord(target))
        else:
            records.append(ndef.TextRecord(target))

    if kill_on_removal:
        records.append(ndef.TextRecord(KILL_FLAG_RECORD_TEXT))

    ndef_bytes = b"".join(ndef.message_encoder(records))

    ndef_len = len(ndef_bytes)
    if ndef_len < 255:
        tlv = bytes([0x03, ndef_len]) + ndef_bytes + bytes([0xFE])
    else:
        tlv = bytes([0x03, 0xFF, (ndef_len >> 8) & 0xFF, ndef_len & 0xFF]) + ndef_bytes + bytes([0xFE])

    remainder = len(tlv) % 4
    if remainder != 0:
        tlv += b"\x00" * (4 - remainder)

    return tlv