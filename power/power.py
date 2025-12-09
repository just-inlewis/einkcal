#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script exposes the functions to interface with PiSugar. Mainly to retrieve the current battery level and also
to trigger the syncing of the PiSugar
"""

import socket
import logging

HOST = "127.0.0.1"
PORT = 8423

class PowerHelper:
    def __init__(self):
        self.logger = logging.getLogger('einkcal')

    @staticmethod
    def send_pisugar_cmd(cmd: str, timeout: float = 2.0) -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((HOST, PORT))
            s.sendall((cmd + "\n").encode("utf-8"))
            s.shutdown(socket.SHUT_WR)

            buf = b""
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break

        line = buf.split(b"\n", 1)[0]
        return line.decode("utf-8", errors="replace").strip()

    def get_battery(self) -> float:
        try:
            result_str = self.send_pisugar_cmd("get battery")
            parts = result_str.split()
            battery_str = parts[-1]
            battery_float = float(battery_str)
            return battery_float
        except Exception as e:
            self.logger.info(f"Invalid battery output: {e}")
            return -1.0

    def is_charging(self) -> bool:
        try:
            result_str = self.send_pisugar_cmd("get battery_power_plugged")
            return result_str.lower() == "true"
        except Exception as e:
            self.logger.info(f"Invalid status: {e}")
            return False

    def sync_time(self) -> None:
        try:
            resp = self.send_pisugar_cmd("rtc_pi2rtc", timeout=2.0)
            self.logger.info(f"rtc_pi2rtc response: {resp}")
        except (socket.timeout, OSError) as e:
            self.logger.error(f"Time sync failed: {e!r}")
