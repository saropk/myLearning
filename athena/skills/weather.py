"""Live weather via Open-Meteo — free and needs no API key.

Two calls: geocode the place name to coordinates, then fetch the current
conditions. WMO weather codes are mapped to plain-English descriptions.
"""

import re

from .base import Skill
from ..util import http

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather-interpretation codes -> short descriptions.
WMO = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "drizzly", 53: "drizzly", 55: "drizzly",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rainy", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snowy", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


class WeatherSkill(Skill):
    name = "get_weather"
    triggers = ("weather", "forecast", "temperature", "how hot", "how cold", "raining")

    expose = True
    description = "Get the current weather for a city or place by name."
    parameters = {
        "location": {"type": "string", "description": "City or place, e.g. 'Paris'."}
    }
    required = ("location",)

    def run(self, athena, location: str | None = None) -> str:
        location = (location or "").strip()
        if not location:
            return "Which city's weather would you like?"

        geo = http.get_json(GEOCODE_URL, {"name": location, "count": 1, "language": "en"})
        if not geo or not geo.get("results"):
            return f"I couldn't find a place called {location}."
        place = geo["results"][0]
        name = place["name"]

        data = http.get_json(FORECAST_URL, {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        if not data or "current" not in data:
            return f"I couldn't reach the weather service for {name} right now."

        cur = data["current"]
        temp = round(cur["temperature_2m"])
        feels = round(cur["apparent_temperature"])
        desc = WMO.get(cur["weather_code"], "cloudy")
        wind = round(cur["wind_speed_10m"])
        feels_note = f", feeling like {feels}" if abs(feels - temp) >= 3 else ""
        return (
            f"It's {temp} degrees and {desc} in {name}{feels_note}, "
            f"with wind at {wind} kilometers per hour."
        )

    def parse(self, text: str) -> dict | None:
        if not self.can_handle(text):
            return None
        match = re.search(r"\b(?:in|at|for|near)\s+(.+)$", text.lower())
        location = match.group(1).strip(" ?.") if match else ""
        return {"location": location}
