import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { PlaceResult, MapRouteGeometry, NewsItem } from '../types'

interface MapViewProps {
  center: [number, number]
  onCenterChange?: (center: [number, number]) => void
  selectedPlace: PlaceResult | null
  userLocation: [number, number] | null
  sourceLocation: [number, number] | null
  destLocation: [number, number] | null
  mapRef?: React.MutableRefObject<any>
  allMarkers: PlaceResult[]
  onMarkerClick?: (place: PlaceResult) => void
  routeGeometry?: MapRouteGeometry[]
  onMapClick?: (latlng: [number, number]) => void
  newsItems?: NewsItem[]
  waypoints?: { lat: number; lng: number; query: string }[]
  liveTrackingPos?: [number, number] | null
  trackingActive?: boolean
}

function createColoredPin(color: string, emoji: string, size: number = 28, glow: boolean = false) {
  const glowStyle = glow ? `filter: drop-shadow(0 0 8px ${color}) brightness(1.3);` : ''
  return L.divIcon({
    className: '',
    html: `<div style="font-size:${size}px;${glowStyle}">${emoji}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  })
}

function MapController({ center, mapRef, onMapClick }: {
  center: [number, number]
  mapRef?: React.MutableRefObject<any>
  onMapClick?: (latlng: [number, number]) => void
}) {
  const map = useMap()
  useEffect(() => {
    if (mapRef) mapRef.current = map
  }, [map, mapRef])

  useEffect(() => {
    if (!onMapClick) return
    const handler = (e: L.LeafletMouseEvent) => onMapClick([e.latlng.lat, e.latlng.lng])
    map.on('click', handler)
    return () => { map.off('click', handler) }
  }, [map, onMapClick])

  return null
}

interface TrafficRoad {
  geometry: { type: string; coordinates: [number, number][] }
  properties: { highway: string; color: string; name: string }
}
function TrafficLayer() {
  const map = useMap()
  const [roads, setRoads] = useState<TrafficRoad[]>([])
  const [congestion, setCongestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [enabled, setEnabled] = useState(false)
  const moveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchTraffic = useCallback(async () => {
    const b = map.getBounds()
    try {
      setLoading(true)
      const resp = await fetch(`/api/routes/traffic-overlay?north=${b.getNorth()}&south=${b.getSouth()}&east=${b.getEast()}&west=${b.getWest()}`)
      const data = await resp.json()
      if (data.features) setRoads(data.features)
      if (data.congestion) setCongestion(data.congestion)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [map])

  useEffect(() => {
    if (!enabled) { setRoads([]); return }
    fetchTraffic()
    const handler = () => {
      if (moveTimer.current) clearTimeout(moveTimer.current)
      moveTimer.current = setTimeout(fetchTraffic, 800)
    }
    map.on('moveend', handler)
    return () => { map.off('moveend', handler); if (moveTimer.current) clearTimeout(moveTimer.current) }
  }, [enabled, map, fetchTraffic])

  return (
    <>
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <button onClick={() => setEnabled(!enabled)}
          style={{
            padding: '6px 12px', fontSize: 12, cursor: 'pointer', borderRadius: 6,
            background: enabled ? '#1e3a5f' : '#1e293b', color: enabled ? '#60a5fa' : '#94a3b8',
            border: enabled ? '1px solid #3b82f6' : '1px solid #475569',
            transition: 'all 0.2s',
          }}>
          🚦 Traffic {enabled ? 'ON' : 'OFF'} {loading ? '...' : congestion ? `(${congestion})` : ''}
        </button>
      </div>
      {enabled && roads.map((road, i) => (
        <Polyline
          key={`tr-${i}`}
          positions={road.geometry.coordinates.map(c => [c[1], c[0]] as [number, number])}
          pathOptions={{
            color: road.properties.color,
            weight: road.properties.highway === 'motorway' || road.properties.highway === 'trunk' ? 4 : road.properties.highway === 'primary' || road.properties.highway === 'secondary' ? 3 : 2,
            opacity: road.properties.highway === 'motorway' || road.properties.highway === 'trunk' ? 0.8 : 0.5,
          }}
        />
      ))}
    </>
  )
}

function getPlaceEmoji(placeType: string): string {
  const emojis: Record<string, string> = {
    mall: '🛍️', hospital: '🏥', airport: '✈️', railway_station: '🚉',
    bus_stand: '🚏', park: '🌳', it_hub: '🏢', metro_station: '🚇',
    bus_stop: '🚏', atm: '🏧', bank: '🏦', restaurant: '🍽️',
    hotel: '🏨', lodge: '🏨', temple: '🛕', mosque: '🕌', church: '⛪',
    school: '📚', petrol_pump: '⛽', charging_station: '🔋',
    police_station: '🚔', cafe: '☕', clinic: '🏥', pharmacy: '💊',
    supermarket: '🛒', gym: '🏋️', library: '📖', cinema: '🎬',
    post_office: '📮', place: '📍',
  }
  return emojis[placeType] || '📍'
}

export default function MapView({
  center, selectedPlace, userLocation, sourceLocation,
  destLocation, mapRef, allMarkers, onMarkerClick,
  routeGeometry, onMapClick, newsItems, waypoints,
  liveTrackingPos, trackingActive,
}: MapViewProps) {
  const userIcon = useMemo(() => createColoredPin('#3b82f6', '📍', 32, true), [])
  const sourceIcon = useMemo(() => createColoredPin('#3b82f6', '🟢', 24), [])
  const destIcon = useMemo(() => createColoredPin('#ef4444', '🔴', 24), [])

  const polylineColors: Record<string, string> = {
    metro: '#22c55e', metro_interchange: '#059669',
    walk: '#94a3b8', walk_to_bus: '#94a3b8', walk_to_metro: '#94a3b8',
    walk_from_bus: '#94a3b8', walk_from_metro: '#94a3b8',
    bus_ordinary: '#3b82f6', bus_ac_vajra: '#8b5cf6',
    car: '#f97316', driving: '#f97316',
  }

  return (
    <MapContainer
      center={center}
      zoom={13}
      style={{ width: '100%', height: '100%' }}
      zoomControl={true}
    >
      <MapController center={center} mapRef={mapRef} onMapClick={onMapClick} />
      <TrafficLayer />

      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Route polylines - white outline */}
      {routeGeometry?.map((rg, i) => {
        const coords = rg.coordinates.map(c => [c[0], c[1]] as [number, number])
        const isMain = rg.type === 'route'
        const isWalk = rg.label?.toLowerCase().includes('walk') || rg.dashArray === '8, 6'
        const w = rg.weight || (rg.type === 'hover' ? 7 : isMain ? 6 : 4)
        return (
          <Polyline
            key={`route-outline-${i}`}
            positions={coords}
            pathOptions={{
              color: '#ffffff',
              weight: w + (isMain ? 4 : 2),
              opacity: 1,
              lineCap: 'round',
              lineJoin: 'round',
            }}
          />
        )
      })}
      {/* Route polylines - colored fill (solid for transit, dashed for walking) */}
      {routeGeometry?.filter(rg => rg.type !== 'stop').map((rg, i) => {
        const coords = rg.coordinates.map(c => [c[0], c[1]] as [number, number])
        const isMain = rg.type === 'route'
        const isWalk = rg.label?.toLowerCase().includes('walk') || rg.dashArray === '10, 6'
        const w = rg.weight || (rg.type === 'hover' ? 7 : isMain ? 6 : 4)
        return (
          <Polyline
            key={`route-color-${i}`}
            positions={coords}
            pathOptions={{
              color: rg.color,
              weight: w,
              opacity: rg.type === 'hover' ? 0.95 : 0.85,
              dashArray: isWalk ? '10, 6' : rg.dashArray,
              lineCap: 'round',
              lineJoin: 'round',
            }}
          />
        )
      })}

      {/* Transit stop markers */}
      {routeGeometry?.filter(rg => rg.type === 'stop').map((rg, i) => (
        <CircleMarker key={`stop-${i}`}
          center={[rg.coordinates[0][0], rg.coordinates[0][1]]}
          radius={6}
          pathOptions={{ color: '#22c55e', fillColor: '#22c55e33', fillOpacity: 0.6, weight: 2 }}
        >
          {rg.label && <Popup>{rg.label}</Popup>}
        </CircleMarker>
      ))}

      {/* News affected-area markers */}
      {newsItems?.map((item, i) => {
        if (!item.lat || !item.lng) return null
        const bgColor = item.impact === 'negative' ? '#ef4444' : item.impact === 'positive' ? '#22c55e' : '#3b82f6'
        const emoji = item.impact === 'negative' ? '⚠️' : item.impact === 'positive' ? '✅' : 'ℹ️'
        return (
          <Marker
            key={`news-${i}`}
            position={[item.lat, item.lng]}
            icon={L.divIcon({
              className: '',
              html: `<div style="font-size:18px;filter:drop-shadow(0 0 6px ${bgColor});text-align:center">${emoji}</div>`,
              iconSize: [24, 24],
              iconAnchor: [12, 12],
            })}
          >
            <Popup>
              <div style={{ minWidth: 160 }}>
                <strong>{item.title}</strong><br />
                <span style={{ fontSize: 11, color: '#666' }}>{item.description}</span>
                <div style={{ fontSize: 10, color: '#999', marginTop: 4 }}>{item.timestamp}</div>
              </div>
            </Popup>
          </Marker>
        )
      })}

      {userLocation && !trackingActive && (
        <Marker position={userLocation} icon={userIcon}>
          <Popup>
            <strong>📍 Your Location</strong>
            <br />
            <span style={{ fontSize: 12, color: '#666' }}>
              {userLocation[0].toFixed(4)}, {userLocation[1].toFixed(4)}
            </span>
          </Popup>
        </Marker>
      )}

      {liveTrackingPos && (
        <Marker position={liveTrackingPos} icon={createColoredPin('#22c55e', '🟢', 36, true)}>
          <Popup>
            <strong>📍 Live Position</strong>
            <br />
            <span style={{ fontSize: 12, color: '#666' }}>
              {liveTrackingPos[0].toFixed(4)}, {liveTrackingPos[1].toFixed(4)}
            </span>
            <br />
            <span style={{ fontSize: 11, color: '#22c55e' }}>🚶 Tracking active</span>
          </Popup>
        </Marker>
      )}

      {sourceLocation && (
        <Marker position={sourceLocation} icon={sourceIcon}>
          <Popup>Source</Popup>
        </Marker>
      )}

      {destLocation && (
        <Marker position={destLocation} icon={destIcon}>
          <Popup>Destination</Popup>
        </Marker>
      )}

      {allMarkers.map((place, i) => {
        const score = place.reliability_score || 0.5
        const isGood = score > 0.7
        const emoji = getPlaceEmoji(place.place_type)
        const isSelected = selectedPlace &&
          Math.abs(place.lat - selectedPlace.lat) < 0.001 &&
          Math.abs(place.lng - selectedPlace.lng) < 0.001

        const icon = L.divIcon({
          className: '',
          html: `<div style="font-size:${isSelected ? 34 : 24}px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">${isGood ? '🟢' : '🔴'}${emoji}</div>`,
          iconSize: [isSelected ? 34 : 24, isSelected ? 34 : 24],
          iconAnchor: [isSelected ? 17 : 12, isSelected ? 34 : 24],
          popupAnchor: [0, isSelected ? -34 : -24],
        })

        return (
          <Marker
            key={`marker-${i}`}
            position={[place.lat, place.lng]}
            icon={icon}
            eventHandlers={{
              click: () => onMarkerClick?.(place),
            }}
          >
            <Popup>
              <div style={{ minWidth: 180 }}>
                <strong>{place.name}</strong><br />
                <span style={{ fontSize: 12, color: '#666' }}>{place.address}</span>
                <div style={{ marginTop: 6, fontSize: 12 }}>
                  ⭐ {place.rating?.toFixed(1) || 'N/A'} | ✅ {((place.reliability_score || 0.5) * 100).toFixed(0)}%
                </div>
                {place.review_summary && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#666', fontStyle: 'italic' }}>
                    {place.review_summary}
                  </div>
                )}
                {place.price_info && (
                  <div style={{ marginTop: 4, fontSize: 12, color: '#f59e0b' }}>
                    💰 {place.price_info}
                  </div>
                )}
                <button
                  onClick={() => onMarkerClick?.(place)}
                  style={{
                    marginTop: 8, padding: '4px 12px',
                    background: '#2563eb', color: 'white',
                    border: 'none', borderRadius: 4, cursor: 'pointer',
                    fontSize: 12
                  }}
                >
                  View Details
                </button>
              </div>
            </Popup>
          </Marker>
        )
      })}

      {selectedPlace && allMarkers.length === 0 && (
        <Marker
          position={[selectedPlace.lat, selectedPlace.lng]}
          icon={L.divIcon({
            className: '',
            html: `<div style="font-size:32px;filter:drop-shadow(0 2px 8px rgba(37,99,235,0.5))">🔵${getPlaceEmoji(selectedPlace.place_type)}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 32],
          })}
        >
          <Popup>
            <strong>{selectedPlace.name}</strong><br />
            <span style={{ fontSize: 12, color: '#666' }}>{selectedPlace.address}</span>
          </Popup>
        </Marker>
      )}

      {/* Waypoint markers (multi-stop) */}
      {waypoints?.map((wp, i) => (
        <Marker
          key={`wp-${i}`}
          position={[wp.lat, wp.lng]}
          icon={L.divIcon({
            className: '',
            html: `<div style="font-size:20px;filter:drop-shadow(0 2px 6px rgba(245,158,11,0.8))">🟠<span style="position:absolute;top:-4px;left:10px;background:#f59e0b;color:#000;font-size:10px;font-weight:bold;padding:1px 4px;border-radius:8px;line-height:14px">${i+1}</span></div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 28],
          })}
        >
          <Popup>
            <strong>📍 Stop {i + 1}</strong><br />
            <span style={{ fontSize: 12, color: '#666' }}>{wp.query || `Waypoint ${i + 1}`}</span>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}