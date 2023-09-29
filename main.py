#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import sys

from pytz import timezone
from cal.cal import CalHelper
from render.render import RenderHelper
from weather.weather import WeatherHelper
from power.power import PowerHelper
from display.display import DisplayHelper
import json
import logging
import os
import traceback


configFile = open('config.json')
config = json.load(configFile)

# Basic configuration settings (user replaceable)
displayTZ = timezone(config['displayTZ']) # list of timezones - print(pytz.all_timezones)
thresholdHours = config['thresholdHours']  # considers events updated within last 12 hours as recently updated
maxEventsPerDay = config['maxEventsPerDay']  # limits number of events to display (remainder displayed as '+X more')
isDisplayToScreen = config['isDisplayToScreen']  # set to true when debugging rendering without displaying to screen
isShutdownOnComplete = config['isShutdownOnComplete']  # set to true to conserve power, false if in debugging mode
batteryDisplayMode = config['batteryDisplayMode']  # 0: do not show / 1: always show / 2: show when battery is low
weekStartDay = config['weekStartDay']  # Monday = 0, Sunday = 6
dayOfWeekText = config['dayOfWeekText'] # Monday as first item in list
screenWidth = config['screenWidth']  # Width of E-Ink display. Default is landscape. Need to rotate image to fit.
screenHeight = config['screenHeight']  # Height of E-Ink display. Default is landscape. Need to rotate image to fit.
imageWidth = config['imageWidth']  # Width of image to be generated for display.
imageHeight = config['imageHeight'] # Height of image to be generated for display.
rotateAngle = config['rotateAngle']  # If image is rendered in portrait orientation, angle to rotate to fit screen
calendar = config['calendar']  # calendar url
latitude = config['lat'] # latitude for open weather call
longitude = config['long'] # longitude for open weather call
apiKey = config['openweatherapi'] # api key for open weather clal
updateTime = config['dailyUpdateTime'] # hour of day data is refreshed, this ensures device wont shut down during testing

def shutdown():
    currDatetime = dt.datetime.now(displayTZ)
    logger.info("Checking if configured to shutdown safely - Current hour: {}".format(currDatetime.hour))
    if isShutdownOnComplete:
        if currDatetime.hour == updateTime:
            logger.info("Shutting down safely.")
            os.system("sudo shutdown -h now")


def main():
    # Create and configure logger
    logging.basicConfig(filename="logfile.log", format='%(asctime)s %(levelname)s - %(message)s', filemode='a')
    logger = logging.getLogger('einkcal')
    logger.addHandler(logging.StreamHandler(sys.stdout))  # print logger to stdout
    logger.setLevel(logging.INFO)
    logger.info("Starting daily calendar update")

    try:
        # Establish current date and time information
        # Note: For Python datetime.weekday() - Monday = 0, Sunday = 6
        # For this implementation, each week starts on a Sunday and the calendar begins on the nearest elapsed Sunday
        # The calendar will also display 5 weeks of events to cover the upcoming month, ending on a Saturday
        powerService = PowerHelper()
        powerService.sync_time()
        currBatteryLevel = powerService.get_battery()
        logger.info('Battery level at start: {:.3f}'.format(currBatteryLevel))

        currDatetime = dt.datetime.now(displayTZ)
        logger.info("Time synchronised to {}".format(currDatetime))
        currDate = currDatetime.date()
        calStartDate = currDate - dt.timedelta(days=((currDate.weekday() + (7 - weekStartDay)) % 7))
        calEndDate = calStartDate + dt.timedelta(days=(5 * 7 - 1))
        calStartDatetime = displayTZ.localize(dt.datetime.combine(calStartDate, dt.datetime.min.time()))
        calEndDatetime = displayTZ.localize(dt.datetime.combine(calEndDate, dt.datetime.max.time()))

        # Using Google Calendar to retrieve all events within start and end date (inclusive)
        start = dt.datetime.now()
        calService = CalHelper()
        eventList = calService.retrieve_events(calendar, calStartDatetime, calEndDatetime, displayTZ, thresholdHours)
        logger.info("Calendar events retrieved in " + str(dt.datetime.now() - start))

        # Populate dictionary with information to be rendered on e-ink display
        calDict = {'events': eventList, 'calStartDate': calStartDate, 'today': currDate, 'lastRefresh': currDatetime,
                   'batteryLevel': currBatteryLevel, 'batteryDisplayMode': batteryDisplayMode,
                   'dayOfWeekText': dayOfWeekText, 'weekStartDay': weekStartDay, 'maxEventsPerDay': maxEventsPerDay}
        
        weatherService = WeatherHelper()
        start = dt.datetime.now()
        weatherDict = weatherService.get_weather(latitude, longitude, apiKey)
        logger.info("Weather events retrieved in " + str(dt.datetime.now() - start))

        renderService = RenderHelper(imageWidth, imageHeight, rotateAngle)
        calBlackImage = renderService.process_inputs(calDict, weatherDict, red=False)
        calRedImage = renderService.process_inputs(calDict, weatherDict, red=True)

        if isDisplayToScreen:
            displayService = DisplayHelper(screenWidth, screenHeight, showdown)
            if currDate.weekday() == weekStartDay:
                # calibrate display once a week to prevent ghosting
                displayService.calibrate(cycles=0)  # to calibrate in production
            displayService.update(calBlackImage, calRedImage)
            displayService.sleep()

        currBatteryLevel = powerService.get_battery()
        logger.info('Battery level at end: {:.3f}'.format(currBatteryLevel))
        logger.info("Completed daily calendar update")

    except Exception as e:
        traceback.print_exc()
        displayErrorService = DisplayHelper(screenWidth, screenHeight, shutdown)
        displayErrorService.displayError(str(e))
        logger.error(e)
                

if __name__ == "__main__":
    main()
