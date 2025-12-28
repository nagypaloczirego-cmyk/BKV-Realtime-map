
from flask import Flask, jsonify, render_template, send_from_directory, abort
import requests
import os
import csv
from datetime import datetime, timedelta
from google.transit import gtfs_realtime_pb2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "icons")
GTFS_DIR = os.path.join(BASE_DIR, "gtfs")

app = Flask(__name__, template_folder="templates")

API_KEY = "5ad47c1d-0b29-4a6e-854e-ef21b2b76f94"

VEH_PB_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.pb?key={API_KEY}"
VEH_TXT_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.txt?key={API_KEY}"
TRIP_URL   = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/TripUpdates.pb?key={API_KEY}"

# -------------------------------------------------
# GTFS STATIC
# -------------------------------------------------

def load_stops():
    stops = {}
    path = os.path.join(GTFS_DIR, "stops.txt")
    if not os.path.exists(path):
        return stops
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stops[r["stop_id"]] = r["stop_name"]
    return stops

def load_stop_times():
    times = []
    path = os.path.join(GTFS_DIR, "stop_times.txt")
    if not os.path.exists(path):
        return times
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            times.append(r)
    return times

STOPS = load_stops()
STOP_TIMES = load_stop_times()

# -------------------------------------------------
# OLDALAK
# -------------------------------------------------

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

# -------------------------------------------------
# IKONOK
# -------------------------------------------------

@app.route("/icons/<path:filename>")
def icons(filename):
    for name in (filename, filename.replace("é", "e")):
        path = os.path.join(ICON_DIR, name)
        if os.path.exists(path):
            return send_from_directory(ICON_DIR, name)
    abort(404)

# -------------------------------------------------
# RENDSZÁM (TXT)
# -------------------------------------------------

def parse_txt():
    try:
        text = requests.get(VEH_TXT_URL, timeout=10).text
    except:
        return {}

    data = {}
    vid = None
    for line in text.splitlines():
        l = line.strip()
        if l.startswith('id: "'):
            vid = l.split('"')[1]
            data[vid] = {"license_plate": "N/A"}
        elif vid and "license_plate" in l:
            data[vid]["license_plate"] = l.split('"')[1]
    return data

# -------------------------------------------------
# API – JÁRMŰVEK
# -------------------------------------------------

@app.route("/api/vehicles")
def vehicles_api():
    plates = parse_txt()
    feed = gtfs_realtime_pb2.FeedMessage()
    out = []

    try:
        r = requests.get(VEH_PB_URL, timeout=10)
        feed.ParseFromString(r.content)
    except:
        return jsonify([])

    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        if not v.HasField("position"):
            continue

        vid = v.vehicle.id
        out.append({
            "vehicle_id": vid,
            "trip_id": v.trip.trip_id,
            "route_id": v.trip.route_id,
            "license_plate": plates.get(vid, {}).get("license_plate", "N/A"),
            "latitude": v.position.latitude,
            "longitude": v.position.longitude
        })

    return jsonify(out)

# -------------------------------------------------
# API – MENET (HELYES, STABIL KÉSÉS)
# -------------------------------------------------

@app.route("/trip/<trip_id>")
def trip_details(trip_id):
    now = datetime.now()

    trip_stops = [s for s in STOP_TIMES if s["trip_id"] == trip_id]
    if not trip_stops:
        return jsonify({"delay_txt": "időben", "delay_type": "ontime", "stops": []})

    trip_stops.sort(key=lambda x: int(x["stop_sequence"]))

    # 🔑 KÖVETKEZŐ megálló keresése
    base_delay = 0
    found = False

    for s in trip_stops:
        try:
            hh, mm, *_ = s["arrival_time"].split(":")
            hh = int(hh)
            mm = int(mm)

            sched = now.replace(hour=hh % 24, minute=mm, second=0)
            if hh >= 24:
                sched += timedelta(days=1)

            diff = int((now - sched).total_seconds() / 60)

            # első jövőbeli / éppen aktuális megálló
            if diff <= 2:
                base_delay = diff
                found = True
                break
        except:
            continue

    if not found:
        base_delay = 0

    if base_delay > 1:
        delay_txt = f"+{base_delay} perc"
        delay_type = "late"
    elif base_delay < -1:
        delay_txt = f"{base_delay} perc"
        delay_type = "early"
    else:
        delay_txt = "időben"
        delay_type = "ontime"

    stops = []
    for s in trip_stops:
        hh, mm, *_ = s["arrival_time"].split(":")
        time_str = f"{int(hh)%24:02d}:{mm}"
        stops.append({
            "stop_name": STOPS.get(s["stop_id"], s["stop_id"]),
            "time": time_str
        })

    return jsonify({
        "delay_txt": delay_txt,
        "delay_type": delay_type,
        "stops": stops
    })

# -------------------------------------------------
# START
# -------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

from flask import Flask, jsonify, render_template, send_from_directory, abort
import requests
import os
import csv
from datetime import datetime, timedelta
from google.transit import gtfs_realtime_pb2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "icons")
GTFS_DIR = os.path.join(BASE_DIR, "gtfs")

app = Flask(__name__, template_folder="templates")

API_KEY = "5ad47c1d-0b29-4a6e-854e-ef21b2b76f94"

VEH_PB_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.pb?key={API_KEY}"
VEH_TXT_URL = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.txt?key={API_KEY}"
TRIP_URL   = f"https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/TripUpdates.pb?key={API_KEY}"

# -------------------------------------------------
# GTFS STATIC
# -------------------------------------------------

def load_stops():
    stops = {}
    path = os.path.join(GTFS_DIR, "stops.txt")
    if not os.path.exists(path):
        return stops
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stops[r["stop_id"]] = r["stop_name"]
    return stops

def load_stop_times():
    times = []
    path = os.path.join(GTFS_DIR, "stop_times.txt")
    if not os.path.exists(path):
        return times
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            times.append(r)
    return times

STOPS = load_stops()
STOP_TIMES = load_stop_times()

# -------------------------------------------------
# OLDALAK
# -------------------------------------------------

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

# -------------------------------------------------
# IKONOK
# -------------------------------------------------

@app.route("/icons/<path:filename>")
def icons(filename):
    for name in (filename, filename.replace("é", "e")):
        path = os.path.join(ICON_DIR, name)
        if os.path.exists(path):
            return send_from_directory(ICON_DIR, name)
    abort(404)

# -------------------------------------------------
# RENDSZÁM (TXT)
# -------------------------------------------------

def parse_txt():
    try:
        text = requests.get(VEH_TXT_URL, timeout=10).text
    except:
        return {}

    data = {}
    vid = None
    for line in text.splitlines():
        l = line.strip()
        if l.startswith('id: "'):
            vid = l.split('"')[1]
            data[vid] = {"license_plate": "N/A"}
        elif vid and "license_plate" in l:
            data[vid]["license_plate"] = l.split('"')[1]
    return data

# -------------------------------------------------
# API – JÁRMŰVEK
# -------------------------------------------------

@app.route("/api/vehicles")
def vehicles_api():
    plates = parse_txt()
    feed = gtfs_realtime_pb2.FeedMessage()
    out = []

    try:
        r = requests.get(VEH_PB_URL, timeout=10)
        feed.ParseFromString(r.content)
    except:
        return jsonify([])

    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        if not v.HasField("position"):
            continue

        vid = v.vehicle.id
        out.append({
            "vehicle_id": vid,
            "trip_id": v.trip.trip_id,
            "route_id": v.trip.route_id,
            "license_plate": plates.get(vid, {}).get("license_plate", "N/A"),
            "latitude": v.position.latitude,
            "longitude": v.position.longitude
        })

    return jsonify(out)

# -------------------------------------------------
# API – MENET (HELYES, STABIL KÉSÉS)
# -------------------------------------------------

@app.route("/trip/<trip_id>")
def trip_details(trip_id):
    now = datetime.now()

    trip_stops = [s for s in STOP_TIMES if s["trip_id"] == trip_id]
    if not trip_stops:
        return jsonify({"delay_txt": "időben", "delay_type": "ontime", "stops": []})

    trip_stops.sort(key=lambda x: int(x["stop_sequence"]))

    # 🔑 KÖVETKEZŐ megálló keresése
    base_delay = 0
    found = False

    for s in trip_stops:
        try:
            hh, mm, *_ = s["arrival_time"].split(":")
            hh = int(hh)
            mm = int(mm)

            sched = now.replace(hour=hh % 24, minute=mm, second=0)
            if hh >= 24:
                sched += timedelta(days=1)

            diff = int((now - sched).total_seconds() / 60)

            # első jövőbeli / éppen aktuális megálló
            if diff <= 2:
                base_delay = diff
                found = True
                break
        except:
            continue

    if not found:
        base_delay = 0

    if base_delay > 1:
        delay_txt = f"+{base_delay} perc"
        delay_type = "late"
    elif base_delay < -1:
        delay_txt = f"{base_delay} perc"
        delay_type = "early"
    else:
        delay_txt = "időben"
        delay_type = "ontime"

    stops = []
    for s in trip_stops:
        hh, mm, *_ = s["arrival_time"].split(":")
        time_str = f"{int(hh)%24:02d}:{mm}"
        stops.append({
            "stop_name": STOPS.get(s["stop_id"], s["stop_id"]),
            "time": time_str
        })

    return jsonify({
        "delay_txt": delay_txt,
        "delay_type": delay_type,
        "stops": stops
    })

# -------------------------------------------------
# START
# -------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
 dab0cf4150e19a1efd2c62702252ccf900e9506a
