# CityPulse AI — Intelligent Traffic Monitoring

CityPulse AI is a local Smart India Hackathon prototype for city-wide traffic analytics. It uses computer vision and ANPR-oriented workflows to process pre-recorded camera feeds, track vehicles, estimate congestion, predict a route by time, and present the results in an interactive Bengaluru dashboard.

## Features

- Vehicle detection and tracking with YOLO and ByteTrack.
- Per-camera traffic analytics for cars, buses, trucks, and motorcycles.
- Traffic-intensity and route-congestion prediction.
- Interactive Leaflet camera map with a heatmap toggle and road-following route geometry (using OSRM when available).
- Searchable camera and route selectors, responsive analysis charts, and downloadable CSV/JSON reports.
- OpenCity Bengaluru camera-location catalogue nodes (location metadata only; not municipal feed access).
- Live Tracking slots for explicitly authorised external traffic feeds, plus an India-first number-plate image OCR page.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer with npm
- Git (only needed for cloning or contributing)

## Backend setup

Run these commands from the project root — the folder containing `api.py` and `requirements.txt`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## TomTom production traffic

Copy `.env.example` to `.env` and set `TOMTOM_API_KEY` on the backend host. The key is read only by FastAPI and must never be added as a `VITE_*` frontend variable. The dashboard requests TomTom Flow Segment data for each Bengaluru node every 60 seconds and shows current/free-flow speed, delay, confidence, and a red congestion heat halo.

Live Tracking only starts when each `live_feeds.json` entry has an authorised direct `stream_url` plus valid Bengaluru coordinates. Public camera-directory pages are attribution links only; the application does not scrape or extract their protected media streams.

## Precompute camera analytics

The dashboard plays precomputed original and tracked feeds together. Process the configured videos before starting the dashboard:

```powershell
python precompute.py
```

To process one camera while testing:

```powershell
python precompute.py --camera-id CAM-BLR-02
```

Generated files are stored under `output/cameras/{camera_id}`. Use `--force` to regenerate an existing camera after changing the source video or road ROI.

## Run the app

Start the FastAPI backend from the project root:

```powershell
python -m uvicorn api:app --reload --port 8000
```

In a second PowerShell terminal, start the React frontend:

```powershell
cd frontend
npm install
npm run dev
```

If npm is blocked by PowerShell execution policy, use:

```powershell
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173`.

## Frontend notes

- Route lines use the public OSRM driving service to follow roads. If it is unavailable, the UI shows an approximate fallback route and a notice.
- SmoothUI-inspired controls and animations are included locally under `frontend/components/ui/smoothui`. The application remains standard Vite React/CSS; no Tailwind migration is required.
- Run a production check with `npm.cmd run build` from `frontend`.

## Project structure

```text
api.py                 FastAPI endpoints and camera metadata
precompute.py          Precomputes detection, tracking, and analytics
frontend/              Vite + React dashboard
videos/                Input camera videos
output/cameras/        Generated camera manifests and tracked videos
```

## Privacy note

This prototype works with local, pre-recorded demonstration footage. It does not claim to use live municipal CCTV feeds.

## Camera catalogue and live feeds

At startup the API refreshes a spatially balanced sample of 100 Bengaluru camera locations from OpenCity and caches the last valid result in `data/bengaluru_camera_catalogue.json`. The source is credited as OpenCity / Thejesh GN and OpenStreetMap under CC BY-NC-SA 4.0. Catalogue nodes never imply video access.

`live_feeds.json` contains the three supplied OpenCCTV camera pages. The Live Tracking page embeds each source page beside a ByteTrack result panel. A camera page is not itself a machine-readable video stream, so server-side tracking remains on standby until an authorised direct `stream_url` (MJPEG, RTSP, or HLS) is configured for that feed. This preserves a clear distinction between viewing an external page and processing its video. Do not add direct stream URLs unless their terms permit display and automated analysis.

The Number Plate Recognition page processes an uploaded JPEG, PNG, or WebP image transiently. It requires review before India registration-area lookup and returns a masked plate plus salted hash; it does not determine a vehicle's current location.

## On-demand live tracking

The Live Tracking page uses one camera registry for the local MP4 demos, authorised configured streams, and location-only catalogue nodes. `DEMO-BLR-LOCAL` is enabled by default and loops `videos/cam_blr_01.mp4` so it is the guaranteed SIH demonstration path. Choose **Start tracking** to begin YOLO + ByteTrack; choose **Stop tracking** to release it.

Configured entries in `live_feeds.json` support `mp4`, `mjpeg`, `hls`, and `rtsp`. Set `stream_type` to `none` whenever there is no authorised machine-readable source. For private URLs, set `source_env` to a `CAMERA_*` environment variable defined only on the backend host. RTSP is processed server-side and displayed to the browser as MJPEG; its credentials are never returned by the API.

Canonical tracking endpoints are:

- `GET /api/cameras/{camera_id}` and `GET /api/cameras/{camera_id}/status`
- `POST /api/cameras/{camera_id}/tracking/start` and `POST /api/cameras/{camera_id}/tracking/stop`
- `GET /api/cameras/{camera_id}/tracking`
- `GET /api/cameras/{camera_id}/stream?view=tracked` (or `original`)

At most three sessions run at once. A failed source changes only that camera to an error state; it does not stop the API. Run `python -m unittest discover -s tests -v` and `npm.cmd run build` from `frontend` to verify the implementation.
