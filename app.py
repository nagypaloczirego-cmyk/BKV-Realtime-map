from flask import Flask, jsonify, render_template, abort
import requests
import os
import zipfile
from datetime import datetime, timedelta
from google.transit import gtfs_realtime_pb2

# ==============================
# GTFS AUTO DOWNLOAD (Render safe)
# ==============================

GTFS_DIR = "gtfs"
GTFS_ZIP_URL = "https://opendata.bkk.hu/gtfs/budapest_gtfs.zip"
GTFS_ZIP_PATH = "gtfs.zip"
STOP_TIMES_FILE = os.path.join(GTFS_DIR, "stop_times.txt")
STOPS_FILE = os.path.join(GTFS_DIR, "stops.txt")


def ensure_gtfs():
    if os.path.exists(STOP_TIMES_FILE) and os.path.exists(STOPS_FILE):
        print("GTFS already present.")
        return

    print("GTFS not found, downloading...")
    os.makedirs(GTFS_DIR, exist_ok=True)

    r = requests.get(GTFS_ZIP_URL, timeout=60)
    r.raise_for_status()

    with open(GTFS_ZIP_PATH, "wb") as f:
        f.write(r.content)

    with zipfile.ZipFile(GTFS_ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(GTFS_DIR)

    os.remove(GTFS_ZIP_PATH)
    print("GTFS download complete.")


# ==============================
# Flask app
# ==============================

app = Flask(__name__)
ensure_gtfs()

# ==============================
# BKK realtime API
# ==============================

API_KEY = os.environ.get("BKK_API_KEY", "")
PB_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.pb?key={API_KEY}"
TRIP_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/TripUpdates.pb?key={API_KEY}"


# ==============================
# Load GTFS static data
# ==============================

def load_stops():
    stops = {}
    with open(STOPS_FILE, encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            stops[parts[0]] = parts[2]
    return stops


STOPS = load_stops()


# ==============================
# Routes
# ==============================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/map")
def map_view():
    return render_template("map.html")


@app.route("/vehicles")
def vehicles_view():
    return render_template("vehicles.html")


# ==============================
# API: Vehicle list
# ==============================

@app.route("/api/vehicles")
def api_vehicles():
    feed = gtfs_realtime_pb2.FeedMessage()
    r = requests.get(PB_URL, timeout=10)
    feed.ParseFromString(r.content)

    vehicles = []

    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        if not v.HasField("position"):
            continue

        vehicles.append({
            "vehicle_id": v.vehicle.id,
            "route_id": v.trip.route_id,
            "latitude": v.position.latitude,
            "longitude": v.position.longitude,
            "license_plate": v.vehicle.label or "N/A"
        })

    vehicles.sort(key=lambda x: x["license_plate"])
    return jsonify(vehicles)


# ==============================
# API: Trip details
# ==============================

@app.route("/trip/<trip_id>")
def trip_details(trip_id):
    feed = gtfs_realtime_pb2.FeedMessage()
    r = requests.get(TRIP_URL, timeout=10)
    feed.ParseFromString(r.content)

    trip_update = None
    for e in feed.entity:
        if e.HasField("trip_update") and e.trip_update.trip.trip_id == trip_id:
            trip_update = e.trip_update
            break

    if not trip_update:
        abort(404)

    stops = []
    total_delay = 0
    delay_count = 0

    for stu in trip_update.stop_time_update:
        stop_id = stu.stop_id
        name = STOPS.get(stop_id, stop_id)

        if stu.HasField("arrival") and stu.arrival.HasField("time"):
            arrival_time = datetime.fromtimestamp(stu.arrival.time).strftime("%H:%M")
            delay = stu.arrival.delay
        else:
            arrival_time = "?"
            delay = 0

        if delay:
            total_delay += delay
            delay_count += 1

        stops.append({
            "name": name,
            "time": arrival_time
        })

    avg_delay = int(total_delay / delay_count) if delay_count else 0

    if avg_delay > 60:
        status = f"+{avg_delay // 60}p"
        status_color = "red"
    elif avg_delay < -60:
        status = f"{avg_delay // 60}p"
        status_color = "green"
    else:
        status = "időben"
        status_color = "gray"

    return render_template(
        "vehicle.html",
        trip_id=trip_id,
        stops=stops,
        status=status,
        status_color=status_color
    )


# ==============================
# Run locally
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
