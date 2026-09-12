# importing modules
import json
import datetime
import helper

if __name__ == "__main__":
    root = helper.repo_root()

    # read the already-fetched forecast
    weather_file = root / "_data" / "weather.json"
    data = json.loads(weather_file.read_text())

    # pick today's record (match by date, fall back to first entry)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    today = next((d for d in data["days"] if d["date"] == today_str), data["days"][0])

    output_date = datetime.date.today().strftime("%A, %d %B %Y")

    day_temp = str(today["day"])
    feels_like = str(today["feels_like"])
    day_desc = str(today["desc"])
    high_temp = str(today["max"])
    low_temp = str(today["min"])
    wind_speed = str(today["wind"])
    pressure = str(today["pressure"])
    humidity = str(today["humidity"])
    sunrise = str(today["sunrise"])   # already "HH:MM"
    sunset = str(today["sunset"])     # already "HH:MM"

    string_today = f"## On {output_date}\n\n"
    string_today += f"- The average temperature today is {day_temp}˚C,\n"
    string_today += f"- With highs of {high_temp}˚C and lows of {low_temp}˚C,\n"
    string_today += f"- It may feel like {feels_like}˚C with {day_desc}\n"
    string_today += f"- The wind speed is {wind_speed}m/s\n"
    string_today += f"- The pressure is {pressure}hPa and humidity is {humidity}%\n"
    string_today += f"- The sun will rise at {sunrise} and set at {sunset}\n"

    f = root / "index.md"
    m = f.open().read()
    c = helper.replace_chunk(m, "weather_marker", string_today)
    f.open("w").write(c)
    print("Weather completed")
