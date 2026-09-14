<<<<<<< HEAD
# Intelligent Traffic Monitoring

This is the local Python version of the traffic-monitoring notebook.

## Setup

Install the following before starting:

- Python 3.10 or newer
- Node.js 18 or newer and npm
- Git, if you are downloading the project with Git

Open PowerShell in the project root, the folder containing `api.py` and
`requirements.txt`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell does not allow environment activation, run the project with the
virtual-environment Python directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The first tracking run may also install the Ultralytics `lap` dependency. If
that happens, run the same command again after installation completes.

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

## Precompute camera tracking

The dashboard uses precomputed tracking videos so the original and tracked
feeds can start together without running YOLO when a map node is clicked. This
step must be completed before starting the dashboard.

From the project root, run:

```powershell
python precompute.py
```

This can take several minutes because YOLO and ByteTrack process every frame.
The command processes all four cameras and can be run again safely; cameras
with valid output are skipped.

To process only one camera while testing:

```powershell
python precompute.py --camera-id CAM-BLR-02
```

Use `--force` to rebuild an existing camera. The generated MP4 and analytics
manifest are stored under `output/cameras/{camera_id}`. The converter uses the
bundled `imageio-ffmpeg` executable. If FFmpeg is already installed separately,
set its executable path with `FFMPEG_PATH` before running the command.

Before running the command, confirm these configured camera source files exist.
Replace them with your
own videos only if you also keep the same camera filenames or update the paths
in `api.py`:

```text
videos/cam_blr_01.mp4
videos/cam_blr_02.mp4
videos/cam_blr_03.mp4
videos/cam_blr_04.mp4
```

Each camera produces its own `tracked.mp4` and `manifest.json`. Re-running the
command skips cameras that are already ready. Use `--force` after replacing a
source video or changing its road ROI.

## React dashboard

After precomputation finishes, start the backend from the project root:

```powershell
python -m uvicorn api:app --reload --port 8000
```

Open a second PowerShell terminal, move to the frontend folder, and install
the JavaScript dependencies once:

```powershell
cd frontend
npm install
npm run dev
```

If `npm` is blocked by PowerShell execution policy, use:

```powershell
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173`. The dashboard displays four simulated Bengaluru
camera locations. Selecting a node immediately switches to that camera's
original video and its precomputed YOLO/ByteTrack video. Both feeds are muted,
set to autoplay, and loop continuously. Selecting a node does not run tracking;
the tracking work is completed by `precompute.py` before the dashboard starts.

The API serves the original feed from
`GET /api/cameras/{camera_id}/video` and the processed feed from
`GET /api/cameras/{camera_id}/tracked-video`. Camera readiness and analytics
are included in `GET /api/cameras`.

If the dashboard reports that tracking is not precomputed, run
`python precompute.py` from the project root and refresh the dashboard. No
municipal CCTV feed is claimed or required.

If tracking reports an FFmpeg error, reinstall the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

The project uses the bundled `imageio-ffmpeg` converter. If you prefer a
separate FFmpeg installation, set its executable path before precomputing:

```powershell
$env:FFMPEG_PATH = "C:\path\to\ffmpeg.exe"
python precompute.py --force
```

The detector is restricted to vehicle classes: car, motorcycle, bus, and truck. Person detections are excluded so motorcycle riders are not counted as motorcycles or vehicles. Select a camera only after precomputation has completed for that camera.
=======
# 🚀 Smart India Hackathon 2026

## Problem Statement

> City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics

## 💡 Our Solution

Our proposed solution:

> CityPulse AI is a centralized AI-powered platform that transforms existing CCTV networks into a unified urban traffic intelligence system. It uses computer vision and ANPR to detect and identify vehicles across multiple cameras, reconstruct their trajectories, and analyze traffic flow. The platform provides real-time congestion monitoring, vehicle journey tracking, traffic anomaly detection, and short-term congestion prediction through an interactive city dashboard. By combining detection, identification, tracking, analytics, and prediction, CityPulse AI enables authorities to make faster, data-driven traffic management decisions.

## 🎯 Objective

What problem are we solving?

## 👥 Team

| Member | Role |
|---|---|
| Sampreeth | Team Lead / Developer |
| Tanay | Developer |
| Rishi | Developer |
| Sumukha | Developer |
| Ruchika | Developer |
| Sunidhi | Developer |

## 🛠️ Tech Stack

- Frontend:
- Backend:
- Database:
- AI/ML:
- Cloud:

## 📌 Project Status

🟡 Planning

## 📂 Project Structure

Coming soon...

## 📄 Documentation

Coming soon...
>>>>>>> e308ba50a66cb3cc59f2065f0f48e6d2e6b9a4fc
