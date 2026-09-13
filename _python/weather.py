#!/usr/bin/env python3
"""Pick today's record out of the already-fetched _data/weather.json
(written by forecast.py) and write it to _data/weather-today.json for
the homepage to render."""
import json
import datetime
import helper

if __name__ == "__main__":
    root = helper.repo_root()

    weather_file = root / "_data" / "weather.json"
    data = json.loads(weather_file.read_text())

    # pick today's record (match by date, fall back to first entry)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    today = next((d for d in data["days"] if d["date"] == today_str), data["days"][0])

    output = {
        "date": datetime.date.today().strftime("%A, %d %B %Y"),
        "temp": today["day"],
        "feels_like": today["feels_like"],
        "desc": today["desc"],
        "icon": today.get("icon", ""),
        "high": today["max"],
        "low": today["min"],
        "wind": today["wind"],
        "humidity": today["humidity"],
        "sunrise": today["sunrise"],   # already "HH:MM"
        "sunset": today["sunset"],     # already "HH:MM"
    }

    out = root / "_data" / "weather-today.json"
    out.write_text(json.dumps(output, indent=2))
    print(f"Wrote today's weather to {out}")
