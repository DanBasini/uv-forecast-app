from flask import Flask, render_template, request, send_file
import requests
import io
import matplotlib.pyplot as plt
import numpy as np
import base64
from datetime import datetime

app = Flask(__name__)

def get_coordinates(city_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1"
    response = requests.get(url)
    data = response.json()
    if not data.get("results"):
        raise ValueError("City not found")
    result = data["results"][0]
    return result["latitude"], result["longitude"], result["name"], result["country"]

def get_forecast(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=uv_index,cloudcover&daily=uv_index_max,cloudcover_mean"
        f"&timezone=auto"
    )
    response = requests.get(url)
    return response.json()

def adjust_uv_for_clouds(uv_index, cloud_coverage):
    if cloud_coverage < 20:
        factor = 1.0
    elif cloud_coverage < 50:
        factor = 0.8
    elif cloud_coverage < 75:
        factor = 0.5
    else:
        factor = 0.3
    return round(uv_index * factor, 2)

def generate_uv_chart(date, hourly_data):
    times, uv_raw, uv_adj, clouds = [], [], [], []
    for hour, uv, cloud, adjusted in hourly_data:
        hour_int = int(hour.split(":")[0])
        if 6 <= hour_int <= 18:
            times.append(f"{hour}")
            uv_raw.append(uv)
            uv_adj.append(adjusted)
            clouds.append(cloud)

    x = np.arange(len(times))
    fig, ax1 = plt.subplots(figsize=(6, 3), dpi=100)
    fig.suptitle(f"\u2600\ufe0f UV Forecast for {date}", fontsize=12, weight="bold")

    ax1.bar(x, uv_raw, width=0.6, color='lightgrey', label='UV Index (Raw)')
    ax1.bar(x, uv_adj, width=0.4, color='white', label='UV Index (Adjusted)')
    ax1.set_ylabel("UV Index", fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(times, rotation=45)
    ax1.set_ylim(0, np.ceil(max(uv_raw + uv_adj)) + 1)

    ax2 = ax1.twinx()
    ax2.plot(x, clouds, color='dodgerblue', linewidth=2, label='Cloud Cover (%)', marker='o')
    ax2.set_ylabel("Cloud Cover (%)", fontsize=10)
    ax2.set_ylim(0, 100)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc='lower center', bbox_to_anchor=(0.5, -0.3), ncol=3, fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])

    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    encoded = base64.b64encode(img.read()).decode('utf-8')
    plt.close(fig)
    return encoded

def organize_forecast_data(forecast):
    forecast_data_by_day = {}
    hourly_times = forecast["hourly"]["time"]
    uv_hourly = forecast["hourly"]["uv_index"]
    cloud_hourly = forecast["hourly"]["cloudcover"]

    daily_times = forecast["daily"]["time"]
    uv_daily = forecast["daily"]["uv_index_max"]
    cloud_daily = forecast["daily"]["cloudcover_mean"]

    for i in range(len(hourly_times)):
        dt = hourly_times[i]
        date = dt.split("T")[0]
        hour = dt.split("T")[1]
        uv = uv_hourly[i]
        cloud = cloud_hourly[i]
        adjusted = adjust_uv_for_clouds(uv, cloud)
        if date not in forecast_data_by_day:
            forecast_data_by_day[date] = {"hourly": [], "daily": None}
        forecast_data_by_day[date]["hourly"].append((hour, uv, cloud, adjusted))

    for i in range(len(daily_times)):
        date = daily_times[i]
        if date not in forecast_data_by_day:
            forecast_data_by_day[date] = {"hourly": [], "daily": None}
        uv = uv_daily[i]
        cloud = cloud_daily[i]
        adjusted = adjust_uv_for_clouds(uv, cloud)
        forecast_data_by_day[date]["daily"] = (uv, cloud, adjusted)

    return forecast_data_by_day

@app.route('/', methods=['GET', 'POST'])
def index():
    city = request.form.get('city')
    chart = None
    forecast_text = None
    if city:
        try:
            lat, lon, name, country = get_coordinates(city)
            forecast = get_forecast(lat, lon)
            forecast_data = organize_forecast_data(forecast)
            date = sorted(forecast_data.keys())[0]
            hourly_data = forecast_data[date]["hourly"]
            chart = generate_uv_chart(date, hourly_data)
            forecast_text = [(hour, uv, cloud, adj) for hour, uv, cloud, adj in hourly_data]
        except Exception as e:
            forecast_text = [("Error", str(e), "", "")]

    return render_template('index.html', chart=chart, forecast=forecast_text)

if __name__ == '__main__':
    app.run(debug=True)
