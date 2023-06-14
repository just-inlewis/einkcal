#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from icalendar import Calendar
from pytz import timezone
import datetime
import logging

class CalHelper:

    def __init__(self):
        self.logger = logging.getLogger('maginkcal')

    def get_datetime(self, date, localTZ, offset=0):
        allDayEvent = False
        try:
            formattedDate = date.astimezone(localTZ)
        except:
            allDayEvent = True
            formattedDate = datetime.datetime(date.year, date.month, date.day + offset).astimezone(localTZ)
        return formattedDate, allDayEvent

    def is_multiday(self, start, end):
        # check if event stretches across multiple days
        return start.date() != end.date()

    def retrieve_events(self, calendar, startDate, endDate, localTZ, thresholdHours):
        r = requests.get(calendar)
        cal = Calendar.from_ical(r.text)
        events = []
        for event in cal.walk('VEVENT'):
            allDayEvent = False
            dtstart = event.get('DTSTART').dt
            dtend = event.get('DTEND').dt
            start, allDayEventS = self.get_datetime(dtstart, localTZ)
            # All day events are erroneously maked as 1 day longer than they actually are.
            end, allDayEventE = self.get_datetime(dtend, localTZ, offset=-1)
            if (startDate > end or endDate < end):
                continue

            events.append({
            'allday': allDayEventS or allDayEventE,
            'startDatetime': start,
            'endDatetime': end,
            'isMultiday': self.is_multiday(start, end),
            'summary': event.get('SUMMARY').to_ical().decode().strip()
            })
        return events
