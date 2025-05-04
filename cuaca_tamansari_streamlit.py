import streamlit as st
import requests
import pandas as pd
import json
import base64
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from gspread_dataframe import set_with_dataframe

# === DECODE BASE64 CREDENTIALS ===
def fix_padding(b64_string):
    return b64_string + "=" * (-len(b64_string) % 4)

b64_creds = st.secrets["GOOGLE_CREDS"]
fixed = fix_padding(b64_creds)
GOOGLE_CREDS = json.loads(base64.b64decode(fixed).decode("utf-8"))

# === KONFIGURASI ===
LAT = -6.90389
LON = 107.61861
SPREADSHEET_NAME = "Data Streamlit Cuaca Bandung"
API_KEY = st.secrets["OPENWEATHER_API_KEY"]

st.set_page_config(page_title="Cuaca Tamansari", page_icon="🌧️", layout="centered")
st.title("🌧️ Cuaca Real-Time Tamansari, Bandung")

# Auto-refresh tiap 10 menit (600.000 ms)
st_autorefresh(interval=600000, key="data_refresh")

if 'data_history' not in st.session_state:
    st.session_state['data_history'] = []

# === EMOJI CUACA ===
def weather_emoji(desc):
    desc = desc.lower()
    if "thunderstorm" in desc:
        return "⛈️ " + desc
    elif "drizzle" in desc:
        return "🌦️ " + desc
    elif "rain" in desc:
        return "🌧️ " + desc
    elif "snow" in desc:
        return "❄️ " + desc
    elif any(x in desc for x in ["mist", "smoke", "haze", "fog"]):
        return "🌫️ " + desc
    elif any(x in desc for x in ["sand", "dust", "ash"]):
        return "🌪️ " + desc
    elif any(x in desc for x in ["squall", "tornado"]):
        return "🌪️ " + desc
    elif "clear" in desc:
        return "☀️ " + desc
    elif "few clouds" in desc:
        return "🌤️ " + desc
    elif "scattered clouds" in desc:
        return "🌥️ " + desc
    elif "broken clouds" in desc or "overcast clouds" in desc:
        return "☁️ " + desc
    else:
        return "❓ " + desc

# === SIMPAN KE GOOGLE SHEETS ===
def simpan_ke_google_sheets(df):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SPREADSHEET_NAME).sheet1
    sheet.clear()
    set_with_dataframe(sheet, df)

# === AMBIL DATA DARI OPENWEATHER ===
def fetch_weather():
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang=en"
    try:
        response = requests.get(url)
        data = response.json()

        current = data['current']
        temp = current['temp']
        humidity = current['humidity']
        desc = current['weather'][0]['description']
        icon = current['weather'][0]['icon']
        icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"
        wind = current.get('wind_speed', 0)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        st.session_state['data_history'].append({
            'Time': timestamp,
            'Temperature': temp,
            'Humidity': humidity,
            'Weather': desc,
            'Wind_kmh': wind
        })

        df = pd.DataFrame(st.session_state['data_history'])
        simpan_ke_google_sheets(df)

        return temp, desc, humidity, wind, icon_url, timestamp

    except Exception as e:
        st.error(f"Gagal ambil data: {e}")
        return None, None, None, None, None, None

# === JALANKAN ===
temp, desc, humidity, wind, icon_url, timestamp = fetch_weather()
if temp:
    df = pd.DataFrame(st.session_state['data_history'])

    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(icon_url, width=100)
    with col2:
        st.metric("🌡️ Temperature", f"{temp} °C")
        st.markdown(f"### {weather_emoji(desc)}")
        st.caption(f"Last updated: {timestamp}")

    st.metric("💧 Humidity", f"{humidity}%")
    st.metric("🌬️ Wind Speed", f"{wind} km/h")
    st.line_chart(df.set_index("Time")["Temperature"])

st.caption("🔁 Auto-updated every 10 minutes • Data from OpenWeather • Synced to Google Sheets")
