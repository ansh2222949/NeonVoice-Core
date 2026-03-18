"""NeonAI: Tool implementation used by the router."""

import requests
import re
from brain import memory


def get_weather(city):
    """Get weather using Open-Meteo API (free, reliable, no API key)."""
    try:
        from utils import network
        if not network.is_internet_allowed("casual", silent=True):
            return "⚠️ I cannot check the weather while offline."

        # Clean city name
        city = city.strip().title()

        # Step 1: Get coordinates for the city
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_resp = requests.get(geo_url, timeout=5)
        
        if geo_resp.status_code != 200 or not geo_resp.json().get("results"):
            return f"❌ Couldn't find location coordinates for {city}."
            
        geo_data = geo_resp.json()["results"][0]
        lat, lon = geo_data["latitude"], geo_data["longitude"]
        location_name = geo_data.get("name", city)
        country = geo_data.get("country", "")

        # Step 2: Get weather data using coordinates
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
        )
        weather_resp = requests.get(weather_url, timeout=5)
        
        if weather_resp.status_code != 200:
            return f"❌ Couldn't get weather data for {location_name}."

        w_data = weather_resp.json()
        current = w_data.get("current", {})
        daily = w_data.get("daily", {})

        # Parse current weather
        temp_c = current.get("temperature_2m", "?")
        feels = current.get("apparent_temperature", "?")
        humidity = current.get("relative_humidity_2m", "?")
        wind_kmph = current.get("wind_speed_10m", "?")
        
        # WMO Weather interpretation codes (simplified)
        wcode = current.get("weather_code", 0)
        desc_map = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"
        }
        desc = desc_map.get(wcode, "Unknown")

        result = (
            f"🌤️ **Weather in {location_name}**"
            f"{f', {country}' if country else ''}\n\n"
            f"🌡️ Temperature: **{temp_c}°C** (feels like {feels}°C)\n"
            f"☁️ Condition: **{desc}**\n"
            f"💧 Humidity: {humidity}%\n"
            f"💨 Wind: {wind_kmph} km/h"
        )

        # Add forecast if available
        if "temperature_2m_max" in daily and len(daily["temperature_2m_max"]) >= 3:
            tmr_max = daily["temperature_2m_max"][1]
            tmr_min = daily["temperature_2m_min"][1]
            da_max = daily["temperature_2m_max"][2]
            da_min = daily["temperature_2m_min"][2]
            
            result += f"\n\n📅 **Tomorrow:** {tmr_min}°C - {tmr_max}°C"
            result += f"\n📅 **Day After:** {da_min}°C - {da_max}°C"

        return result

    except requests.RequestException:
        return f"⚠️ Couldn't connect to weather service. Check your internet."
    except Exception as e:
        return f"⚠️ Weather error: {str(e)}"


def handle(user_text, user_id="anon"):
    """Handle weather queries. Returns string or None."""

    lower = user_text.lower().strip()
    # Remove trailing punctuation to ensure regexes match correctly
    lower = re.sub(r'[,.?!]+$', '', lower)
    # Strip conversational filler
    lower = re.sub(r'^(?:can you|could you|would you|please|just|hey neon|neon|tell me|show me)\s+', '', lower).strip()

    # Intent is now governed by the Semantic Router in tool_router.py.
    # We proceed directly to parsing the parameters (location).

    # Extract city name (Upgraded Regex logic)
    patterns = [
        r"(?:weather|wether|climate).*?(?:in|at|for|of)\s+([a-z\s]+)",
        r"(?:temperature|temperter).*?(?:in|at|of)\s+([a-z\s]+)",
        r"forecast.*?(?:in|at|for|of)\s+([a-z\s]+)",
        r"(?:how\s+(?:hot|cold|warm)).*?(?:in|at|outside|outside in)\s+([a-z\s]+)",
        r"([a-z\s]+)\s+(?:weather|wether|temperature|climate|forecast)",
        r"(?:weather|wether|temperature|climate|forecast)\s+(?:for\s+)?([a-z\s]+)",
        r"(?:in|at|of|for)\s+([a-z\s]+)",  # Extreme fallback for semantic queries like "is it raining in london"
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            city = match.group(1).strip()
            # Clean common trailing stop words that might have been caught by [a-z\s]+
            city = re.sub(r"\b(right now|today|tomorrow|currently|please|thanks)\b", "", city).strip()
            # If city was completely erased (e.g., they just said "weather today"), skip this match
            if city and len(city) > 2 and city not in ["the", "a", "an", "is", "like", "what", "how"]:
                return get_weather(city)

    # If we still can't find a city from the user text, use default location.
    # Because Semantic Router confidently sent us here, we must assume they want weather.
    prof = memory.load_profile("general", user_id)
    loc = prof.get("location", "Delhi")
    return get_weather(loc)
