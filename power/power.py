#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script exposes the functions to interface with PiSugar. Mainly to retrieve the current battery level and also
to trigger the syncing of the PiSugar
"""

from pisugar import *
import socket
import logging

HOST = "127.0.0.1"
PORT = 8423

class PowerHelper:
    def __init__(self):
        self.logger = logging.getLogger('einkcal')
        conn, event_conn = connect_tcp("127.0.0.1", 8423)
        self.pisugar = PiSugarServer(conn, event_conn)

    def sync_time(self) -> None:
        self.pisugar.rtc_web()

    def get_battery(self) -> float:
        return self.pisugar.get_battery_level()

    def is_charging(self) -> bool:
        return self.pisugar.get_battery_power_plugged()
