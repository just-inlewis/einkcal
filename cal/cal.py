#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from icalendar import Calendar
from pytz import timezone
import recurring_ical_events
import datetime
import logging

class CalHelper:
    def __init__(self):
        self.logger = logging.getLogger('einkcal')

    def retry_strategy(self):
        return requests.adapters.Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            backoff_factor=2,
            allowed_methods=None,
        )

    def get_datetime(self, date, localTZ, offset=0):
        allDayEvent = False
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            allDayEvent = True
            dt_obj = datetime.datetime(date.year, date.month, date.day) + datetime.timedelta(days=offset)
            dt_obj = localTZ.localize(dt_obj)
        else:
            if date.tzinfo is None:
                dt_obj = localTZ.localize(date)
            else:
                dt_obj = date.astimezone(localTZ)
        return dt_obj, allDayEvent

    def is_multiday(self, start, end):
        return start.date() != end.date()

    def retrieve_events(self, calendar, startDate, endDate, localTZ, thresholdHours):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=self.retry_strategy())
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        try:
            r = session.get(calendar, timeout=10)
            r.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching calendar: {e}", file=sys.stderr)
            return []
        try:
            cal = Calendar.from_ical(r.content)
        except Exception as e:
            logger.error(f"Error parsing iCal data: {e}", file=sys.stderr)
            return []
        events = []
        try:
            occurrences = recurring_ical_events.of(cal).between(startDate, endDate)
        except Exception as e:
            logger.error(f"Error expanding recurring events: {e}", file=sys.stderr)
            occurrences = cal.walk("VEVENT")
        for event in occurrences:
            status = str(event.get("STATUS", "CONFIRMED")).upper()
            if status == "CANCELLED":
                continue
            dtstart_prop = event.get("DTSTART")
            if dtstart_prop is None:
                continue
            try:
                dtstart = dtstart_prop.dt
            except Exception:
                continue
            dtend_prop = event.get("DTEND")
            duration_prop = event.get("DURATION")
            dtend = None
            if dtend_prop is not None:
                try:
                    dtend = dtend_prop.dt
                except Exception:
                    dtend = None
            if dtend is None and duration_prop is not None:
                try:
                    dtend = dtstart + duration_prop.dt
                except Exception:
                    dtend = None
            if dtend is None:
                dtend = dtstart
            try:
                start, allDayEventS = self.get_datetime(dtstart, localTZ)
                end, allDayEventE = self.get_datetime(dtend, localTZ, offset=-1)
            except Exception:
                continue
            if end < startDate or start > endDate:
                continue
            summary_prop = event.get("SUMMARY")
            if summary_prop is not None:
                try:
                    summary = summary_prop.to_ical().decode().strip()
                except Exception:
                    summary = str(summary_prop)
            else:
                summary = ""

            events.append(
                {
                    "allday": allDayEventS or allDayEventE,
                    "startDatetime": start,
                    "endDatetime": end,
                    "isMultiday": self.is_multiday(start, end),
                    "summary": summary,
                }
            )

        return sorted(events, key=lambda x: x["startDatetime"])
