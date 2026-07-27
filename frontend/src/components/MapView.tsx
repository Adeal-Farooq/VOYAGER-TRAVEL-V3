import { useEffect, useRef, useCallback } from 'react'
import { MapContainer, TileLayer, useMap, Polyline, Marker, Popup, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import type { PlaceResult, MapRouteGeometry, NewsItem } from '../types'
import { getPlaceIconName, getScoreLabel, getScoreColor } from '../utils/helpers'

interface MapViewProps {
  mapRef: React.MutableRefObject<any>
  center: [number, number]
  onCenterChange?: (center: [number, number]) => void
  userLocation: [number, number] | null
  allMarkers: PlaceResult[]
  selectedPlace: PlaceResult | null
  onMarkerClick?: (place: PlaceResult) => void
  routeGeometry: MapRouteGeometry[] | null
  sourceLocation: [number, number] | null
  destLocation: [number, number] | null
  liveTrackingPos: [number, number] | null
  trackingActive: boolean
  newsItems: NewsItem[]
}

function MapController({ mapRef, onCenterChange, center }: {
  mapRef: React.MutableRefObject<any>
  onCenterChange?: (center: [number, number]) => void
  center: [number, number]
}) {
  const map = useMap()
  mapRef.current = map
  const cbRef = useRef(onCenterChange)
  cbRef.current = onCenterChange
  useEffect(() => {
    if (!cbRef.current) return
    const handler = () => {
      const c = map.getCenter()
      cbRef.current?.([c.lat, c.lng])
    }
    map.on('moveend', handler)
    return () => map.off('moveend', handler)
  }, [map])
  return null
}

function UserLocationMarker({ position }: { position: [number, number] }) {
  return (
    <Marker position={position} icon={L.divIcon({
      className: '', html: `<div style="position:relative;width:28px;height:28px">
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:28px;height:28px;border-radius:50%;background:rgba(0,102,255,0.15);animation:pulse-ring 2s cubic-bezier(0.4,0,0.6,1) infinite;"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:14px;height:14px;border-radius:50%;background:#0066FF;border:2px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>
      </div>`, iconSize: [28, 28], iconAnchor: [14, 14],
    })} />
  )
}

function createPinHtml(place: PlaceResult): string {
  const score = place.reliability_score || 0.5
  const color = getScoreColor(score * 100)
  const icon = getPlaceIconName(place.place_type)
  return `<div style="position:relative;width:32px;height:32px;">
    <div style="position:absolute;top:0;left:0;width:32px;height:32px;border-radius:50%;background:${color};border:2px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.25);font-size:16px;color:white;cursor:pointer;transition:all 0.2s;"
      onmouseover="this.style.transform='scale(1.15)'" onmouseout="this.style.transform='scale(1)'">
      <span class="material-symbols-outlined" style="font-size:16px;font-variation-settings:'wght'400,'FILL'1">${icon}</span>
    </div>
  </div>`
}

function PlaceMarker({ place, onClick }: { place: PlaceResult; onClick?: (p: PlaceResult) => void }) {
  const score = place.reliability_score || 0.5
  return (
    <Marker position={[place.lat, place.lng]}
      icon={L.divIcon({ className: '', html: createPinHtml(place), iconSize: [32, 32], iconAnchor: [16, 16] })}
      eventHandlers={{ click: () => onClick?.(place) }}>
      <Popup>
        <div style={{ minWidth: 200 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{place.name}</div>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{place.place_type.replace(/_/g, ' ')}</div>
          {place.rating && <div style={{ fontSize: 12, marginBottom: 2 }}>⭐ {place.rating.toFixed(1)}</div>}
          <div style={{ fontSize: 12, marginBottom: 2 }}>
            Reliability: <span style={{ color: getScoreColor(score * 100), fontWeight: 600 }}>{(score * 100).toFixed(0)}%</span>
          </div>
          {place.review_summary && (
            <div style={{ fontSize: 11, fontStyle: 'italic', marginTop: 4, color: '#666', lineHeight: 1.4 }}>{place.review_summary}</div>
          )}
          {place.hotel_prices && place.hotel_prices.avg_price > 0 && (
            <div style={{ fontSize: 12, marginTop: 4, color: '#b45309', fontWeight: 500 }}>₹{place.hotel_prices.min_price}-{place.hotel_prices.max_price}/night</div>
          )}
        </div>
      </Popup>
    </Marker>
  )
}

export default function MapView({
  mapRef, center, onCenterChange, userLocation,
  allMarkers, selectedPlace, onMarkerClick,
  routeGeometry, sourceLocation, destLocation,
  liveTrackingPos, trackingActive, newsItems,
}: MapViewProps) {

  return (
    <MapContainer center={center} zoom={13} style={{ width: '100%', height: '100%', background: '#e8e8ec' }}
      zoomControl={true}>
      <MapController mapRef={mapRef} onCenterChange={onCenterChange} center={center} />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://openstreetmap.org/copyright">OSM</a>'
      />

      {userLocation && !trackingActive && <UserLocationMarker position={userLocation} />}
      {liveTrackingPos && trackingActive && <UserLocationMarker position={liveTrackingPos} />}

      {allMarkers.map((place, i) => (
        <PlaceMarker key={i} place={place} onClick={onMarkerClick} />
      ))}

      {selectedPlace && !allMarkers.some(m => m.name === selectedPlace.name && m.lat === selectedPlace.lat) && (
        <Marker position={[selectedPlace.lat, selectedPlace.lng]} icon={L.divIcon({
          className: '', html: `<div style="width:36px;height:36px;border-radius:50%;background:#8b5cf6;border:3px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 12px rgba(139,92,246,0.5);font-size:18px;color:white;animation:pulse-ring 2s cubic-bezier(0.4,0,0.6,1) infinite;"><span class="material-symbols-outlined" style="font-size:18px;font-variation-settings:'FILL'1">star</span></div>`,
          iconSize: [36, 36], iconAnchor: [18, 18],
        })}>
          <Popup>{selectedPlace.name}</Popup>
        </Marker>
      )}

      {routeGeometry?.map((geo, i) => (
        geo.type === 'stop' ? (
          <CircleMarker key={i} center={geo.coordinates[0]} radius={6}
            pathOptions={{ color: geo.color, fillColor: geo.color, fillOpacity: 0.8, weight: 2 }}>
            {geo.label && <Popup>{geo.label}</Popup>}
          </CircleMarker>
        ) : (
          <Polyline key={i} positions={geo.coordinates}
            pathOptions={{
              color: geo.color, weight: geo.weight || 4, opacity: 0.85,
              dashArray: geo.dashArray,
              lineCap: 'round', lineJoin: 'round',
            }}>
            {geo.label && <Popup>{geo.label}</Popup>}
          </Polyline>
        )
      ))}

      {sourceLocation && (
        <Marker position={sourceLocation} icon={L.divIcon({
          className: '', html: `<div style="width:32px;height:32px;border-radius:50%;background:#22c55e;border:3px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(34,197,94,0.4);font-size:16px;color:white;"><span class="material-symbols-outlined" style="font-size:16px;font-variation-settings:'FILL'1">trip_origin</span></div>`,
          iconSize: [32, 32], iconAnchor: [16, 16],
        })}>
          <Popup>Source</Popup>
        </Marker>
      )}

      {destLocation && (
        <Marker position={destLocation} icon={L.divIcon({
          className: '', html: `<div style="position:relative;width:40px;height:40px;"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:40px;height:40px;border-radius:50%;background:rgba(239,68,68,0.15);animation:pulse-ring 2s cubic-bezier(0.4,0,0.6,1) infinite;"></div><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:36px;height:36px;border-radius:50%;background:#ef4444;border:3px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 12px rgba(239,68,68,0.4);font-size:18px;color:white;"><span class="material-symbols-outlined" style="font-size:18px;font-variation-settings:'FILL'1">location_on</span></div></div>`,
          iconSize: [40, 40], iconAnchor: [20, 20],
        })}>
          <Popup>Destination</Popup>
        </Marker>
      )}

      {newsItems.filter(n => n.lat && n.lng).map((item, i) => (
        <Marker key={i} position={[item.lat!, item.lng!]} icon={L.divIcon({
          className: '', html: `<div style="width:24px;height:24px;border-radius:50%;background:${item.impact === 'positive' ? '#22c55e' : item.impact === 'negative' ? '#ef4444' : '#3b82f6'};border:2px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.3);font-size:12px;color:white;">!</div>`,
          iconSize: [24, 24], iconAnchor: [12, 12],
        })}>
          <Popup>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</div>
            <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>{item.description}</div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
