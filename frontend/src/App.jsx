import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";

const API_URL = import.meta.env.VITE_API_URL || "";
const BENGALURU_CENTER = [12.9716, 77.5946];

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.text();
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    throw new Error(`API returned ${response.status}: ${body.slice(0, 120)}`);
  }
  if (!response.ok) {
    throw new Error(payload.detail || `API request failed (${response.status})`);
  }
  return payload;
}

function formatPercent(value) {
  return value == null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

function statusFromAnalytics(analytics) {
  if (!analytics) return "Awaiting analysis";
  const peak = analytics.peak_occupancy;
  if (peak >= 0.35) return "Heavy";
  if (peak >= 0.2) return "Moderate";
  return "Low";
}

function App() {
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [loadingCameras, setLoadingCameras] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchJson(`${API_URL}/api/cameras`)
      .then((items) => {
        setCameras(items);
        setSelectedCamera(items[0] || null);
      })
      .catch((reason) => setError(reason.message))
      .finally(() => setLoadingCameras(false));
  }, []);

  const selectCamera = (camera) => {
    setSelectedCamera(camera);
    setError("");
  };

  const analytics = selectedCamera?.analytics;
  const trackingReady = selectedCamera?.tracking_ready;
  const trafficStatus = statusFromAnalytics(analytics);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark">CP</span>
          <div>
            <p className="eyebrow">CITYPULSE AI</p>
            <h1>Traffic command view</h1>
          </div>
        </div>
        <div className="mode-chip"><span className="pulse" /> Simulated CCTV network</div>
      </header>

      <section className="intro-row">
        <div>
          <p className="eyebrow">BENGALURU / LIVE ANALYSIS WORKSPACE</p>
          <h2>See the city move.</h2>
          <p className="lede">Select a simulated camera to compare the prerecorded feed with its preprocessed YOLO and ByteTrack output.</p>
        </div>
        <div className="network-stat"><strong>{cameras.length || "--"}</strong><span>camera nodes</span></div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="workspace">
        <div className="map-panel panel">
          <div className="panel-heading">
            <div><span className="section-kicker">01 / NETWORK MAP</span><h3>Bengaluru camera grid</h3></div>
            <span className="map-hint">Click a node to inspect</span>
          </div>
          <div className="map-wrap">
            {loadingCameras ? <div className="map-state">Loading camera network...</div> : (
              <MapContainer center={BENGALURU_CENTER} zoom={11} scrollWheelZoom className="map">
                <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {cameras.map((camera) => (
                  <CircleMarker
                    key={camera.id}
                    center={[camera.latitude, camera.longitude]}
                    radius={selectedCamera?.id === camera.id ? 12 : 8}
                    pathOptions={{ color: selectedCamera?.id === camera.id ? "#ffcc66" : "#25d0c3", fillColor: selectedCamera?.id === camera.id ? "#ffcc66" : "#25d0c3", fillOpacity: 0.9, weight: 3 }}
                    eventHandlers={{ click: () => selectCamera(camera) }}
                  >
                    <Tooltip>{camera.id} · {camera.location}</Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>
            )}
          </div>
          <div className="map-footer"><span><i className="legend-dot" /> Connected simulation</span><span>OpenStreetMap base layer</span></div>
        </div>

        <aside className="camera-panel panel">
          <div className="panel-heading"><div><span className="section-kicker">02 / SELECTED FEED</span><h3>{selectedCamera?.id || "No camera selected"}</h3></div><span className={`status-label ${trafficStatus.toLowerCase().replace(" ", "-")}`}>{trafficStatus}</span></div>
          {selectedCamera ? <>
            <div className="camera-meta"><span>{selectedCamera.location}</span><span>{selectedCamera.metadata}</span></div>
            <div className="video-stack">
              <div className="video-frame">
                {trackingReady ? <video key={selectedCamera.tracked_video_url} src={`${API_URL}${selectedCamera.tracked_video_url}`} controls autoPlay muted loop playsInline /> : <div className="video-state">Run precompute.py before opening this feed.</div>}
                <span className="feed-tag">TRACKED VIDEO</span>
              </div>
              <div className="video-frame source-video">
                <video key={selectedCamera.video_url} src={`${API_URL}${selectedCamera.video_url}`} controls autoPlay muted loop playsInline />
                <span className="feed-tag source-tag">ORIGINAL VIDEO</span>
              </div>
            </div>
          </> : <div className="empty-state">Choose a camera marker to load its feed.</div>}
        </aside>
      </section>

      <section className="analytics-section">
        <div className="panel-heading"><div><span className="section-kicker">03 / PIPELINE OUTPUT</span><h3>Traffic intelligence</h3></div><span className="availability">{analytics ? "Precomputed pipeline response" : "Tracking not precomputed"}</span></div>
        {!analytics ? <div className="empty-analytics">Run the precompute command once to generate the tracking video and analytics for this camera.</div> : <div className="analytics-grid">
          <Metric label="Unique vehicles" value={Object.values(analytics.vehicle_counts).reduce((sum, value) => sum + value, 0)} />
          <Metric label="Average occupancy" value={formatPercent(analytics.average_occupancy)} />
          <Metric label="Peak occupancy" value={formatPercent(analytics.peak_occupancy)} />
          <Metric label="Congestion" value={trafficStatus} />
          <div className="breakdown metric"><span className="metric-label">Vehicle mix</span>{Object.entries(analytics.vehicle_counts).map(([name, count]) => <span className="mix-row" key={name}><span>{name}</span><strong>{count}</strong></span>)}</div>
          <div className="metric unavailable"><span className="metric-label">Average speed</span><strong>Unavailable</strong><small>Not provided by current tracker</small></div>
        </div>}
      </section>
      <footer>CityPulse AI · prerecorded demonstration · not connected to municipal CCTV</footer>
    </main>
  );
}

function Metric({ label, value }) {
  return <div className="metric"><span className="metric-label">{label}</span><strong>{value}</strong></div>;
}

export default App;
