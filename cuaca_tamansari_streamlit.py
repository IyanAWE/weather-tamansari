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
from pytz import timezone

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
BMKG_SPREADSHEET_ID = "1Eac7sce0H0pkg3PQslBhjPcAc_5nMw-AFFZCgKUabNQ"
wib = timezone("Asia/Jakarta")

st.set_page_config(page_title="Cuaca Tamansari", page_icon="🌧️", layout="wide")
st.title("🌧️ Dashboard Cuaca Tamansari: OpenWeather vs BMKG (OCR)")

# === AUTO REFRESH TRIGGER ===
refresh_trigger = st_autorefresh(interval=900000, key="data_refresh")  # 15 menit

# === SESSION STATE ===
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
    elif any(x in desc for x in ["sand", "dust", "ash", "squall", "tornado"]):
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

    existing = sheet.get_all_values()
    if not existing:
        header = list(df.columns)
        sheet.append_row(header)

    last_row = df.tail(1).values.tolist()[0]
    sheet.append_row(last_row)

# === BACA DATA DARI BMKG SHEET ===
def ambil_data_bmkg_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(BMKG_SPREADSHEET_ID).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# === FETCH DATA OPENWEATHER ===
API_KEY = st.secrets["OPENWEATHER_API_KEY"]

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
        timestamp = datetime.now(wib).strftime('%Y-%m-%d %H:%M:%S')

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
        st.error(f"Gagal ambil data OpenWeather: {e}")
        return None, None, None, None, None, None

# === JALANKAN FETCH ===
do_refresh = st.button("🔁 Refresh Now") or refresh_trigger > 0

if do_refresh:
    temp, desc, humidity, wind, icon_url, timestamp = fetch_weather()
else:
    temp, desc, humidity, wind, icon_url, timestamp = None, None, None, None, None, None

# === UI DISPLAY (2 KOLOM) ===
col1, col2 = st.columns(2)

with col1:
    st.header("📡 OpenWeather (Live API)")
    if temp:
        st.image(icon_url, width=100)
        st.metric("🌡️ Temperature", f"{temp} °C")
        st.metric("💧 Humidity", f"{humidity}%")
        st.metric("🌬️ Wind Speed", f"{wind} km/h")
        st.markdown(f"### {weather_emoji(desc)}")
        st.caption(f"Last updated: {timestamp}")
    else:
        st.info("Belum ada data OpenWeather.")

with col2:
    st.header("🛰️ BMKG via OCR (Google Sheets)")
    try:
        df_bmkg = ambil_data_bmkg_sheet()
        if not df_bmkg.empty:
            latest = df_bmkg.tail(1).squeeze()
            st.metric("🌡️ Temperature", f"{latest['Temperature']} °C")
            st.metric("💧 Humidity", f"{latest['Humidity']}%")
            st.metric("🌬️ Wind Speed", f"{latest['Wind_kmh']} km/h")
            st.markdown(f"### ☁️ {latest['Weather']}")
            st.caption(f"Last updated: {latest['Time']}")
        else:
            st.info("Belum ada data dari Sheet BMKG.")
    except Exception as e:
        st.warning(f"⚠️ Gagal ambil data dari Sheet BMKG: {e}")

st.caption("🔁 Auto-updated every 15 minutes • Left: OpenWeather API • Right: BMKG OCR via Sheets")
