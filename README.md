# Intelligent Traffic Monitoring

This is the local Python version of the traffic-monitoring notebook.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

Place a traffic video anywhere on your computer and run:

```powershell
python main.py "C:\path\to\traffic_video.mp4"
```

By default, the whole video frame is treated as the road region. For a useful
congestion measurement, pass the road ROI as pixel coordinates:

```powershell
python main.py "C:\path\to\traffic_video.mp4" --road-roi 0 180 1280 720
```

The coordinates are `left top right bottom`. Select only the visible drivable
road area and exclude sky, buildings, sidewalks, and other background. The
program calculates vehicle bounding-box area divided by road ROI area for each
frame. Congestion is based on average and peak occupancy, so the same vehicle
count can produce different results on narrow and wide roads.

To run ANPR as well:

```powershell
python main.py "C:\path\to\traffic_video.mp4" --plate-image "C:\path\to\number_plate.webp"
```

Results are written under `output/detect` and `output/track`.

## React dashboard

Install the API dependencies and start the backend:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn api:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dashboard uses simulated Bengaluru camera
locations, serves the existing `traffic_video.mp4` for each camera, and starts
the real YOLO/ByteTrack pipeline through `POST /api/cameras/{camera_id}/tracking`.
Analytics are polled from `GET /api/jobs/{job_id}`. No municipal CCTV feed is
claimed or required.

The detector is restricted to vehicle classes: car, motorcycle, bus, and truck. Person detections are excluded so motorcycle riders are not counted as motorcycles or vehicles.
