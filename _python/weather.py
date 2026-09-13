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
    humidity = str(today["humidity"])
    sunrise = str(today["sunrise"])   # already "HH:MM"
    sunset = str(today["sunset"])     # already "HH:MM"
    icon = str(today.get("icon", ""))
    icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png" if icon else ""

    string_today = f'<div class="weather-glance">\n'
    string_today += f'    <p class="weather-glance-date">{output_date}</p>\n'
    string_today += f'    <div class="weather-glance-header">\n'
    if icon_url:
        string_today += f'        <img src="{icon_url}" alt="{day_desc}" class="weather-glance-icon" width="80" height="80">\n'
    string_today += f'        <div>\n'
    string_today += f'            <span class="weather-glance-temp">{day_temp}&deg;C</span>\n'
    string_today += f'            <span class="weather-glance-desc">{day_desc.capitalize()} &middot; feels like {feels_like}&deg;C</span>\n'
    string_today += f'        </div>\n'
    string_today += f'    </div>\n'
    string_today += f'    <ul class="weather-glance-stats">\n'
    string_today += f'        <li><span>High / Low</span><strong>{high_temp}&deg; / {low_temp}&deg;</strong></li>\n'
    string_today += f'        <li><span>Wind</span><strong>{wind_speed} m/s</strong></li>\n'
    string_today += f'        <li><span>Humidity</span><strong>{humidity}%</strong></li>\n'
    string_today += f'        <li><span>Sunrise / Sunset</span><strong>{sunrise} / {sunset}</strong></li>\n'
    string_today += f'    </ul>\n'
    string_today += f'</div>\n'

    f = root / "index.md"
    m = f.open().read()
    c = helper.replace_chunk(m, "weather_marker", string_today)
    f.open("w").write(c)
    print("Weather completed")
