import { useEffect, useMemo, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useApp, scoreClass } from "../context/AppContext";
import type { Coord, HopOption, LatLng } from "../types";

const NUM_COLORS = [
  "#6c5ce7", "#00cec9", "#fd79a8", "#f39c12", "#27ae60",
  "#0984e3", "#e17055", "#a29bfe", "#00b894", "#d63031",
];

function userIcon() {
  return L.divIcon({ className: "", html: `<div class="marker-user"></div>`, iconSize: [14, 14] });
}
function pinIcon(cls: string) {
  return L.divIcon({ className: "", html: `<div class="marker-pin ${cls}"><span>${cls[0].toUpperCase()}</span></div>`, iconSize: [30, 30] });
}
function numIcon(n: number) {
  const c = NUM_COLORS[n % NUM_COLORS.length];
  return L.divIcon({ className: "", html: `<div class="marker-num" style="background:${c}">${n + 1}</div>`, iconSize: [26, 26] });
}
function starIcon() {
  return L.divIcon({ className: "", html: `<div class="marker-star">★</div>`, iconSize: [40, 40] });
}
function newsIcon(cat: string) {
  const color = { traffic: "#e74c3c", weather: "#3498db", event: "#f1c40f", general: "#95a5a6" }[cat] ?? "#95a5a6";
  return L.divIcon({ className: "", html: `<div class="marker-num" style="background:${color}">!</div>`, iconSize: [22, 22] });
}

function FlyController({ target }: { target: LatLng | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) {
      map.flyTo([target.lat, target.lng], Math.max(map.getZoom(), 14), { duration: 0.9 });
    }
  }, [target, map]);
  return null;
}

const MODE_COLOR: Record<string, string> = {
  bus: "#6c5ce7", metro: "#00cec9", train: "#e17055", walk: "#95a5a6",
  ride: "#f39c12", connecting: "#f39c12", dropoff: "#fd79a8",
};

function legGeometry(opt: HopOption): Coord[] {
  const g = opt.geometry;
  if (!g) return [];
  return g.map((pt: number[]) => [pt[1], pt[0]]) as Coord[];
}

function RoutePolylines() {
  const { journey, source, dest } = useApp();
  const segs = journey.segments?.segments ?? [];
  const lines: { pts: Coord[]; mode: string; approx: boolean }[] = [];

  for (const seg of segs) {
    for (const opt of seg.options ?? []) {
      const pts = legGeometry(opt);
      if (pts.length < 2) continue;
      const mode = opt.mode ?? "connecting";
      const approx = opt.geometrySource === "interpolated" || opt.status === "estimated";
      lines.push({ pts, mode, approx });
    }
  }

  return (
    <>
      {lines.map((ln, i) => (
        <Polyline
          key={i}
          positions={ln.pts}
          color={MODE_COLOR[ln.mode] ?? "#6c5ce7"}
          weight={ln.mode === "walk" ? 3 : 5}
          dashArray={ln.approx || ln.mode === "walk" ? "6 6" : undefined}
          opacity={0.85}
        />
      ))}
      {source && dest && (
        <Polyline
          positions={[[source.lat, source.lng], [dest.lat, dest.lng]]}
          color={MODE_COLOR.connecting}
          weight={2}
          dashArray="4 8"
          opacity={0.5}
        />
      )}
    </>
  );
}

function Pins() {
  const { places, selected, userLoc, source, dest, journey, news } = useApp();
  const numbered = journey.active ? [] : places; // numbered pins hidden during journey

  return (
    <>
      {userLoc && <Marker position={[userLoc.lat, userLoc.lng]} icon={userIcon()} />}
      {source && (
        <Marker position={[source.lat, source.lng]} icon={pinIcon("green")}>
          <Popup>Source: {source.name}</Popup>
        </Marker>
      )}
      {dest && (
        <Marker position={[dest.lat, dest.lng]} icon={pinIcon("red")}>
          <Popup>Destination: {dest.name}</Popup>
        </Marker>
      )}
      {selected && (
        <Marker position={[selected.lat, selected.lng]} icon={starIcon()}>
          <Popup>{selected.name}</Popup>
        </Marker>
      )}
      {numbered.map((p, i) => {
        const cls = p.business_status === "CLOSED_PERMANENTLY" ? "red" : scoreClass(p.rating ? p.rating * 20 : null);
        return (
          <Marker key={p.place_id || i} position={[p.lat, p.lng]} icon={numIcon(i)}>
            <Popup>
              <b>{p.name}</b>
              <div className="muted">{p.address}</div>
              {p.rating != null && <div>★ {p.rating} ({p.user_rating_count ?? 0})</div>}
              <div>
                <span className={`score-pill ${cls}`}>
                  {p.business_status ?? "OPERATIONAL"}
                </span>
              </div>
            </Popup>
          </Marker>
        );
      })}
      {news.map((n, i) =>
        n.geo ? (
          <Marker key={i} position={[n.geo.lat, n.geo.lng]} icon={newsIcon(n.category ?? "general")}>
            <Popup>
              <b>{n.title}</b>
              {n.summary && <div className="muted">{n.summary}</div>}
            </Popup>
          </Marker>
        ) : null,
      )}
    </>
  );
}

function JourneyPosition() {
  const { journey } = useApp();
  if (!journey.active || !journey.position) return null;
  return (
    <CircleMarker center={[journey.position.lat, journey.position.lng]} radius={7} pathOptions={{ color: "#2196f3", fillColor: "#2196f3", fillOpacity: 1 }} />
  );
}

export default function MapView() {
  const { flyTo, userLoc, journey } = useApp();
  const center: [number, number] = useMemo(() => {
    if (userLoc) return [userLoc.lat, userLoc.lng];
    return [12.9716, 77.5946];
  }, [userLoc]);

  const mapRef = useRef<L.Map | null>(null);
  useEffect(() => {
    if (mapRef.current && journey.segments) {
      const pts: [number, number][] = [];
      for (const seg of journey.segments.segments ?? []) {
        for (const opt of seg.options ?? []) {
          for (const pt of legGeometry(opt)) pts.push(pt as [number, number]);
        }
      }
      if (pts.length) mapRef.current.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
    }
  }, [journey.segments]);

  return (
    <MapContainer
      center={center}
      zoom={13}
      className="full-map"
      ref={(m) => { mapRef.current = m ?? null; }}
      zoomControl={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FlyController target={flyTo} />
      <Pins />
      <RoutePolylines />
      <JourneyPosition />
    </MapContainer>
  );
}
