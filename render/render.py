#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import timedelta
import pathlib
from PIL import Image
import logging
import subprocess
import math

class RenderHelper:

    def __init__(self, width, height, angle):
        self.logger = logging.getLogger('einkcal')
        self.currPath = str(pathlib.Path(__file__).parent.absolute())
        self.htmlFile = self.currPath + '/calendar.html'
        self.imageWidth = width
        self.imageHeight = height
        self.rotateAngle = angle

    def get_screenshot(self, red):
        if red:
            name = '/calendar_red.png'
        else:
            name = '/calendar_black.png'
        result = subprocess.check_output(['wkhtmltoimage', 
                                          '--enable-local-file-access',
                                          '--height',
                                          '1304',
                                          '--width',
                                          '984',
                                          self.htmlFile,
                                          self.currPath + name
                                          ])
        result_str = result.decode('utf-8').rstrip()
        self.logger.info(result_str)
        self.logger.info('Screenshot captured and saved to file.')
        img = Image.open(self.currPath + name)  # get image)
        img = img.rotate(self.rotateAngle, expand=True)
        return img

    def get_day_in_cal(self, startDate, eventDate):
        delta = eventDate - startDate
        return delta.days

    def get_short_time(self, datetimeObj):
        datetime_str = ''
        if datetimeObj.minute > 0:
            datetime_str = ':{:02d}'.format(datetimeObj.minute)

        if datetimeObj.hour == 0:
            datetime_str = '12{}am'.format(datetime_str)
        elif datetimeObj.hour == 12:
            datetime_str = '12{}pm'.format(datetime_str)
        elif datetimeObj.hour > 12:
            datetime_str = '{}{}pm'.format(str(datetimeObj.hour % 12), datetime_str)
        else:
            datetime_str = '{}{}am'.format(str(datetimeObj.hour), datetime_str)
        return datetime_str

    def process_inputs(self, calDict, weatherDict, red=False):
        # calDict = {'events': eventList, 'calStartDate': calStartDate, 'today': currDate, 'lastRefresh': currDatetime, 'batteryLevel': batteryLevel}
        # weatherDict = {'high': 75, "low": 55, "pop": 10, "id": 501}
        # first setup list to represent the 5 weeks in our calendar
        calList = []
        for i in range(35):
            calList.append([])

        # retrieve calendar configuration
        maxEventsPerDay = calDict['maxEventsPerDay']
        batteryDisplayMode = calDict['batteryDisplayMode']
        dayOfWeekText = calDict['dayOfWeekText']
        weekStartDay = calDict['weekStartDay']

        # for each item in the eventList, add them to the relevant day in our calendar list
        for event in calDict['events']:
            idx = self.get_day_in_cal(calDict['calStartDate'], event['startDatetime'].date())
            if idx >= 0:
                calList[idx].append(event)
            if event['isMultiday']:
                idx = self.get_day_in_cal(calDict['calStartDate'], event['endDatetime'].date())
                if idx < len(calList):
                    calList[idx].append(event)

        # Read html template
        with open(self.currPath + '/calendar_template.html', 'r') as file:
            calendar_template = file.read()

        # Insert month header
        month_name = str(calDict['today'].month)

        # Insert battery icon
        # batteryDisplayMode - 0: do not show / 1: always show / 2: show when battery is low
        battLevel = calDict['batteryLevel']

        if batteryDisplayMode == 0:
            battText = 'batteryHide'
        elif batteryDisplayMode == 1:
            if battLevel >= 80:
                battText = 'battery80'
            elif battLevel >= 60:
                battText = 'battery60'
            elif battLevel >= 40:
                battText = 'battery40'
            elif battLevel >= 20:
                battText = 'battery20'
            elif battLevel < 12:
                battText = 'battery0'

        elif batteryDisplayMode == 2 and battLevel < 20.0:
            battText = 'battery0'
        elif batteryDisplayMode == 2 and battLevel >= 20.0:
            battText = 'batteryHide'
        if red:
            battText = 'batteryHide'

        # Populate the day of week row
        cal_days_of_week = ''
        for i in range(0, 7):
            cal_days_of_week += '<li class="{0}">{1}</li>\n'.format("text-uppercase-white" if red else "text-uppercase", dayOfWeekText[
                (i + weekStartDay) % 7])

        # Populate the date and events
        cal_events_text = ''
        for i in range(len(calList)):
            currDate = calDict['calStartDate'] + timedelta(days=i)
            dayOfMonth = currDate.day
            if currDate == calDict['today']:
                cal_events_text += '<li><div class="{0}">{1}</div>\n'.format("datecircle" if red else "datecircle-white", str(dayOfMonth))
            elif currDate.month != calDict['today'].month:
                cal_events_text += '<li><div class="date {0}">{1}</div>\n'.format("text-white" if red else "text-muted", str(dayOfMonth))
            else:
                cal_events_text += '<li><div class="date" style="color:{0};">{1}</div>\n'.format("white" if red else "black", str(dayOfMonth))

            event_count = len(calList[i])
            for j in range(min(event_count, maxEventsPerDay)):
                event = calList[i][j]
                event_line_limit = max(math.floor(maxEventsPerDay / event_count), 1)
                event_color = "color:white;" if red else "color: #6c757d!important;" if currDate.month != calDict['today'].month and not red else "color:black;"
                cal_events_text += '<div {0}'.format('style="overflow:hidden;font-weight:bold;line-height:1.5em;height:{0}em;{1}'.format(1.5 * event_line_limit, event_color))
                if event['isMultiday']:
                    if event['startDatetime'].date() == currDate:
                        cal_events_text += '">►' + event['summary']
                    else:
                        cal_events_text += '">◄' + event['summary']
                elif event['allday']:
                    cal_events_text += '">' + event['summary']
                else:
                    cal_events_text += '">' + self.get_short_time(event['startDatetime']) + ' ' + event[
                        'summary']
                cal_events_text += '</div>\n'
            if len(calList[i]) > maxEventsPerDay:
                cal_events_text += '<div class="{0}">{1} more'.format("event-white" if red else "event text-muted", str(len(calList[i]) - maxEventsPerDay))

            cal_events_text += '</li>\n'

        # Append the bottom and write the file
        htmlFile = open(self.currPath + '/calendar.html', "w")
        htmlFile.write(calendar_template.format(month=month_name, battText=battText, dayOfWeek=cal_days_of_week,
                                                events=cal_events_text, forcastImage=weatherDict.get('id'), 
                                                forcastString="{0}% | {1}-{2}°".format(weatherDict.get('pop'), weatherDict.get('low'), weatherDict.get('high')), 
                                                forcastStyle="text-white" if red else "text-uppercase"))
        htmlFile.close()
        image = self.get_screenshot(red)
        return image
