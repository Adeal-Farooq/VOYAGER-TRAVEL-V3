import { useEffect } from "react";
import { useApp, type Mode } from "../context/AppContext";
import HeaderBar from "../components/HeaderBar";
import MapView from "../components/MapView";
import SearchPanel from "../components/SearchPanel";
import AToBPanel from "../components/AToBPanel";
import TripPanel from "../components/TripPanel";
import DiscoveryPanel from "../components/DiscoveryPanel";
import NewsPopup from "../components/NewsPopup";
import type { LatLng } from "../types";
import "./MainPage.css";

const TABS: { key: Mode; label: string; icon: string }[] = [
  { key: "search", label: "Search", icon: "search" },
  { key: "atob", label: "A→B", icon: "directions" },
  { key: "trip", label: "Trip", icon: "luggage" },
];

export default function MainPage() {
  const { mode, setMode, setUserLoc } = useApp();

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setUserLoc({ lat: 12.9716, lng: 77.5946, name: "Bengaluru" }),
      { timeout: 6000 },
    );
  }, [setUserLoc]);

  return (
    <div className="app-shell">
      <HeaderBar />
      <div className="app-body">
        <aside className={`sidebar glass ${mode === "search" ? "visible" : ""}`}>
          {mode === "search" && <SearchPanel />}
          {mode === "atob" && <AToBPanel />}
          {mode === "trip" && <TripPanel />}
        </aside>

        <main className="map-wrap">
          <MapView />
          <NewsPopup />
        </main>

        <DiscoveryPanel />
      </div>

      <nav className="bottom-nav glass-strong">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${mode === t.key ? "active" : ""}`}
            onClick={() => setMode(t.key)}
          >
            <span className="material-symbols-outlined">{t.icon}</span>
            <span className="tab-label">{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

// helper to fly somewhere from anywhere
export function flyToPoint(map: unknown, point: LatLng, zoom = 15) {
  const anyMap = map as { flyTo?: (c: LatLng, z: number) => void };
  anyMap?.flyTo?.({ lat: point.lat, lng: point.lng }, zoom);
}
