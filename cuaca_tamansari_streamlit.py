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
import matplotlib.pyplot as plt

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
API_KEY = st.secrets["OPENWEATHER_API_KEY"]
wib = timezone("Asia/Jakarta")

st.set_page_config(page_title="Cuaca Tamansari", page_icon="🌧️", layout="wide")
st.title("🌧️ Dashboard Cuaca Tamansari: OpenWeather vs BMKG (OCR)")

# === AUTO REFRESH TRIGGER ===
refresh_trigger = st_autorefresh(interval=900000, key="data_refresh")  # 15 menit

if 'data_history' not in st.session_state:
    st.session_state['data_history'] = []

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

# === BACA DATA DARI BMKG (Real-Time + Forecast) ===
def ambil_data_bmkg_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(BMKG_SPREADSHEET_ID).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def ambil_forecast_bmkg():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(BMKG_SPREADSHEET_ID).worksheet("HourlyForecast")
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# === FETCH OPENWEATHER DATA ===
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

do_refresh = st.button("🔁 Refresh Now") or refresh_trigger > 0

if do_refresh:
    temp, desc, humidity, wind, icon_url, timestamp = fetch_weather()
else:
    temp, desc, humidity, wind, icon_url, timestamp = None, None, None, None, None, None

# === UI: 2 KOLOM
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
            st.info("Belum ada data dari BMKG.")
    except Exception as e:
        st.warning(f"⚠️ Gagal baca BMKG Real-Time: {e}")

# === Forecast BMKG OCR (jam-jaman)
try:
    df_forecast = ambil_forecast_bmkg()
    if not df_forecast.empty:
        st.subheader("📆 Forecast BMKG (OCR)")
        if 'Capture Time' in df_forecast.columns:
            df_forecast = df_forecast.drop(columns=['Capture Time'])
        df_forecast = df_forecast[df_forecast['Time'].str.contains(r'^\d{2}[.:]\d{2}$', regex=True, na=False)]
        df_forecast['Time'] = df_forecast['Time'].str.replace('.', ':', regex=False) + " WIB"
        def jam_to_int(t):
            try:
                return int(t.split(":")[0])
            except:
                return 99
        df_forecast = df_forecast.sort_values(by='Time', key=lambda x: x.map(jam_to_int))
        st.table(df_forecast.reset_index(drop=True))
except Exception as e:
    st.warning(f"⚠️ Gagal ambil forecast BMKG: {e}")

# === GRAFIK SUHU HISTORIS ===
def tampilkan_grafik_suhu(df_open, df_bmkg):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df_open["Time"], df_open["Temperature"], marker='o', label="OpenWeather")
    ax.plot(df_bmkg["Time"], df_bmkg["Temperature"], marker='x', label="BMKG OCR")
    ax.set_title("📊 Grafik Suhu Historis")
    ax.set_xlabel("Waktu")
    ax.set_ylabel("Suhu (°C)")
    ax.legend()
    ax.grid(True)
    fig.autofmt_xdate()
    st.pyplot(fig)

try:
    df_open = pd.DataFrame(st.session_state['data_history'])
    df_open["Time"] = pd.to_datetime(df_open["Time"], errors='coerce')
    df_open["Temperature"] = pd.to_numeric(df_open["Temperature"], errors='coerce')
    df_open = df_open.dropna(subset=["Time", "Temperature"])

    df_bmkg = ambil_data_bmkg_sheet()
    df_bmkg["Time"] = pd.to_datetime(df_bmkg["Time"], errors='coerce')
    df_bmkg["Temperature"] = pd.to_numeric(df_bmkg["Temperature"], errors='coerce')
    df_bmkg = df_bmkg.dropna(subset=["Time", "Temperature"])

    st.subheader("📈 Grafik Suhu Historis")
    tampilkan_grafik_suhu(df_open.tail(12), df_bmkg.tail(12))

except Exception as e:
    st.warning(f"⚠️ Gagal tampilkan grafik suhu: {e}")

st.caption("🔁 Auto-refresh tiap 30 menit | Kiri: OpenWeather API • Kanan: BMKG OCR + Grafik")
