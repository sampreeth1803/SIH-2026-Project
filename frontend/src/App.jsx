import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip } from "react-leaflet";

const API_URL = import.meta.env.VITE_API_URL || "";
const BENGALURU_CENTER = [12.9716, 77.5946];
const ACCOUNTS_KEY = "citypulse-auth-accounts";
const SESSION_KEY = "citypulse-auth-session";

function buildRoadPath(start, end, steps = 18) {
  const points = [];
  for (let index = 0; index <= steps; index += 1) {
    const ratio = index / steps;
    const lat = start[0] + (end[0] - start[0]) * ratio;
    const lng = start[1] + (end[1] - start[1]) * ratio;
    points.push([lat, lng]);
  }
  return points;
}

function loadAccounts() {
  try {
    const raw = window.localStorage.getItem(ACCOUNTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function loadSession() {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

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
  const average = analytics.average_occupancy;
  if (peak >= 0.5 || average >= 0.3) return "Severe";
  if (peak >= 0.35) return "Heavy";
  if (peak >= 0.2) return "Moderate";
  return "Low";
}

function latestTrendValue(analytics, key, fallback = 0) {
  const trend = analytics?.trend;
  return trend?.length ? trend[trend.length - 1][key] : fallback;
}

function formatTimestamp(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function markerColor(status) {
  if (status === "Severe" || status === "Heavy") return "#ff525f";
  if (status === "Moderate") return "#ffbf4d";
  if (status === "Low") return "#35d399";
  return "#789095";
}

function buildTrafficSummary(camera, analytics, status) {
  if (!camera || !analytics) return "No precomputed traffic analytics are available for this camera.";
  const vehicleCount = Object.values(analytics.vehicle_counts || {}).reduce((sum, value) => sum + value, 0);
  const peak = formatPercent(analytics.peak_occupancy);
  const average = formatPercent(analytics.average_occupancy);
  return `${camera.location} is currently ${status.toLowerCase()}. ${vehicleCount} unique vehicles were detected; peak occupancy reached ${peak} and average occupancy was ${average}. This is based on a prerecorded local video, not live municipal CCTV.`;
}

function BangaloreTrafficMap() {
  return (
    <section className="traffic-map-preview" aria-label="Static Bengaluru traffic route preview">
      <div className="traffic-map-heading">
        <div>
          <p className="mini-tag">Bengaluru network snapshot</p>
          <h3>Live traffic across Bengaluru</h3>
        </div>
        <div className="traffic-map-legend">
          <span><i className="route-key green" /> Free flow</span>
          <span><i className="route-key yellow" /> Moderate</span>
          <span><i className="route-key red" /> Congested</span>
        </div>
      </div>
      <div className="traffic-map-canvas">
        <img src="/bengaluru-traffic-map.png" alt="Dark Bengaluru traffic map showing red, yellow, and green live routes" />
        <div className="map-live-badge"><span className="pulse" /> Live traffic</div>
      </div>
    </section>
  );
}

function App() {
  const [screen, setScreen] = useState("preview");
  const [authMode, setAuthMode] = useState("login");
  const [accounts, setAccounts] = useState(() => loadAccounts());
  const [currentUser, setCurrentUser] = useState(() => loadSession());
  const [authForm, setAuthForm] = useState({ name: "", email: "", password: "", confirmPassword: "" });
  const [authMessage, setAuthMessage] = useState("");

  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [loadingCameras, setLoadingCameras] = useState(true);
  const [error, setError] = useState("");
  const [fromCameraId, setFromCameraId] = useState("CAM-BLR-01");
  const [toCameraId, setToCameraId] = useState("CAM-BLR-04");
  const [travelTimeInput, setTravelTimeInput] = useState("18:45");
  const [routePrediction, setRoutePrediction] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState("");
  const [cameraSearch, setCameraSearch] = useState("");
  const [heatmapEnabled, setHeatmapEnabled] = useState(true);
  const [trafficPredictions, setTrafficPredictions] = useState(null);
  const [predictionError, setPredictionError] = useState("");
  const [systemHealth, setSystemHealth] = useState(null);

  useEffect(() => {
    window.localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
  }, [accounts]);

  useEffect(() => {
    if (currentUser) {
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(currentUser));
    } else {
      window.localStorage.removeItem(SESSION_KEY);
    }
  }, [currentUser]);

  useEffect(() => {
    if (screen !== "dashboard") return;
    fetchJson(`${API_URL}/api/cameras`)
      .then((items) => {
        setCameras(items);
        setSelectedCamera(items[0] || null);
        if (items.length) {
          setFromCameraId(items[0].id);
          setToCameraId(items[items.length - 1].id);
        }
      })
      .catch((reason) => setError(reason.message))
      .finally(() => setLoadingCameras(false));
  }, [screen]);

  useEffect(() => {
    if (screen !== "dashboard") return;
    fetchJson(`${API_URL}/api/health`).then(setSystemHealth).catch(() => setSystemHealth(null));
  }, [screen]);

  useEffect(() => {
    if (screen !== "dashboard" || !selectedCamera?.id || !selectedCamera.analytics) {
      setTrafficPredictions(null);
      return;
    }
    setPredictionError("");
    fetchJson(`${API_URL}/api/predict-traffic?camera_id=${encodeURIComponent(selectedCamera.id)}`)
      .then(setTrafficPredictions)
      .catch((reason) => {
        setTrafficPredictions(null);
        setPredictionError(reason.message);
      });
  }, [screen, selectedCamera?.id, selectedCamera?.analytics]);

  const selectCamera = (camera) => {
    setSelectedCamera(camera);
    setError("");
  };

  const handleRoutePrediction = async () => {
    setRouteLoading(true);
    setRouteError("");
    try {
      const prediction = await fetchJson(
        `${API_URL}/api/predict-route?from_camera=${encodeURIComponent(fromCameraId)}&to_camera=${encodeURIComponent(toCameraId)}&time=${encodeURIComponent(travelTimeInput)}`
      );
      setRoutePrediction(prediction);
    } catch (reason) {
      setRouteError(reason.message);
      setRoutePrediction(null);
    } finally {
      setRouteLoading(false);
    }
  };

  const exportReport = (format) => {
    if (!selectedCamera) return;
    const report = {
      exported_at: new Date().toISOString(),
      camera: selectedCamera,
      analytics: selectedCamera.analytics || null,
      alerts: selectedCamera.alerts || [],
      traffic_predictions: trafficPredictions?.predictions || [],
      note: "Local prerecorded demonstration data; not municipal live CCTV.",
    };
    const content = format === "csv"
      ? ["metric,value", `camera_id,${selectedCamera.id}`, `traffic_status,${selectedCamera.traffic_status || "Unavailable"}`, `vehicle_count,${selectedCamera.vehicle_count ?? "Unavailable"}`, `average_occupancy,${selectedCamera.analytics?.average_occupancy ?? "Unavailable"}`, `peak_occupancy,${selectedCamera.analytics?.peak_occupancy ?? "Unavailable"}`].join("\n")
      : JSON.stringify(report, null, 2);
    const blob = new Blob([content], { type: format === "csv" ? "text/csv" : "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `citypulse-${selectedCamera.id}.${format}`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const handleAuthChange = (event) => {
    const { name, value } = event.target;
    setAuthForm((previous) => ({ ...previous, [name]: value }));
  };

  const handleAuthSubmit = (event) => {
    event.preventDefault();
    setAuthMessage("");

    const email = authForm.email.trim().toLowerCase();
    const password = authForm.password.trim();

    if (!email || !password || (authMode === "signup" && !authForm.name.trim())) {
      setAuthMessage("Please fill in the required fields.");
      return;
    }

    if (authMode === "signup") {
      if (password.length < 6) {
        setAuthMessage("Password must be at least 6 characters long.");
        return;
      }
      if (authForm.confirmPassword !== password) {
        setAuthMessage("Passwords do not match.");
        return;
      }
      const duplicate = accounts.some((account) => account.email === email);
      if (duplicate) {
        setAuthMessage("An account with this email already exists.");
        return;
      }

      const newAccount = {
        id: Date.now().toString(),
        name: authForm.name.trim(),
        email,
        password,
      };
      setAccounts((previous) => [...previous, newAccount]);
      setCurrentUser({ name: newAccount.name, email: newAccount.email });
      setScreen("dashboard");
      setAuthForm({ name: "", email: "", password: "", confirmPassword: "" });
      return;
    }

    const account = accounts.find((item) => item.email === email && item.password === password);
    if (!account) {
      setAuthMessage("Invalid email or password. Try again.");
      return;
    }

    setCurrentUser({ name: account.name, email: account.email });
    setScreen("dashboard");
    setAuthForm({ name: "", email: "", password: "", confirmPassword: "" });
  };

  const logout = () => {
    setCurrentUser(null);
    setScreen("preview");
  };

  const analytics = selectedCamera?.analytics;
  const trackingReady = selectedCamera?.tracking_ready;
  const trafficStatus = selectedCamera?.traffic_status || statusFromAnalytics(analytics);
  const alerts = selectedCamera?.alerts || [];
  const filteredCameras = cameras.filter((camera) => `${camera.id} ${camera.name} ${camera.location}`.toLowerCase().includes(cameraSearch.toLowerCase()));
  const routeCoordinates = routePrediction
    ? routePrediction.route
        .map((cameraId) => {
          const camera = cameras.find((item) => item.id === cameraId);
          return camera ? [camera.latitude, camera.longitude] : null;
        })
        .filter(Boolean)
    : [];

  const routeMapSegments = routePrediction?.segment_congestion || [];
  const roadSegments = routeMapSegments
    .map((segment) => {
      const from = cameras.find((camera) => camera.id === segment.from);
      const to = cameras.find((camera) => camera.id === segment.to);
      if (!from || !to) return null;
      return {
        ...segment,
        path: buildRoadPath([from.latitude, from.longitude], [to.latitude, to.longitude], 20),
      };
    })
    .filter(Boolean);

  if (screen === "preview") {
    return (
      <div className="landing-page">
        <header className="landing-header">
          <div className="brand-lockup">
            <span className="brand-mark">CP</span>
            <div>
              <p className="eyebrow">CITYPULSE AI</p>
              <h1>Traffic intelligence</h1>
            </div>
          </div>
          <nav className="landing-nav">
            <a href="#features">Features</a>
            <a href="#demo">Demo</a>
            <button className="ghost-button" onClick={() => setScreen("auth")}>Login</button>
          </nav>
        </header>

        <main className="landing-main">
          <section className="hero-panel">
            <div className="hero-copy">
              <p className="mini-tag">Urban mobility analytics</p>
              <h2>See traffic before it slows the city down.</h2>
              <p className="hero-text">
                Monitor vehicle flow, predict congestion by time, and choose the smartest route across Bengaluru camera nodes.
              </p>
              <div className="hero-actions">
                <button className="primary-cta" onClick={() => setScreen("auth")}>Get started</button>
                <button className="secondary-cta" onClick={() => window.document.getElementById("demo")?.scrollIntoView({ behavior: "smooth" })}>Watch demo</button>
              </div>
              <div className="trust-row">
                <span>4 live camera feeds</span>
                <span>YOLO + ByteTrack</span>
                <span>Smart route prediction</span>
              </div>
            </div>
            <div className="hero-visual">
              <div className="signal-card big-card">
                <span className="signal-label">Live network</span>
                <div className="signal-grid">
                  <span className="signal-dot green" />
                  <span className="signal-dot yellow" />
                  <span className="signal-dot red" />
                  <span className="signal-dot green" />
                </div>
                <div className="signal-bars">
                  <span style={{ height: "25%" }} />
                  <span style={{ height: "60%" }} />
                  <span style={{ height: "75%" }} />
                  <span style={{ height: "45%" }} />
                  <span style={{ height: "90%" }} />
                  <span style={{ height: "55%" }} />
                </div>
              </div>
              <div className="signal-card small-card">
                <span className="signal-label">Best route</span>
                <strong>12 min</strong>
                <small>Moderate congestion</small>
              </div>
            </div>
          </section>

          <BangaloreTrafficMap />

          <section id="features" className="feature-grid">
            <FeatureCard
              color="teal"
              title="Camera intelligence"
              text="Track vehicle movement across four simulated city points and visualize what the road looks like in real time."
            />
            <FeatureCard
              color="amber"
              title="Forecasted congestion"
              text="Estimate traffic intensity by time of day and choose routes with less delay before you leave."
            />
            <FeatureCard
              color="rose"
              title="Smart route planning"
              text="Get a color-coded route prediction showing where roads are clear, moderate, or highly congested."
            />
          </section>

          <section id="demo" className="demo-panel">
            <div className="demo-copy">
              <p className="mini-tag">Demo preview</p>
              <h3>See how the platform works</h3>
              <p>
                A product walkthrough video will be added here soon. The area is prepared for the final demo clip and UI walkthrough.
              </p>
            </div>
            <div className="video-placeholder">
              <button className="play-button">▶</button>
              <span>Demo video coming soon</span>
            </div>
          </section>

          <section className="cta-panel">
            <div>
              <p className="mini-tag">Ready to explore?</p>
              <h3>Sign in to unlock the dashboard and route prediction tools.</h3>
            </div>
            <button className="primary-cta" onClick={() => setScreen("auth")}>Continue to login</button>
          </section>
        </main>
      </div>
    );
  }

  if (screen === "auth") {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-brand">
            <span className="brand-mark">CP</span>
            <div>
              <p className="eyebrow">CITYPULSE AI</p>
              <h2>{authMode === "login" ? "Welcome back" : "Create account"}</h2>
            </div>
          </div>

          <div className="auth-toggle">
            <button className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>Login</button>
            <button className={authMode === "signup" ? "active" : ""} onClick={() => setAuthMode("signup")}>Sign up</button>
          </div>

          <form className="auth-form" onSubmit={handleAuthSubmit}>
            {authMode === "signup" && (
              <label>
                <span>Full name</span>
                <input name="name" type="text" value={authForm.name} onChange={handleAuthChange} placeholder="Your name" />
              </label>
            )}

            <label>
              <span>Email</span>
              <input name="email" type="email" value={authForm.email} onChange={handleAuthChange} placeholder="you@example.com" />
            </label>

            <label>
              <span>Password</span>
              <input name="password" type="password" value={authForm.password} onChange={handleAuthChange} placeholder="••••••••" />
            </label>

            {authMode === "signup" && (
              <label>
                <span>Confirm password</span>
                <input name="confirmPassword" type="password" value={authForm.confirmPassword} onChange={handleAuthChange} placeholder="Repeat password" />
              </label>
            )}

            {authMessage && <div className="auth-message">{authMessage}</div>}

            <button type="submit" className="primary-cta auth-submit">
              {authMode === "login" ? "Login" : "Create account"}
            </button>
          </form>

          <button className="text-link" onClick={() => setScreen("preview")}>Back to preview</button>
        </div>
      </div>
    );
  }

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
        <div className="header-actions">
          <div className="mode-chip"><span className="pulse" /> Signed in as {currentUser?.name || "User"}</div>
          <button className="ghost-button" onClick={() => exportReport("json")} disabled={!selectedCamera}>Export</button>
          <button className="ghost-button" onClick={logout}>Logout</button>
        </div>
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
            <div className="map-controls"><label><input type="checkbox" checked={heatmapEnabled} onChange={(event) => setHeatmapEnabled(event.target.checked)} /> Heatmap</label><span className="map-hint">Click a node to inspect</span></div>
          </div>
          <div className="map-wrap">
            {loadingCameras ? <div className="map-state">Loading camera network...</div> : (
              <MapContainer center={BENGALURU_CENTER} zoom={11} scrollWheelZoom className="map">
                <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {routeCoordinates.length > 1 && (
                  <Polyline
                    positions={routeCoordinates}
                    pathOptions={{ color: "#ffcc66", weight: 4, opacity: 0.9, dashArray: "10 12" }}
                  />
                )}
                {heatmapEnabled && cameras.filter((camera) => camera.analytics).map((camera) => (
                  <CircleMarker
                    key={`heat-${camera.id}`}
                    center={[camera.latitude, camera.longitude]}
                    radius={18 + Math.round((camera.analytics?.peak_occupancy || 0) * 34)}
                    pathOptions={{ color: markerColor(camera.traffic_status), fillColor: markerColor(camera.traffic_status), fillOpacity: 0.14, weight: 1, opacity: 0.35 }}
                  />
                ))}
                {cameras.map((camera) => (
                  <CircleMarker
                    key={camera.id}
                    center={[camera.latitude, camera.longitude]}
                    radius={selectedCamera?.id === camera.id ? 12 : 8}
                    pathOptions={{ color: selectedCamera?.id === camera.id ? "#f8fafc" : markerColor(camera.traffic_status), fillColor: markerColor(camera.traffic_status), fillOpacity: 0.95, weight: selectedCamera?.id === camera.id ? 4 : 3 }}
                    eventHandlers={{ click: () => selectCamera(camera) }}
                  >
                    <Tooltip>{camera.id} · {camera.location}</Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>
            )}
          </div>
          <div className="camera-list-tools"><input type="search" value={cameraSearch} onChange={(event) => setCameraSearch(event.target.value)} placeholder="Search cameras or locations" /><span>{filteredCameras.length} of {cameras.length}</span></div>
          <div className="camera-list" aria-label="Camera list">
            {filteredCameras.map((camera) => (
              <button
                key={camera.id}
                className={`camera-list-item ${selectedCamera?.id === camera.id ? "selected" : ""}`}
                onClick={() => selectCamera(camera)}
              >
                <span className={`camera-status-dot ${String(camera.traffic_status || "unavailable").toLowerCase()}`} />
                <span><strong>{camera.id}</strong><small>{camera.location}</small></span>
                <em>{camera.traffic_status || "Unavailable"}</em>
              </button>
            ))}
          </div>
          <div className="map-footer"><span><i className="legend-dot" /> Prerecorded simulation</span><span>OpenStreetMap base layer</span></div>
        </div>

        <aside className="camera-panel panel">
          <div className="panel-heading"><div><span className="section-kicker">02 / SELECTED FEED</span><h3>{selectedCamera?.id || "No camera selected"}</h3></div><span className={`status-label ${trafficStatus.toLowerCase().replace(" ", "-")}`}>{trafficStatus}</span></div>
          {selectedCamera ? <>
            <div className="camera-meta"><span>{selectedCamera.location}</span><span>{selectedCamera.metadata}</span><span>{selectedCamera.status || "Status unavailable"} · {selectedCamera.camera_health || "Health unavailable"}</span><span>Updated {formatTimestamp(selectedCamera.last_updated)}</span><span>{selectedCamera.fps ? `${selectedCamera.fps.toFixed(1)} FPS` : "FPS unavailable"}</span><span>{selectedCamera.detection_confidence ? `Confidence ${(selectedCamera.detection_confidence * 100).toFixed(0)}%` : "Confidence unavailable"}</span></div>
            <div className="video-stack">
              <div className="video-frame">
                {trackingReady ? <video key={selectedCamera.tracked_video_url} src={`${API_URL}${selectedCamera.tracked_video_url}`} controls autoPlay muted loop playsInline /> : <div className="video-state">Tracking has not been precomputed for this camera.</div>}
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
        <div className="panel-heading"><div><span className="section-kicker">03 / PIPELINE OUTPUT</span><h3>Traffic intelligence</h3></div><div className="panel-actions"><span className="availability">{analytics ? "Precomputed pipeline response" : "Tracking not precomputed"}</span><button className="ghost-button compact" onClick={() => exportReport("csv")} disabled={!analytics}>CSV</button></div></div>
        {!analytics ? <div className="empty-analytics">Run the precompute command once to generate the tracking video and analytics for this camera.</div> : <div className="analytics-grid">
          <Metric label="Unique vehicles" value={Object.values(analytics.vehicle_counts).reduce((sum, value) => sum + value, 0)} />
          <Metric label="Vehicles in latest frame" value={latestTrendValue(analytics, "vehicles")} />
          <Metric label="Peak vehicles in frame" value={analytics.peak_vehicles_in_frame ?? "Unavailable"} />
          <Metric label="Vehicles per minute" value={analytics.vehicles_per_minute ? analytics.vehicles_per_minute.toFixed(1) : "Unavailable"} />
          <Metric label="Average occupancy" value={formatPercent(analytics.average_occupancy)} />
          <Metric label="Peak occupancy" value={formatPercent(analytics.peak_occupancy)} />
          <Metric label="Congestion" value={trafficStatus} />
          <div className="breakdown metric"><span className="metric-label">Vehicle mix</span>{Object.entries(analytics.vehicle_counts).map(([name, count]) => <span className="mix-row" key={name}><span>{name}</span><strong>{count}</strong></span>)}</div>
        </div>}
      </section>

      <section className="insights-grid">
        <TrendPanel analytics={analytics} />
        <section className="insight-panel">
          <div className="insight-heading"><span className="section-kicker">06 / ANPR</span><h3>Plate recognition</h3></div>
          <div className="insight-empty"><strong>No plate results attached</strong><span>The current ANPR tool processes a separate still image through the CLI. No plate numbers are inferred from this camera feed.</span></div>
        </section>
        <AlertPanel alerts={alerts} selectedCamera={selectedCamera} />
        <section className="insight-panel">
          <div className="insight-heading"><span className="section-kicker">08 / ESTIMATION</span><h3>Speed and direction</h3></div>
          <div className="unavailable-detail"><strong>Unavailable</strong><span>Speed and direction require camera calibration or a defined road direction. The current tracker does not provide either reliably.</span></div>
        </section>
      </section>

      <section className="operations-grid">
        <section className="insight-panel prediction-panel">
          <div className="insight-heading"><span className="section-kicker">09 / PREDICTION</span><h3>Estimated traffic outlook</h3></div>
          {!trafficPredictions ? <div className="insight-empty"><strong>{predictionError || "Prediction unavailable"}</strong><span>Predictions require precomputed camera analytics.</span></div> : <><div className="prediction-cards">{trafficPredictions.predictions.map((prediction) => <div className="prediction-card" key={prediction.horizon_minutes}><span>+{prediction.horizon_minutes} min</span><strong>{prediction.traffic_level}</strong><small>{prediction.predicted_vehicle_count} vehicles · {prediction.confidence} confidence</small><em>{prediction.trend}</em></div>)}</div><p className="chart-note">Estimated baseline prediction, not a trained historical model.</p></>}
        </section>
        <section className="insight-panel summary-panel">
          <div className="insight-heading"><span className="section-kicker">10 / AI SUMMARY</span><h3>Traffic intelligence brief</h3></div>
          <p className="summary-text">{buildTrafficSummary(selectedCamera, analytics, trafficStatus)}</p>
          <div className="system-health"><span className={`health-indicator ${systemHealth?.status === "ok" ? "online" : "offline"}`} /> <strong>System status</strong><span>{systemHealth ? `${systemHealth.camera_sources} sources · ${systemHealth.precomputed_cameras} precomputed` : "Backend health unavailable"}</span></div>
        </section>
      </section>

      <section className="route-panel panel">
        <div className="panel-heading">
          <div><span className="section-kicker">04 / CONGESTION PREDICTOR</span><h3>Plan a route by time</h3></div>
        </div>
        <div className="route-form">
          <label>
            <span>From</span>
            <select value={fromCameraId} onChange={(event) => setFromCameraId(event.target.value)}>
              {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
            </select>
          </label>
          <label>
            <span>To</span>
            <select value={toCameraId} onChange={(event) => setToCameraId(event.target.value)}>
              {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
            </select>
          </label>
          <label>
            <span>Time</span>
            <input type="time" value={travelTimeInput} onChange={(event) => setTravelTimeInput(event.target.value)} />
          </label>
          <button className="primary-button route-button" onClick={handleRoutePrediction} disabled={routeLoading || !cameras.length}>
            {routeLoading ? "Predicting..." : "Predict route"}
          </button>
        </div>

        {routeError && <div className="error-banner">{routeError}</div>}

        {routePrediction && (
          <>
            <div className="route-result">
              <div className="result-metric">
                <span className="metric-label">Route</span>
                <strong>{routePrediction.route_names.join(" → ")}</strong>
              </div>
              <div className="result-metric">
                <span className="metric-label">Estimated congestion</span>
                <strong>{(routePrediction.average_congestion * 100).toFixed(1)}%</strong>
              </div>
              <div className="result-metric">
                <span className="metric-label">Travel time</span>
                <strong>{routePrediction.estimated_travel_minutes} min</strong>
              </div>
              <div className="result-reason">
                <span className="metric-label">Best route note</span>
                <p>{routePrediction.best_route_reason}</p>
              </div>
            </div>

            <div className="predictor-map-panel">
              <div className="predictor-map-header">
                <span className="section-kicker">TRAFFIC MAP</span>
                <div className="legend-row">
                  <span className="legend-chip green"><i /> Free flow</span>
                  <span className="legend-chip orange"><i /> Moderate</span>
                  <span className="legend-chip red"><i /> Peak</span>
                </div>
              </div>
              <MapContainer center={routeCoordinates.length ? routeCoordinates[0] : BENGALURU_CENTER} zoom={12} scrollWheelZoom className="predictor-map">
                <TileLayer
                  attribution='&copy; OpenStreetMap contributors &copy; CARTO'
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                />
                {roadSegments.map((segment) => (
                  <Polyline
                    key={`${segment.from}-${segment.to}`}
                    positions={[...segment.path]}
                    pathOptions={{ color: "#0b1320", weight: 12, opacity: 1 }}
                  />
                ))}
                {roadSegments.map((segment) => (
                  <Polyline
                    key={`${segment.from}-${segment.to}-color`}
                    positions={[...segment.path]}
                    pathOptions={{ color: segment.color, weight: 7, opacity: 0.95 }}
                  />
                ))}
                {routeCoordinates.map((position, index) => (
                  <CircleMarker
                    key={`route-point-${routePrediction.route[index]}`}
                    center={position}
                    radius={8}
                    pathOptions={{ color: "#f8fafc", fillColor: "#ffcc66", fillOpacity: 1, weight: 2 }}
                  />
                ))}
              </MapContainer>
            </div>
          </>
        )}
      </section>
      <footer>CityPulse AI · prerecorded demonstration · not connected to municipal CCTV</footer>
    </main>
  );
}

function Metric({ label, value }) {
  return <div className="metric"><span className="metric-label">{label}</span><strong>{value}</strong></div>;
}

function TrendPanel({ analytics }) {
  const trend = analytics?.trend || [];
  const maxVehicles = Math.max(...trend.map((point) => point.vehicles), 1);
  return (
    <section className="insight-panel trend-panel">
      <div className="insight-heading"><span className="section-kicker">05 / TRAFFIC TREND</span><h3>Vehicles through the video</h3></div>
      {!trend.length ? <div className="insight-empty"><strong>No trend samples available</strong><span>Run analysis to generate sampled frame counts.</span></div> : <div className="trend-chart" aria-label="Vehicle count trend chart">
        {trend.map((point) => <div className="trend-column" key={point.frame} title={`Frame ${point.frame}: ${point.vehicles} vehicles`}><span style={{ height: `${Math.max(8, (point.vehicles / maxVehicles) * 100)}%` }} /><small>{point.vehicles}</small></div>)}
      </div>}
      <div className="chart-note">Sampled every 30 frames · occupancy is ROI-based</div>
    </section>
  );
}

function AlertPanel({ alerts, selectedCamera }) {
  return (
    <section className="insight-panel alert-panel">
      <div className="insight-heading"><span className="section-kicker">07 / ALERTS</span><h3>Detected incidents</h3></div>
      {!alerts.length ? <div className="insight-empty"><strong>No alerts detected</strong><span>Alerts appear when tracked occupancy or frame-level vehicle buildup crosses the configured thresholds.</span></div> : <div className="alert-list">
        {alerts.map((alert) => <article className={`alert-item ${alert.severity}`} key={`${alert.type}-${alert.timestamp}`}><div><strong>{alert.type.replace("_", " ")}</strong><small>{formatTimestamp(alert.timestamp)}</small></div><p>{alert.reason}</p><span>{selectedCamera?.id} · {alert.source}</span></article>)}
      </div>}
    </section>
  );
}

function FeatureCard({ color, title, text }) {
  return (
    <article className={`feature-card ${color}`}>
      <div className="feature-icon" />
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}

export default App;
