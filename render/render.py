#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from time import sleep
from datetime import timedelta
import pathlib
from PIL import Image
import logging
import math

MAX_LINES = 4

class RenderHelper:

    def __init__(self, width, height, angle):
        self.logger = logging.getLogger('maginkcal')
        self.currPath = str(pathlib.Path(__file__).parent.absolute())
        self.htmlFile = 'file://' + self.currPath + '/calendar.html'
        self.imageWidth = width
        self.imageHeight = height
        self.rotateAngle = angle

    def set_viewport_size(self, driver):

        # Extract the current window size from the driver
        current_window_size = driver.get_window_size()

        # Extract the client window size from the html tag
        html = driver.find_element(By.TAG_NAME,'html')
        inner_width = int(html.get_attribute("clientWidth"))
        inner_height = int(html.get_attribute("clientHeight"))

        # "Internal width you want to set+Set "outer frame width" to window size
        target_width = self.imageWidth + (current_window_size["width"] - inner_width)
        target_height = self.imageHeight + (current_window_size["height"] - inner_height)

        driver.set_window_rect(
            width=target_width,
            height=target_height)

    def get_screenshot(self, red):
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--hide-scrollbars");
        opts.add_argument('--force-device-scale-factor=1')
        driver = webdriver.Chrome(options=opts)
        self.set_viewport_size(driver)
        driver.get(self.htmlFile)
        sleep(1)
        if red:
            name = '/calendar_red.png'
        else:
            name = '/calendar_black.png'
        driver.get_screenshot_as_file(self.currPath + name)
        driver.quit()

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
        # weatherDict = {'high': 75, "low": 55, "pop": 10, "id": 801}
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
            else:
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
            cal_days_of_week += '<li class="font-weight-bold {0}">{1}</li>\n'.format("text-uppercase-white" if red else "text-uppercase", dayOfWeekText[
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
                cal_events_text += '<li><div class="{0}">{1}</div>\n'.format("date-white" if red else "date", str(dayOfMonth))

            event_count = len(calList[i])
            for j in range(min(event_count, maxEventsPerDay)):
                event = calList[i][j]
                event_line_limit = max(math.floor(MAX_LINES / event_count), 1)
                cal_events_text += '<div {0}'.format('class="event-white' if red 
                    else 'style="font-size:1rem;max-height:{0}rem;padding:0.1rem;{1}overflow:hidden;text-overflow:ellipsis;border-radius:0rem;margin-bottom:1px;'.format(
                        1.5 * event_line_limit, "color: #6c757d!important;" if currDate.month != calDict['today'].month and not red else "color:black;"))
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
                                                forcastText="text-white" if red else "text-uppercase"))
        htmlFile.close()
        image = self.get_screenshot(red)
        return image
