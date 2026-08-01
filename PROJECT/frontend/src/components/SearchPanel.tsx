import { useCallback, useEffect, useRef, useState } from "react";
import { useApp, scoreClass } from "../context/AppContext";
import { api } from "../services/api";
import type { PlaceResult } from "../types";
import "./SearchPanel.css";

const NEARBY_CATEGORIES = [
  "ATM", "Bank", "Hospital", "Pharmacy", "Restaurant", "Cafe", "Hotel", "Mall",
  "Petrol Pump", "EV Station", "Supermarket", "Park", "Bus Stop", "Metro",
  "Temple", "Police", "School", "Gym", "Cinema",
];

function PlaceCard({ place, index, onPick, onDetails, onNavigate }: {
  place: PlaceResult; index: number;
  onPick: (p: PlaceResult) => void;
  onDetails: (p: PlaceResult) => void;
  onNavigate: (p: PlaceResult) => void;
}) {
  const cls = place.business_status === "CLOSED_PERMANENTLY" ? "red" : scoreClass(place.rating ? place.rating * 20 : null);
  return (
    <div className="place-card glass hover-lift anim-up" style={{ borderLeftColor: `var(--score-${cls})` }} onClick={() => onPick(place)}>
      <div className="spread">
        <div className="row">
          <span className="marker-num" style={{ background: `var(--primary)` }}>{index + 1}</span>
          <div>
            <div className="place-name">{place.name}</div>
            <div className="muted small">{place.primary_type ?? place.types?.[0] ?? ""}</div>
          </div>
        </div>
        <span className={`score-pill ${cls}`}>
          {place.business_status === "OPERATIONAL" ? "open" : place.business_status ?? "unknown"}
        </span>
      </div>
      <div className="muted small truncate mt8">{place.address}</div>
      <div className="spread mt8">
        <span className="row">
          {place.rating != null && <span>★ {place.rating}</span>}
          {place.user_rating_count != null && <span className="muted">({place.user_rating_count})</span>}
          {place.distance_km != null && <span className="muted">{place.distance_km.toFixed(1)} km</span>}
        </span>
        {place.open_now != null && (
          <span className={place.open_now ? "badge live" : "badge est"}>{place.open_now ? "Open now" : "Closed"}</span>
        )}
      </div>
      <div className="row mt12">
        <button className="btn small" onClick={(e) => { e.stopPropagation(); onDetails(place); }}>Details</button>
        <button className="btn ghost small" onClick={(e) => { e.stopPropagation(); onNavigate(place); }}>Navigate</button>
      </div>
    </div>
  );
}

export default function SearchPanel() {
  const { setPlaces, setSelected, setShowDiscovery, setDest, setMode, setFlyTo, userLoc } = useApp();
  const [tab, setTab] = useState<"specific" | "nearby">("specific");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PlaceResult[]>([]);
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [radiusKm, setRadiusKm] = useState(2);
  const [category, setCategory] = useState("Restaurant");
  const [pinned, setPinned] = useState<PlaceResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.trim().length < 2) { setSuggestions([]); return; }
    abortRef.current?.abort();
    const c = new AbortController();
    abortRef.current = c;
    try {
      const r = await api.searchPlaces(q, userLoc?.lat, userLoc?.lng, c.signal);
      setSuggestions(r.slice(0, 5));
    } catch { /* aborted */ }
  }, [userLoc]);

  useEffect(() => {
    const id = setTimeout(() => fetchSuggestions(query), 300);
    return () => clearTimeout(id);
  }, [query, fetchSuggestions]);

  const runSearch = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const r = await api.searchPlaces(q, userLoc?.lat, userLoc?.lng);
      setResults(r);
      setPlaces(r);
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  };

  const runNearby = async () => {
    const base = pinned ?? (userLoc ? { lat: userLoc.lat, lng: userLoc.lng } : { lat: 12.9716, lng: 77.5946 });
    setLoading(true);
    try {
      const r = await api.searchNearby(base.lat, base.lng, radiusKm * 1000, [category]);
      setResults(r);
      setPlaces(r);
    } finally {
      setLoading(false);
    }
  };

  const pickPlace = (p: PlaceResult) => {
    setPlaces([p]);
    setPinned(p);
    setFlyTo({ lat: p.lat, lng: p.lng });
  };

  const openDetails = async (p: PlaceResult) => {
    setSelected(null);
    setShowDiscovery(true);
    try {
      const d = await api.enrichPlace(p);
      setSelected(d);
    } catch {
      setSelected({ ...p, reviews: [] });
    }
  };

  const navigate = (p: PlaceResult) => {
    setDest({ lat: p.lat, lng: p.lng, name: p.name });
    setMode("atob");
  };

  return (
    <div className="search-panel">
      <div className="tabs row">
        <button className={`chip ${tab === "specific" ? "active" : ""}`} onClick={() => setTab("specific")}>Search</button>
        <button className={`chip ${tab === "nearby" ? "active" : ""}`} onClick={() => setTab("nearby")}>Nearby</button>
      </div>

      {tab === "specific" ? (
        <div className="specific">
          <div className="search-box">
            <input
              className="text-input"
              placeholder="Search place or location…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") runSearch(query); }}
            />
            <button className="btn" onClick={() => runSearch(query)}>
              <span className="material-symbols-outlined">search</span>
            </button>
          </div>
          {suggestions.length > 0 && (
            <div className="suggest glass-strong">
              {suggestions.map((s) => (
                <button key={s.place_id} className="suggest-item" onClick={() => { setQuery(s.name); runSearch(s.name); }}>
                  <span className="material-symbols-outlined">location_on</span>
                  <span>
                    <b>{s.name}</b>
                    <div className="muted small">{s.address}</div>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="nearby">
          {pinned && (
            <div className="pinned-banner glass anim-in">
              <span className="row">
                <span className="material-symbols-outlined">push_pin</span>
                <span className="truncate">Near {pinned.name}</span>
              </span>
              <button className="btn ghost small" onClick={() => setPinned(null)}>Clear</button>
            </div>
          )}
          <div className="chips">
            {NEARBY_CATEGORIES.map((c) => (
              <button key={c} className={`chip ${category === c ? "active" : ""}`} onClick={() => setCategory(c)}>{c}</button>
            ))}
          </div>
          <div className="radius row">
            <span className="muted small">Radius</span>
            <input type="range" min={0.5} max={10} step={0.5} value={radiusKm} onChange={(e) => setRadiusKm(Number(e.target.value))} />
            <span className="small">{radiusKm} km</span>
          </div>
          <button className="btn full mt8" onClick={runNearby}>
            {loading ? <span className="spinner inline" /> : <span className="material-symbols-outlined">near_me</span>} Find nearby
          </button>
        </div>
      )}

      {loading && <div className="skeleton-list">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton card-skel" />)}</div>}

      {!loading && results.length > 0 && (
        <div className="results">
          {results.map((p, i) => (
            <PlaceCard key={p.place_id || i} place={p} index={i} onPick={pickPlace} onDetails={openDetails} onNavigate={navigate} />
          ))}
        </div>
      )}
    </div>
  );
}
