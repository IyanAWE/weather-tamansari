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
API_KEY = st.secrets["OPENWEATHER_API_KEY"]
wib = timezone("Asia/Jakarta")

st.set_page_config(page_title="Cuaca Tamansari", page_icon="🌧️", layout="centered")
st.title("🌧️ Cuaca Real-Time Tamansari, Bandung")

# === AUTO REFRESH TRIGGER ===
refresh_trigger = st_autorefresh(interval=600000, key="data_refresh")  # 10 menit

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

# === FETCH DATA ===
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
        st.error(f"Gagal ambil data: {e}")
        return None, None, None, None, None, None

def simpan_forecast_ke_sheets(df_forecast):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Forecast Cuaca Tamansari")

    try:
        worksheet = spreadsheet.worksheet("Forecast")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="Forecast", rows="1000", cols="10")

    worksheet.clear()
    worksheet.append_row(df_forecast.columns.tolist())
    for row in df_forecast.values.tolist():
        worksheet.append_row(row)


# === JALANKAN FETCH ===
do_refresh = st.button("Refresh Now") or refresh_trigger > 0

if do_refresh:
    temp, desc, humidity, wind, icon_url, timestamp = fetch_weather()
else:
    temp, desc, humidity, wind, icon_url, timestamp = None, None, None, None, None, None

# === TAMPILKAN UI ===
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

    if len(df) > 1:
        st.line_chart(df.set_index("Time")["Temperature"])

    # === HOURLY FORECAST (next 12 hours) ===
    try:
        response = requests.get(f"https://api.openweathermap.org/data/3.0/onecall?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang=en")
        data = response.json()
        if 'hourly' in data:
            hourly_forecast = data['hourly'][:12]  # Next 12 hours
            hourly_data = []
            for h in hourly_forecast:
                ts = datetime.fromtimestamp(h['dt'], tz=wib).strftime('%H:%M')
                temp_hour = h['temp']
                desc_hour = h['weather'][0]['description'].capitalize()
                hourly_data.append({'Time': ts, 'Temp (°C)': temp_hour, 'Weather': desc_hour})

            st.subheader("📆 Prakiraan 12 Jam ke Depan")
            st.table(pd.DataFrame(hourly_data))
    except:
        st.warning("⚠️ Gagal mengambil data hourly forecast.")



st.caption("🔁 Auto-updated every 10 minutes • Data from OpenWeather • Synced to Google Sheets")
