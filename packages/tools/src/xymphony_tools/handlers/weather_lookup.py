"""Deterministic Weather Lookup tool."""

from __future__ import annotations

import hashlib
from typing import Any

from xymphony_tools.domain import Tool

# Deterministic base conditions for known cities
_KNOWN_CITIES: dict[str, dict[str, Any]] = {
    "san francisco": {
        "city": "San Francisco",
        "temperature_c": 16,
        "condition": "Foggy",
        "humidity_percent": 82,
        "wind_speed_kmh": 18,
    },
    "new york": {
        "city": "New York",
        "temperature_c": 22,
        "condition": "Partly Cloudy",
        "humidity_percent": 65,
        "wind_speed_kmh": 12,
    },
    "london": {
        "city": "London",
        "temperature_c": 15,
        "condition": "Light Rain",
        "humidity_percent": 88,
        "wind_speed_kmh": 15,
    },
    "tokyo": {
        "city": "Tokyo",
        "temperature_c": 24,
        "condition": "Clear",
        "humidity_percent": 58,
        "wind_speed_kmh": 8,
    },
    "paris": {
        "city": "Paris",
        "temperature_c": 19,
        "condition": "Sunny",
        "humidity_percent": 50,
        "wind_speed_kmh": 10,
    },
    "sydney": {
        "city": "Sydney",
        "temperature_c": 20,
        "condition": "Sunny",
        "humidity_percent": 60,
        "wind_speed_kmh": 16,
    },
}

_CONDITIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Clear", "Breezy"]


def _derive_city_weather(city: str) -> dict[str, Any]:
    city_normalized = city.strip().lower()
    if city_normalized in _KNOWN_CITIES:
        return dict(_KNOWN_CITIES[city_normalized])

    # Deterministic generation for any unknown city
    digest = int(hashlib.md5(city_normalized.encode()).hexdigest()[:8], 16)
    temp_c = 10 + (digest % 25)
    condition = _CONDITIONS[digest % len(_CONDITIONS)]
    humidity = 40 + (digest % 50)
    wind = 5 + (digest % 25)
    return {
        "city": city.strip().title(),
        "temperature_c": temp_c,
        "condition": condition,
        "humidity_percent": humidity,
        "wind_speed_kmh": wind,
    }


def lookup_weather(city: str, units: str = "celsius") -> dict[str, Any]:
    """Retrieve weather conditions for a specified city in Celsius or Fahrenheit."""
    clean_city = city.strip()
    if not clean_city:
        raise ValueError("City name cannot be empty.")

    clean_units = units.strip().lower() if units else "celsius"
    if clean_units not in ("celsius", "fahrenheit"):
        raise ValueError(f"Unsupported units '{units}'. Must be 'celsius' or 'fahrenheit'.")

    base = _derive_city_weather(clean_city)
    temp_c = base["temperature_c"]

    if clean_units == "fahrenheit":
        temp_final = round((temp_c * 9 / 5) + 32, 1)
        if temp_final.is_integer():
            temp_final = int(temp_final)
    else:
        temp_final = temp_c

    return {
        "city": base["city"],
        "temperature": temp_final,
        "units": clean_units,
        "condition": base["condition"],
        "humidity_percent": base["humidity_percent"],
        "wind_speed_kmh": base["wind_speed_kmh"],
    }


def create_weather_lookup_tool() -> Tool:
    """Create a configured Tool instance for weather lookup."""
    return Tool(
        name="weather_lookup",
        description="Retrieves current weather conditions, temperature, humidity, and wind speed for a specified city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Name of the city to look up weather for.",
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature units (celsius or fahrenheit). Defaults to celsius.",
                },
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        handler=lookup_weather,
    )
