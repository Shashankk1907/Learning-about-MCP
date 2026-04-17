from __future__ import annotations

import logging

import httpx

from mcp_server.core.app import SecureMCP

logger = logging.getLogger(__name__)

def register_weather_tools(app: SecureMCP):
    """Register weather tools with the SecureMCP application."""

    @app.tool(
        name="weather-get",
        description="Get current weather for a specific city using wttr.in",
        required_scopes=["tools:weather:get"]
    )
    async def get_weather(city: str) -> str:
        """Fetch weather data for a city from wttr.in."""
        url = f"https://wttr.in/{city}?format=j1"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                # Extract key information from the JSON response
                current = data.get("current_condition", [{}])[0]
                temp_c = current.get("temp_C")
                weather_desc = current.get("weatherDesc", [{}])[0].get("value")
                humidity = current.get("humidity")
                wind_speed = current.get("windspeedKmph")

                result = (
                    f"Current weather in {city}:\n"
                    f"- Temperature: {temp_c}°C\n"
                    f"- Condition: {weather_desc}\n"
                    f"- Humidity: {humidity}%\n"
                    f"- Wind Speed: {wind_speed} km/h"
                )
                return result

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching weather for {city}: {e}")
                return f"Error: Could not retrieve weather for '{city}' (Status: {e.response.status_code})"
            except Exception as e:
                logger.error(f"Unexpected error fetching weather for {city}: {e}")
                return f"Error: An unexpected error occurred while fetching weather for '{city}'"
