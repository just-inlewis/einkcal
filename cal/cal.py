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

    def _has_mixed_naive_aware(self, event):
        dtstart_prop = event.get("DTSTART")
        dtend_prop = event.get("DTEND")
        if dtstart_prop is None or dtend_prop is None:
            return False
        start = dtstart_prop.dt
        end = dtend_prop.dt
        if not (
            isinstance(start, datetime.datetime)
            and isinstance(end, datetime.datetime)
        ):
            return False
        start_naive = (start.tzinfo is None)
        end_naive = (end.tzinfo is None)
        return start_naive != end_naive  # one naive, one aware

    def strip_bad_series(self, cal: Calendar):
        bad_uids = set()
        bad_events = []
        for event in cal.walk("VEVENT"):
            uid = str(event.get("UID", ""))
            if not uid:
                continue
            if self._has_mixed_naive_aware(event):
                bad_uids.add(uid)
                bad_events.append(event)
        if not bad_uids:
            return cal, bad_events
        new_cal = Calendar()
        for k, v in cal.items():
            new_cal.add(k, v)
        for component in cal.subcomponents:
            if component.name == "VEVENT":
                uid = str(component.get("UID", ""))
                if uid in bad_uids:
                    summary = component.get("SUMMARY")
                    try:
                        summary_txt = summary.to_ical().decode().strip()
                    except Exception:
                        summary_txt = str(summary)
                    print(f"Handling mixed-tz event manually UID={uid!r}, summary={summary_txt!r}")
                    continue
            new_cal.add_component(component)
        return new_cal, bad_events

    def retrieve_events(self, calendar, startDate, endDate, localTZ, thresholdHours):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=self.retry_strategy())
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        try:
            r = session.get(calendar, timeout=10)
            r.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Error fetching calendar: {e}")
            return []
        try:
            cal = Calendar.from_ical(r.content)
        except Exception as e:
            self.logger.error(f"Error parsing iCal data: {e}")
            return []
        events = []
        cal, bad_events = self.strip_bad_series(cal)
        try:
            occurrences = list(recurring_ical_events.of(cal).between(startDate, endDate))
        except Exception as e:
            self.logger.error(f"Error expanding recurring events: {e}")
            occurrences = list(cal.walk("VEVENT"))
        occurrences.extend(bad_events)
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
