# CityPulse AI — Intelligent Traffic Monitoring

CityPulse AI is a local Smart India Hackathon prototype for city-wide traffic analytics. It uses computer vision and ANPR-oriented workflows to process pre-recorded camera feeds, track vehicles, estimate congestion, predict a route by time, and present the results in an interactive Bengaluru dashboard.

## Features

- Vehicle detection and tracking with YOLO and ByteTrack.
- Per-camera traffic analytics for cars, buses, trucks, and motorcycles.
- Traffic-intensity and route-congestion prediction.
- Interactive Leaflet camera map with a heatmap toggle and road-following route geometry (using OSRM when available).
- Searchable camera and route selectors, responsive analysis charts, and downloadable CSV/JSON reports.

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
