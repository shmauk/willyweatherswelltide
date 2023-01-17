"""Support for the WillyWeather Australia service."""
import logging
from datetime import timedelta, datetime

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by WillyWeather"

CONF_STATION_ID = 'station_id'
CONF_API_KEY = 'api_key'

DEFAULT_NAME = 'WW Swell and Tide'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

SENSOR_TYPES = {
    'next_tide_type': ['Next Tide Type', None],
    'next_tide_time': ['Next Tide Time', None],
    'next_tide_height': ['Next Tide Height', 'm'],
    'second_tide_type': ['Second Tide Type', None],
    'second_tide_time': ['Second Tide Time', None],
    'second_tide_height': ['Second Tide Height', 'm'],
    'third_tide_type': ['Third Tide Type', None],
    'third_tide_time': ['Third Tide Time', None],
    'third_tide_height': ['Third Tide Height', 'm'],
    'fourth_tide_type': ['Fourth Tide Type', None],
    'fourth_tide_time': ['Fourth Tide Time', None],
    'fourth_tide_height': ['Fourth Tide Height', 'm']
}

FORECAST_TYPES = {
    'forecast_swell_height' : ['Swell Height', 'm'],
    'forecast_swell_direction' : ['Swell Direction', 'degrees'],
    'forecast_swell_direction_text': ['Swell Direciton Text', None]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the WillyWeather weather sensor."""

    station_id = config.get(CONF_STATION_ID)
    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)

    # If no station_id determine from Home Assistant lat/long
    if station_id is None:
        station_id = get_station_id(hass.config.latitude, hass.config.longitude, api_key)
        if station_id is None:
            _LOGGER.critical("Can't retrieve Station from WillyWeather")
            return False

    ww_data = WWSwellTideInstance(api_key, station_id)

    try:
        ww_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from WillyWeather: %s", err)
        return

    sensors = []
    for sensor in SENSOR_TYPES:
        sensors.append(WWSwellTideSensor(name,ww_data,sensor))

    add_entities(sensors)

def get_station_id(lat, lng, api_key):

    closestURLParams = [
        ("lat", lat),
        ("lng", lng),
        ("units", "distance:km")
    ]

    try:
        resp = requests.get(f'https://api.willyweather.com.au/v2/{api_key}/search.json', params=closestURLParams, timeout=10).json()
        if resp is None:
            return

        return resp['location']['id']

    except ValueError as err:
        _LOGGER.error("*** Error finding closest station")

class WWSwellTideSensor(Entity):
    
    def __init__(self, name, data, sensor):
            """Initialize the data object."""
            self._client = name
            self._name = SENSOR_TYPES[sensor][0]
            self._unit = SENSOR_TYPES[sensor][1]
            self._latest = data # this is an entire swell tide instance
            self._type = sensor
            self._unique_id = None
            self._state = None

    @property
    def name(self):
        return self._name

    @property
    def unit(self):
        return self._unit

    @property
    def unique_id(self):
        """Return the sensor unique id."""
        return f"{self._client} {self._name}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        return attrs

    def update(self):
        """Get the latest data from WillyWeather and updates the states."""
        self._latest.update()
        if self._latest == None:
            _LOGGER.info("Didn't receive weather data from WillyWeather")
            return
        elif self._type == 'next_tide_type':
            self._state = self._latest._tide_data[0]['type']
        elif self._type == 'next_tide_time':
            self._state = self._latest._tide_data[0]['dateTime']
        elif self._type == 'next_tide_height':
            self._state = self._latest._tide_data[0]['height']
        elif self._type == 'second_tide_type':
            self._state = self._latest._tide_data[1]['type']
        elif self._type == 'second_tide_time':
            self._state = self._latest._tide_data[1]['dateTime']
        elif self._type == 'second_tide_height':
            self._state = self._latest._tide_data[1]['height']
        elif self._type == 'third_tide_type':
            self._state = self._latest._tide_data[2]['type']
        elif self._type == 'third_tide_time':
            self._state = self._latest._tide_data[2]['dateTime']
        elif self._type == 'third_tide_height':
            self._state = self._latest._tide_data[2]['height']
        elif self._type == 'fourth_tide_type':
            self._state = self._latest._tide_data[3]['type']
        elif self._type == 'fourth_tide_time':
            self._state = self._latest._tide_data[3]['dateTime']
        elif self._type == 'fourth_tide_height':
            self._state = self._latest._tide_data[3]['height']

class WWSwellTideInstance:
    """Handle WillyWeather API object and limit updates."""

    def __init__(self, api_key, station_id):
        """Initialize the data object."""
        self._api_key = api_key
        self._station_id = station_id
        self._data = None
        self._tide_data = None
        self._swell_data = None

    def remove_past_tide_data(self):
        now = datetime.now()
        
        tide_events = self._data['forecasts']['tides']['days'][0]['entries']
        tide_events.extend(self._data['forecasts']['tides']['days'][1]['entries'])

        current_tide_events = [tide_event for tide_event in tide_events if datetime.strptime(tide_event['dateTime'], '%Y-%m-%d %H:%M:%S') > now]
        self._tide_data = current_tide_events[:4]

    def remove_past_swell_data(self):
        now = datetime.now()
        
        swell_forecasts = self._data['forecasts']['swell']['days'][0]['entries']
        swell_forecasts.extend(self._data['forecasts']['swell']['days'][1]['entries'])

        current_swell_forecasts = [swell_forecast for swell_forecast in swell_forecasts if datetime.strptime(swell_forecast['dateTime'], '%Y-%m-%d %H:%M:%S') > now]
        self._swell_data = current_swell_forecasts[:24]

    @property
    def api_key(self):
        return self._api_key

    @property
    def station_id(self):
        return self._station_id

    @property
    def swell_tide_data(self):
        """Return the latest data object."""
        return self._data

    #@Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from WillyWeather."""
        result = requests.get(f'https://api.willyweather.com.au/v2/{self._api_key}/locations/{self._station_id}/weather.json?forecasts=swell,tides&days=2', timeout=10).json()
        self._data = result
        self.remove_past_swell_data()
        self.remove_past_tide_data()
        return
