import requests
from config import SOHAG_LATITUDE, SOHAG_LONGITUDE, TIMEZONE


def get_sohag_weather() -> dict:
    """
    Get weather for Sohag from Open-Meteo API (Free, No Key).
    Returns temp for Morning (8AM), Noon (1PM), Night (10PM).
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": SOHAG_LATITUDE,
        "longitude": SOHAG_LONGITUDE,
        "hourly": "temperature_2m,weathercode",
        "timezone": TIMEZONE,
        "forecast_days": 1,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        hourly_times = data["hourly"]["time"]
        hourly_temps = data["hourly"]["temperature_2m"]
        hourly_codes = data["hourly"]["weathercode"]

        # Create dict for quick lookup by hour
        weather_by_hour = {}
        for i, time_str in enumerate(hourly_times):
            hour = int(time_str.split("T")[1].split(":")[0])
            weather_by_hour[hour] = {
                "temp": hourly_temps[i],
                "code": hourly_codes[i],
            }

        def get_weather_emoji(code: int) -> str:
            """Convert weather code to emoji"""
            if code == 0:
                return "☀️"
            elif code in [1, 2]:
                return "🌤️"
            elif code == 3:
                return "☁️"
            elif code in [45, 48]:
                return "🌫️"
            elif code in range(51, 68):
                return "🌧️"
            elif code in range(71, 78):
                return "❄️"
            elif code in range(80, 90):
                return "⛈️"
            else:
                return "🌡️"

        morning = weather_by_hour.get(8, {"temp": "—", "code": 0})
        noon = weather_by_hour.get(13, {"temp": "—", "code": 0})
        night = weather_by_hour.get(22, {"temp": "—", "code": 0})

        return {
            "morning": {
                "temp": morning["temp"],
                "emoji": get_weather_emoji(morning["code"]),
            },
            "noon": {
                "temp": noon["temp"],
                "emoji": get_weather_emoji(noon["code"]),
            },
            "night": {
                "temp": night["temp"],
                "emoji": get_weather_emoji(night["code"]),
            },
        }

    except Exception as e:
        print(f"Error fetching weather: {e}")
        return {
            "morning": {"temp": "—", "emoji": "🌡️"},
            "noon": {"temp": "—", "emoji": "🌡️"},
            "night": {"temp": "—", "emoji": "🌡️"},
        }
