from flask import Flask, jsonify, render_template, abort
import requests, os, csv
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# ======================
# PATHOK
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GTFS_DIR = os.path.join(BASE_DIR, "gtfs")
STOPS_FILE = os.path.join(GTFS_DIR, "stops.txt")

# ======================
# API
# ======================
API_KEY = os.environ.get("BKK_API_KEY", "SAJAT_API_KULCS")
VP_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.pb?key={API_KEY}"
TU_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/TripUpdates.pb?key={API_KEY}"

# ======================
# STOPS BETÖLTÉS
# ======================
STOP_NAMES = {}

if os.path.exists(STOPS_FILE):
    with open(STOPS_FILE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            STOP_NAMES[r["stop_id"]] = r["stop_name"]

# ======================
# OLDALAK
# ======================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/map")
def map_page():
    return render_template("map.html")

@app.route("/vehicles")
def vehicles_page():
    return render_template("vehicles.html")

@app.route("/vehicle/<vehicle_id>")
def vehicle_page(vehicle_id):
    return render_template("vehicle.html", vehicle_id=vehicle_id)

# ======================
# VEHICLE LISTA
# ======================
@app.route("/api/vehicles")
def api_vehicles():
    feed = gtfs_realtime_pb2.FeedMessage()
    r = requests.get(VP_URL, timeout=10)
    feed.ParseFromString(r.content)

    out = []
    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        out.append({
            "vehicle_id": v.vehicle.id,
            "route_id": v.trip.route_id,
            "lat": v.position.latitude,
            "lon": v.position.longitude
        })

    return jsonify(out)

# ======================
# JÁRMŰ + STOP TIMES
# ======================
@app.route("/api/trip/<vehicle_id>")
def api_trip(vehicle_id):
    feed = gtfs_realtime_pb2.FeedMessage()
    r = requests.get(TU_URL, timeout=10)
    feed.ParseFromString(r.content)

    for e in feed.entity:
        if not e.HasField("trip_update"):
            continue

        tu = e.trip_update
        if tu.vehicle.id != vehicle_id:
            continue

        stops = []
        seen = set()

        for stu in tu.stop_time_update:
            stop_id = stu.stop_id
            if stop_id in seen:
                continue
            seen.add(stop_id)

            name = STOP_NAMES.get(stop_id, stop_id)

            if stu.HasField("arrival"):
                t = stu.arrival.time
                delay = stu.arrival.delay
            elif stu.HasField("departure"):
                t = stu.departure.time
                delay = stu.departure.delay
            else:
                continue

            time_str = datetime.fromtimestamp(
                t, tz=timezone(timedelta(hours=2))
            ).strftime("%H:%M")

            if delay > 60:
                delay_text = f"+{delay//60}p"
                delay_state = "late"
            elif delay < -60:
                delay_text = f"{delay//60}p"
                delay_state = "early"
            else:
                delay_text = "időben"
                delay_state = "on_time"

            stops.append({
                "name": name,
                "time": time_str,
                "delay": delay_text,
                "state": delay_state
            })

        return jsonify({
            "vehicle_id": vehicle_id,
            "route_id": tu.trip.route_id,
            "stops": stops
        })

    abort(404)

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
