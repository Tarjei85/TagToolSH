"""
ACR122U NFC Reader worker and hardware communication module.
Communicates via PC/SC (pyscard) in a PySide6 QThread.
Handles reader detection, card tap/removal, Type 2 NDEF reading,
Type 2 NDEF writing, and hardware buzzer feedback.

Buzzer strategy:
  - At reader connect, attempt to disable the firmware auto-beep on
    card detection and card removal.
  - App-controlled beeps: one on successful read, one on successful write.
  - On write failure: three rapid beeps regardless of the buzzer setting.

Shutdown strategy:
  - stop() sets flags only (no blocking wait).
  - run() checks stop_requested at the top of every iteration and exits promptly.
  - MainWindow._shutdown_worker() does the bounded wait / force-terminate.

Detection deduplication:
  - _emit_detected suppresses repeated emissions for the same UID within
    DETECT_DEDUPE_SEC.
  - _emit_removed suppresses repeated removals for the same UID within
    REMOVAL_DEDUPE_SEC.
  - Removals are delayed by REMOVAL_GRACE_SEC to avoid false positives from
    transient PC/SC disconnects.
"""

import time
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import QThread, Signal

from smartcard.System import readers
from smartcard.Exceptions import NoCardException, CardConnectionException

from ndef_handler import extract_ndef_from_tag_bytes, parse_ndef_message


REMOVAL_GRACE_SEC = 0.35
DETECT_DEDUPE_SEC = 1.0
REMOVAL_DEDUPE_SEC = 1.0


class NFCWorker(QThread):
    reader_status_changed = Signal(bool, str)
    tag_detected = Signal(dict)
    tag_removed = Signal(str)
    write_progress = Signal(str)
    write_completed = Signal(bool, str)
    log_event = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.stop_requested = False
        self.reader_name: Optional[str] = None
        self.is_reader_connected = False
        self.active_card_uid: Optional[str] = None
        self.buzzer_on_tap = True
        self.buzzer_on_write = True

        self.pending_write: Optional[bytes] = None
        self._write_lock = False
        self._firmware_beep_disabled = False

        self._last_detected_uid: Optional[str] = None
        self._last_detected_time: float = 0.0
        self._last_removed_uid: Optional[str] = None
        self._last_removed_time: float = 0.0
        self._card_missing_since: Optional[float] = None

    def stop(self):
        """Non-blocking stop. The caller is responsible for wait/terminate."""
        self.stop_requested = True
        self.running = False

    def queue_write(self, tlv_payload: bytes):
        self.pending_write = tlv_payload
        self.log_event.emit("info", "Write task queued. Waiting for NFC tag on reader...")

    def cancel_write(self):
        self.pending_write = None
        self.log_event.emit("info", "Write task cancelled.")

    # ---------- dedup helpers ---------- #

    def _emit_detected(self, info: dict):
        uid = info.get("uid", "")
        now = time.time()

        if (
            uid == self._last_detected_uid
            and (now - self._last_detected_time) < DETECT_DEDUPE_SEC
        ):
            return

        self._last_detected_uid = uid
        self._last_detected_time = now
        self._card_missing_since = None
        self.tag_detected.emit(info)

    def _emit_removed(self, uid: str):
        now = time.time()
        if (
            uid == self._last_removed_uid
            and (now - self._last_removed_time) < REMOVAL_DEDUPE_SEC
        ):
            return

        self._last_removed_uid = uid
        self._last_removed_time = now
        self._last_detected_uid = None
        self.tag_removed.emit(uid)

    def _handle_removal_candidate(self):
        if self.active_card_uid is None:
            return

        now = time.time()
        if self._card_missing_since is None:
            self._card_missing_since = now
            return

        if (now - self._card_missing_since) < REMOVAL_GRACE_SEC:
            return

        removed_uid = self.active_card_uid
        self.active_card_uid = None
        self._card_missing_since = None
        self._emit_removed(removed_uid)
        self.log_event.emit("info", f"Tag removed: {removed_uid}")

    # ---------- main loop ---------- #

    def run(self):
        active_connection = None

        while self.running and not self.stop_requested:
            try:
                available = readers()
                if not available:
                    if self.is_reader_connected:
                        self.is_reader_connected = False
                        self.reader_name = None
                        self._firmware_beep_disabled = False
                        self.reader_status_changed.emit(False, "No RFID/NFC reader found")
                        self.log_event.emit("warning", "NFC Reader disconnected")
                    active_connection = None
                    self.active_card_uid = None
                    self._card_missing_since = None
                    time.sleep(1.0)
                    continue

                chosen_reader = None
                for r in available:
                    if "ACR122" in str(r).upper():
                        chosen_reader = r
                        break
                if not chosen_reader:
                    chosen_reader = available[0]

                current_name = str(chosen_reader)
                if not self.is_reader_connected or self.reader_name != current_name:
                    self.is_reader_connected = True
                    self.reader_name = current_name
                    self._firmware_beep_disabled = False
                    self.reader_status_changed.emit(True, self.reader_name)
                    self.log_event.emit("info", f"Connected to reader: {self.reader_name}")

                if active_connection is None:
                    try:
                        conn = chosen_reader.createConnection()
                        conn.connect()
                        active_connection = conn
                        if not self._firmware_beep_disabled:
                            self._disable_firmware_beeps(active_connection)
                            self._firmware_beep_disabled = True
                        self._card_missing_since = None
                        self._handle_card_connected(active_connection)
                    except (NoCardException, CardConnectionException):
                        active_connection = None
                        self._handle_removal_candidate()
                    except Exception:
                        active_connection = None

                else:
                    try:
                        uid_data, sw1, sw2 = active_connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                        if sw1 != 0x90:
                            raise CardConnectionException("Card returned non-9000 status")

                        self._card_missing_since = None

                        if self.pending_write is not None:
                            tlv = self.pending_write
                            self.pending_write = None
                            self._execute_write_to_card(active_connection, tlv)

                    except (CardConnectionException, NoCardException):
                        active_connection = None
                        self._handle_removal_candidate()
                    except Exception:
                        active_connection = None
                        self.active_card_uid = None

            except Exception as outer_err:
                self.log_event.emit("error", f"Reader worker loop error: {outer_err}")

            # Short sleep so stop_requested is noticed promptly
            time.sleep(0.15)

    # ---------- hardware ---------- #

    def _disable_firmware_beeps(self, connection):
        variants = [
            [0xFF, 0x00, 0x52, 0x00, 0x00],
            [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x32, 0x00, 0x00],
            [0xFF, 0x00, 0x00, 0x00, 0x04, 0xD4, 0x32, 0x01, 0x00],
        ]
        for apdu in variants:
            try:
                connection.transmit(apdu)
            except Exception:
                pass

    def _handle_card_connected(self, connection):
        try:
            uid_data, sw1, sw2 = connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
            if sw1 != 0x90:
                self.log_event.emit("warning", f"Failed to read card UID (SW: {hex(sw1)} {hex(sw2)})")
                return

            uid_hex = ":".join(f"{b:02X}" for b in uid_data)
            self.active_card_uid = uid_hex

            atr_bytes = connection.getATR()
            atr_hex = ":".join(f"{b:02X}" for b in atr_bytes)

            tag_type, capacity = self._identify_tag(connection, atr_bytes)

            if self.pending_write is not None:
                tlv = self.pending_write
                self.pending_write = None
                self._execute_write_to_card(connection, tlv)
                return

            ndef_bytes = self._read_type2_ndef(connection, capacity)
            actions = []
            if ndef_bytes:
                try:
                    actions = [a.to_dict() for a in parse_ndef_message(ndef_bytes)]
                except Exception as parse_err:
                    self.log_event.emit("warning", f"NDEF parse notice: {parse_err}")

            if self.buzzer_on_tap:
                self._beep_reader(connection, repetitions=1)

            info = {
                "uid": uid_hex,
                "atr": atr_hex,
                "tag_type": tag_type,
                "capacity_bytes": capacity,
                "has_ndef": bool(ndef_bytes),
                "ndef_bytes_len": len(ndef_bytes) if ndef_bytes else 0,
                "actions": actions,
            }

            self._emit_detected(info)
            self.log_event.emit("success", f"Tag detected: {uid_hex} [{tag_type}] with {len(actions)} action(s)")

        except Exception as e:
            self.log_event.emit("error", f"Error reading card: {e}")

    def _identify_tag(self, connection, atr: List[int]) -> Tuple[str, int]:
        tag_type = "NFC Tag (ISO 14443A)"
        capacity = 144

        atr_str = bytes(atr).hex().upper()
        if "0001" in atr_str:
            return "MIFARE Classic 1K", 752
        elif "0002" in atr_str:
            return "MIFARE Classic 4K", 3356
        elif "0003" in atr_str:
            try:
                cc_data, sw1, sw2 = connection.transmit([0xFF, 0xB0, 0x00, 0x03, 0x04])
                if sw1 == 0x90 and len(cc_data) == 4 and cc_data[0] == 0xE1:
                    cc_size = cc_data[2]
                    capacity = cc_size * 8
                    if cc_size == 0x12:
                        return "NTAG213", 144
                    elif cc_size == 0x3E:
                        return "NTAG215", 504
                    elif cc_size == 0x6D:
                        return "NTAG216", 888
                    elif cc_size == 0x06:
                        return "MIFARE Ultralight", 48
                    else:
                        return f"NTAG (Size: {capacity}B)", capacity
            except Exception:
                pass
            return "NTAG / Ultralight", 144

        return tag_type, capacity

    def _read_type2_ndef(self, connection, capacity: int) -> Optional[bytes]:
        try:
            max_pages = min(225, (capacity // 4) + 6)
            raw_memory = bytearray()

            page = 4
            while page < max_pages:
                data, sw1, sw2 = connection.transmit([0xFF, 0xB0, 0x00, page, 0x10])
                if sw1 == 0x90 and len(data) == 16:
                    raw_memory.extend(data)
                    if 0xFE in data:
                        break
                    page += 4
                else:
                    data4, sw1_4, sw2_4 = connection.transmit([0xFF, 0xB0, 0x00, page, 0x04])
                    if sw1_4 == 0x90 and len(data4) == 4:
                        raw_memory.extend(data4)
                        if 0xFE in data4:
                            break
                        page += 1
                    else:
                        break

            if raw_memory:
                return extract_ndef_from_tag_bytes(bytes(raw_memory))

        except Exception as e:
            self.log_event.emit("warning", f"Could not read Type 2 NDEF: {e}")

        return None

    def _execute_write_to_card(self, connection, tlv: bytes):
        try:
            self.write_progress.emit("Verifying tag compatibility...")
            cc_data, sw1, sw2 = connection.transmit([0xFF, 0xB0, 0x00, 0x03, 0x04])
            if sw1 != 0x90:
                raise RuntimeError(f"Cannot read Capability Container (SW: {hex(sw1)} {hex(sw2)})")

            if cc_data[0] != 0xE1:
                self.write_progress.emit("Initializing Capability Container...")
                size_byte = max(0x12, (len(tlv) + 15) // 8)
                init_cc = [0xFF, 0xD6, 0x00, 0x03, 0x04, 0xE1, 0x10, size_byte, 0x00]
                res, s1, s2 = connection.transmit(init_cc)
                if s1 != 0x90:
                    raise RuntimeError("Failed to initialize CC page.")

            capacity = cc_data[2] * 8 if cc_data[0] == 0xE1 else 144
            if len(tlv) > capacity and capacity > 0:
                raise RuntimeError(f"Payload size ({len(tlv)} bytes) exceeds tag capacity ({capacity} bytes)!")

            num_pages = len(tlv) // 4
            self.write_progress.emit(f"Writing {len(tlv)} bytes ({num_pages} pages)...")

            for i in range(num_pages):
                page_num = 4 + i
                chunk = list(tlv[i * 4 : (i + 1) * 4])

                apdu = [0xFF, 0xD6, 0x00, page_num, 0x04] + chunk
                res, s1, s2 = connection.transmit(apdu)

                if s1 != 0x90:
                    fallback_apdu = [0xFF, 0x00, 0x00, 0x00, 0x07, 0xD4, 0x42, 0xA2, page_num] + chunk
                    res, s1, s2 = connection.transmit(fallback_apdu)
                    if s1 != 0x90:
                        raise RuntimeError(f"Failed to write page {page_num} (SW: {hex(s1)} {hex(s2)}). Tag may be locked.")

                self.write_progress.emit(f"Wrote page {i+1} of {num_pages}...")

            self.write_progress.emit("Verifying written data on card...")
            for i in range(num_pages):
                page_num = 4 + i
                expected = list(tlv[i * 4 : (i + 1) * 4])
                read_res, s1, s2 = connection.transmit([0xFF, 0xB0, 0x00, page_num, 0x04])
                if s1 != 0x90 or read_res != expected:
                    raise RuntimeError(f"Verification failed at page {page_num}!")

            if self.buzzer_on_write:
                self._beep_reader(connection, repetitions=1)

            success_msg = f"Successfully encoded and verified {len(tlv)} bytes on tag {self.active_card_uid}!"
            self.write_completed.emit(True, success_msg)
            self.log_event.emit("success", success_msg)

            self._last_detected_uid = None
            self._handle_card_connected(connection)

        except Exception as err:
            err_msg = str(err)
            try:
                self._beep_reader(connection, repetitions=3)
            except Exception:
                pass
            self.write_completed.emit(False, err_msg)
            self.log_event.emit("error", f"Write failed: {err_msg}")

    def _beep_reader(self, connection, repetitions: int = 1):
        try:
            apdu = [0xFF, 0x00, 0x40, 0x00, 0x04, 0x01, 0x00, repetitions, 0x01]
            connection.transmit(apdu)
        except Exception:
            pass

    def trigger_test_beep(self):
        try:
            available = readers()
            if available:
                r = available[0]
                c = r.createConnection()
                c.connect()
                self._beep_reader(c, repetitions=1)
        except Exception:
            pass