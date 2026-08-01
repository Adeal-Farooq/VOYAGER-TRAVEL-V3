import { useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import "./TripPanel.css";

export default function TripPanel() {
  const { journey, setJourney, setMode } = useApp();
  const [watchId, setWatchId] = useState<number | null>(null);

  const startJourney = () => {
    setJourney({ active: true });
    if (!navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition(
      (pos) => setJourney({ position: { lat: pos.coords.latitude, lng: pos.coords.longitude } }),
      () => {},
      { enableHighAccuracy: true, timeout: 10000 },
    );
    setWatchId(id);
  };

  const endJourney = () => {
    if (watchId != null) navigator.geolocation.clearWatch(watchId);
    setWatchId(null);
    setJourney({ active: false, position: null });
  };

  useEffect(() => () => {
    if (watchId != null) navigator.geolocation.clearWatch(watchId);
  }, [watchId]);

  return (
    <div className="trip-panel">
      <div className="ai-insight glass">
        <div className="spread">
          <span className="row"><span className="material-symbols-outlined">auto_awesome</span><b>AI Travel Insights</b></span>
          <span className="badge live">LIVE</span>
        </div>
        <p className="small mt8">
          Plan smarter with live weather, traffic and crowd data feeding every route recommendation.
        </p>
      </div>

      {journey.active ? (
        <div className="active-journey glass-strong anim-in">
          <div className="spread">
            <span className="row"><span className="pulse-dot" /> <b>Journey in progress</b></span>
            <button className="btn small" onClick={endJourney}>End</button>
          </div>
          {journey.position ? (
            <div className="muted small mt8">
              {journey.position.lat.toFixed(5)}, {journey.position.lng.toFixed(5)}
            </div>
          ) : (
            <div className="muted small mt8">Waiting for GPS…</div>
          )}
        </div>
      ) : (
        <button className="btn full mt12" onClick={startJourney}>
          <span className="material-symbols-outlined">navigation</span> Start journey
        </button>
      )}

      <button className="btn full mt12" onClick={() => setMode("atob")}>
        <span className="material-symbols-outlined">add_location_alt</span> Create new trip
      </button>

      <div className="section-head mt12">Your Trips</div>
      <div className="empty glass">
        <span className="material-symbols-outlined">luggage</span>
        <div className="muted small">No saved trips yet. Plan your first A→B route.</div>
      </div>

      <div className="section-head mt12">Day Plan</div>
      <div className="day-tabs row">
        <button className="chip active">Day 1</button>
        <button className="chip">Day 2</button>
        <button className="chip">Day 3</button>
      </div>
    </div>
  );
}
