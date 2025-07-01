import os
import requests
import customtkinter as ctk
import tkinter
from tkinter import messagebox, simpledialog
from datetime import datetime
from dotenv import load_dotenv
import threading
import time

# Load API keys from .env
load_dotenv()
OWM_KEY = os.getenv("OPENWEATHER_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Config file for persistent ZIP
ZIP_FILE = os.path.expanduser("~/.niceoutside_zip_config.txt")

# Set up dark theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

REFRESH_INTERVAL = 600  # default 10 minutes

def get_saved_zip():
    if os.path.exists(ZIP_FILE):
        with open(ZIP_FILE, "r") as f:
            return f.read().strip()
    return None

def save_zip(zip_code):
    with open(ZIP_FILE, "w") as f:
        f.write(zip_code.strip())

def get_location_from_zip(zip_code):
    url = f"http://api.openweathermap.org/geo/1.0/zip?zip={zip_code},US&appid={OWM_KEY}"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise ValueError("Invalid ZIP or failed to get location")
    data = resp.json()
    return {
        "lat": data["lat"],
        "lon": data["lon"],
        "name": data["name"]
    }

def get_current_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=imperial&appid={OWM_KEY}"
    resp = requests.get(url)
    data = resp.json()
    return {
        "temp": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "rain": "rain" in data
    }

def get_monthly_averages(lat, lon):
    now = datetime.now()
    start = f"{now.year}-01-01"
    end = f"{now.year}-12-31"

    url = "https://meteostat.p.rapidapi.com/point/monthly"
    querystring = {
        "lat": str(lat),
        "lon": str(lon),
        "start": start,
        "end": end
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "meteostat.p.rapidapi.com"
    }

    resp = requests.get(url, headers=headers, params=querystring)
    data = resp.json()

    if "data" not in data or not data["data"]:
        raise ValueError("No average data returned")

    valid_months = []
    for m in data["data"]:
        tavg = m.get("tavg")
        if tavg is not None:
            try:
                month = datetime.strptime(m["date"], "%Y-%m-%d %H:%M:%S").month
                tavg_float = float(tavg)
                valid_months.append((month, tavg_float))
            except Exception:
                continue

    if not valid_months:
        raise ValueError("No valid average temperature data available")

    this_month = now.month
    for month, tavg in valid_months:
        if month == this_month:
            return {"avg_temp": (tavg * 9 / 5) + 32}

    latest_month, latest_tavg = max(valid_months, key=lambda x: x[0])
    return {"avg_temp": (latest_tavg * 9 / 5) + 32}
def is_nice_out(current, average):
    return (
        current["temp"] < average["avg_temp"] and
        30 <= current["humidity"] <= 50 and
        not current["rain"]
    )

def prompt_for_zip():
    zip_code = simpledialog.askstring("Enter ZIP", "Enter your ZIP code:")
    if not zip_code:
        raise SystemExit("ZIP code required")
    save_zip(zip_code)
    return zip_code

class WeatherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Is It Nice Outside?")
        self.geometry("500x300")

        self.status = ctk.CTkLabel(self, text="Checking...", font=("Segoe UI", 28))
        self.status.pack(pady=15)

        self.details = ctk.CTkLabel(self, text="", font=("Segoe UI", 14), wraplength=480, justify="center")
        self.details.pack(pady=10)

        self.settings_button = ctk.CTkButton(self, text="Change ZIP", command=self.change_zip)
        self.settings_button.pack(pady=5)

        self.zip_code = get_saved_zip() or prompt_for_zip()

        self.refresh_thread = threading.Thread(target=self.auto_refresh, daemon=True)
        self.refresh_thread.start()

    def change_zip(self):
        new_zip = simpledialog.askstring("Change ZIP", "Enter new ZIP code:")
        if new_zip:
            save_zip(new_zip)
            self.zip_code = new_zip
            self.refresh()

    def refresh(self):
        try:
            loc = get_location_from_zip(self.zip_code)
            current = get_current_weather(loc["lat"], loc["lon"])
            avg = get_monthly_averages(loc["lat"], loc["lon"])
            result = is_nice_out(current, avg)

            msg = "YES!" if result else "Nope"
            color = "green" if result else "red"
            self.status.configure(text=msg, text_color=color)

            self.details.configure(text=(
                f"{loc['name']} ({self.zip_code})\n"
                f"Now: {current['temp']}°F with {current['humidity']}% humidity\n"
                f"Historical avg temp: {avg['avg_temp']:.1f}°F\n"
                f"Criteria: Temp below avg, 30–50% humidity, no rain"
            ))

        except Exception as e:
            self.status.configure(text="Error", text_color="orange")
            self.details.configure(text=str(e))

    def auto_refresh(self):
        while True:
            self.refresh()
            time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    app = WeatherApp()
    app.mainloop()
