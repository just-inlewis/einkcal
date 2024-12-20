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

    def __init__(self, width, height):
        # Initialise the display
        self.logger = logging.getLogger('einkcal')
        self.screenwidth = width
        self.screenheight = height
        self.epd = eink.EPD()
        self.epd.Init()

    def update(self, blackimg, redimg):
        # Updates the display with the grayscale and red images
        # start displaying on eink display
        # self.epd.clear()
        self.epd.display(blackimg, redimg)
        self.logger.info('E-Ink display update complete.')

    def calibrate(self, cycles=1):
        # Calibrates the display to prevent ghosting
        white = Image.new('1', (self.screenwidth, self.screenheight), 255)
        black = Image.new('1', (self.screenwidth, self.screenheight), 255)
        for _ in range(cycles):
            self.epd.display(black, white)
            self.epd.display(white, black)
            self.epd.display(white, white)
        self.logger.info('E-Ink display calibration complete.')

    def sleep(self):
        # send E-Ink display to deep sleep
        self.epd.EPD_Sleep()
        self.logger.info('E-Ink display entered deep sleep.')

    def displayError(self, message):
        blackError = Image.new("1", (self.screenwidth, self.screenheight), 255)
        redError = Image.new("1", (self.screenwidth, self.screenheight), 255)
        drawError = ImageDraw.Draw(blackError)
        drawError.text((self.screenwidth/2, self.screenheight/2), message, fill="black")
        blackError = blackError.rotate(180)
        redError = redError.rotate(180)
        self.update(blackError, redError)
        self.sleep()
