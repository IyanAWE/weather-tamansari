import streamlit as st
import requests
import pandas as pd
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import os

# --- CONFIG ---
API_KEY = os.getenv("OPENWEATHER_API_KEY")
LAT = -6.90389
LON = 107.61861
DATA_CSV = "data_cuaca_tamansari.csv"

st.set_page_config(page_title="Tamansari Weather", page_icon="🌦️", layout="centered")
st.title("🌦️ Real-Time Weather in Tamansari, Bandung")

# Refresh every 10 minutes
refresh_counter = st_autorefresh(interval=600 * 1000, key="auto_refresh")

# Init history
if 'data_history' not in st.session_state:
    if os.path.exists(DATA_CSV):
        st.session_state['data_history'] = pd.read_csv(DATA_CSV).to_dict('records')
    else:
        st.session_state['data_history'] = []

placeholder = st.empty()
chart_placeholder = st.empty()

# --- WEATHER ICON EMOJI MAP ---
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
    elif "mist" in desc or "smoke" in desc or "haze" in desc or "fog" in desc:
        return "🌫️ " + desc
    elif "sand" in desc or "dust" in desc or "ash" in desc:
        return "🌪️ " + desc
    elif "squall" in desc or "tornado" in desc:
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

# --- FETCH WEATHER DATA ---
def fetch_weather():
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang=en"
    try:
        response = requests.get(url)
        data = response.json()

        current = data['current']
        temp = current['temp']
        humidity = current['humidity']
        description = current['weather'][0]['description']
        icon = current['weather'][0]['icon']
        icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"
        wind_speed = current.get('wind_speed', 0)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        st.session_state['data_history'].append({
            'Time': timestamp,
            'Temperature': temp,
            'Humidity': humidity,
            'Weather': description,
            'Wind_kmh': wind_speed
        })

        df = pd.DataFrame(st.session_state['data_history'])
        df.to_csv(DATA_CSV, index=False)

        return temp, description, humidity, wind_speed, icon_url, timestamp

    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return None, None, None, None, None, None

# --- UI HANDLING ---
show_ui = False
if st.button("Refresh Now") or refresh_counter > 0:
    temp, desc, humidity, wind, icon_url, time_str = fetch_weather()
    show_ui = temp is not None

if show_ui:
    df = pd.DataFrame(st.session_state['data_history'])

    with placeholder.container():
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(icon_url, width=100)
        with col2:
            st.metric("🌡️ Temperature", f"{temp} °C")
            st.markdown(f"### {weather_emoji(desc)}")
            st.caption(f"Last updated: {time_str}")

        st.metric("💧 Humidity", f"{humidity}%")
        st.metric("🌬️ Wind Speed", f"{wind} km/h")

    with chart_placeholder.container():
        st.line_chart(df.set_index('Time')['Temperature'])

st.caption("🔁 Powered by OpenWeather • Auto-updates every 10 minutes • Icons + description synced 🚀")
