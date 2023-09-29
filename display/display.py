#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This part of the code exposes functions to interface with the eink display
"""

import display.epd12in48b as eink
from PIL import Image
from PIL import ImageDraw
import logging


class DisplayHelper:

    def __init__(self, width, height, final_callback):
        # Initialise the display
        self.logger = logging.getLogger('einkcal')
        self.screenwidth = width
        self.screenheight = height
        self.epd = eink.EPD(final_callback)
        self.epd.enqueue(epd.Init, callback=None)

    def clear(self, callback=None):
        epd.enqueue(epd.clear, callback=callback)

    def update(self, blackimg, redimg, callback=None):
        # Updates the display with the grayscale and red images
        # start displaying on eink display
        self.logger.info('Enqueuing E-Ink display update.')
        epd.enqueue(epd.display, blackimg, redimg, callback=callback)

    def calibrate(self, cycles=1, callback=None):
        # Calibrates the display to prevent ghosting
        white = Image.new('1', (self.screenwidth, self.screenheight), 255)
        black = Image.new('1', (self.screenwidth, self.screenheight), 255)
        self.logger.info('Enqueuing E-Ink display calibration.')
        for _ in range(cycles):
            epd.enqueue(epd.display, black, white, callback=callback)
            epd.enqueue(epd.display, white, black, callback=callback)
            epd.enqueue(epd.display, white, white, callback=callback)

    def sleep(self, callback=None):
        # send E-Ink display to deep sleep
        self.logger.info('Telling E-Ink display to entered deep sleep.')
        epd.enqueue(epd.EPD_Sleep, callback=callback)

    def displayError(self, message, callback=None):
        blackError = Image.new("1", (self.screenwidth, self.screenheight), 255)
        redError = Image.new("1", (self.screenwidth, self.screenheight), 255)
        drawError = ImageDraw.Draw(blackError)
        drawError.text((self.screenwidth/2, self.screenheight/2), message, fill="black")
        blackError = blackError.rotate(180)
        redError = redError.rotate(180)
        self.update(blackError, redError)
        self.sleep()
