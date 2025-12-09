"""
This is where we retrieve weather forecast from OpenWeatherMap. Before doing so, make sure you have both the
signed up for an OWM account and also obtained a valid API key that is specified in the config.json file.
"""

import logging
import requests
import json
import string
from datetime import datetime


class WeatherHelper:
    def __init__(self):
        self.logger = logging.getLogger('einkcal')

    def retry_strategy(self):
        return requests.adapters.Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            backoff_factor=2,
            allowed_methods=False
        )

    def get_weather(self, lat, lon, api_key, unit="metric"):
        url = "https://api.openweathermap.org/data/3.0/onecall?lat={0}&lon={1}&appid={2}&exclude=current,minutely,hourly,alerts&units=metric".format(
        lat, lon, api_key)
        session = requests.Session()
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=self.retry_strategy()))
        response = session.get(url)
        data = json.loads(response.text)
        for forcast in data.get('daily'):
            if datetime.utcfromtimestamp(forcast.get('dt')).date() == datetime.today().date():
                w = {'high': round(forecast.get('temp', {}).get('max')),
                     'low': round(forcast.get('temp', {}).get('min')),
                     'pop': round(forcast.get('pop') * 100),
                     'id': forcast.get('weather', [{}])[0].get('id')}
                return w
