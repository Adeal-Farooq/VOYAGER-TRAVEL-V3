import { useState, useCallback, useEffect, useRef } from 'react'
import { useApp } from '../context/AppContext'
import type { PlaceResult, RouteOption, RouteLeg, MapRouteGeometry, RidePrice, NewsItem, AllSegment } from '../types'
import { searchPlaces, getSuggestions, planRoute, getRidePrices, getAllSegments } from '../services/api'
import { getModeLabel, formatDuration, formatRupees, getScoreColor } from '../utils/helpers'
import SegmentFlowView from './SegmentFlowView'

interface AToBPanelProps {
  onRouteGeometry: (geo: MapRouteGeometry[] | null) => void
  onNewsUpdate: (news: NewsItem[]) => void
}

type SubMode = 'transport' | 'drive' | 'walk'
type TransportType = 'direct' | 'segment'

export default function AToBPanel({ onRouteGeometry, onNewsUpdate }: AToBPanelProps) {
  const {
    sourceLocation, setSourceLocation, destLocation, setDestLocation,
    sourceQuery, setSourceQuery, destQuery, setDestQuery,
    groupSize, setGroupSize, budget, setBudget,
    mapRef, startJourney, userLocation,
  } = useApp()

  const [sourceSuggestions, setSourceSuggestions] = useState<string[]>([])
  const [destSuggestions, setDestSuggestions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [subMode, setSubMode] = useState<SubMode>('transport')
  const [transportType, setTransportType] = useState<TransportType>('segment')
  const [routes, setRoutes] = useState<RouteOption[]>([])
  const [selectedRouteKey, setSelectedRouteKey] = useState<string | null>(null)
  const [ridePrices, setRidePrices] = useState<RidePrice[]>([])
  const [showPrices, setShowPrices] = useState(false)
  const [expandedLegs, setExpandedLegs] = useState<number | null>(null)
  const [activeHopIndex, setActiveHopIndex] = useState<number>(0)
  const [showHopFlow, setShowHopFlow] = useState(false)
  const [segments, setSegments] = useState<AllSegment[]>([])
  const [segmentsLoading, setSegmentsLoading] = useState(false)
  const [viewMode, setViewMode] = useState<'routes' | 'segments'>('routes')
  const [showSegmentModal, setShowSegmentModal] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const getRouteKey = (r: RouteOption) =>
    `${r.type}-${r.total_fare}-${r.total_duration_minutes}-${r.total_distance_km}`

  useEffect(() => {
    if (!sourceQuery || sourceQuery.length < 2) { setSourceSuggestions([]); return }
    const t = setTimeout(async () => {
      try { setSourceSuggestions(await getSuggestions(sourceQuery)) }
      catch { setSourceSuggestions([]) }
    }, 300)
    return () => clearTimeout(t)
  }, [sourceQuery])

  useEffect(() => {
    if (!destQuery || destQuery.length < 2) { setDestSuggestions([]); return }
    const t = setTimeout(async () => {
      try { setDestSuggestions(await getSuggestions(destQuery)) }
      catch { setDestSuggestions([]) }
    }, 300)
    return () => clearTimeout(t)
  }, [destQuery])

  const pickSource = useCallback(async (q: string) => {
    setSourceQuery(q); setSourceSuggestions([])
    const data = await searchPlaces(q, 12.9716, 77.5946)
    if (data.results?.[0]) setSourceLocation([data.results[0].lat, data.results[0].lng])
  }, [setSourceLocation, setSourceQuery])

  const pickDest = useCallback(async (q: string) => {
    setDestQuery(q); setDestSuggestions([])
    const data = await searchPlaces(q, 12.9716, 77.5946)
    if (data.results?.[0]) {
      setDestLocation([data.results[0].lat, data.results[0].lng])
      if (mapRef.current) mapRef.current.flyTo([data.results[0].lat, data.results[0].lng], 13)
    }
  }, [setDestLocation, setDestQuery, mapRef])

  const handleFindRoutes = useCallback(async () => {
    let srcLoc = sourceLocation
    let dstLoc = destLocation
    if (!srcLoc && sourceQuery.toLowerCase() === 'current location') {
      srcLoc = userLocation || [12.9716, 77.5946]
      setSourceLocation(srcLoc)
    }
    if (!dstLoc && destQuery) {
      try {
        const data = await searchPlaces(destQuery, 12.9716, 77.5946)
        if (data.results?.[0]) {
          dstLoc = [data.results[0].lat, data.results[0].lng]
          setDestLocation(dstLoc)
        }
      } catch {}
    }
    if (!srcLoc || !dstLoc) { setError('Please set both source and destination'); setLoading(false); return }
    setLoading(true); setError(''); setRoutes([]); setSelectedRouteKey(null)
    setSegments([]); setSegmentsLoading(false); setShowSegmentModal(false); setViewMode('routes')
    onRouteGeometry(null)
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      if (subMode === 'drive') {
        const data = await planRoute({
          source_lat: srcLoc[0], source_lng: srcLoc[1],
          dest_lat: dstLoc[0], dest_lng: dstLoc[1],
          mode: 'personal', group_size: groupSize, budget: budget,
        })
        if (ctrl.signal.aborted) return
        if (data?.routes) setRoutes(data.routes)
        const prices = await getRidePrices(
          sourceQuery || 'Source', destQuery || 'Destination',
          srcLoc[0], srcLoc[1],
          dstLoc[0], dstLoc[1],
        )
        if (!ctrl.signal.aborted) setRidePrices(prices?.prices || [])
      } else if (subMode === 'walk') {
        const data = await planRoute({
          source_lat: srcLoc[0], source_lng: srcLoc[1],
          dest_lat: dstLoc[0], dest_lng: dstLoc[1],
          mode: 'walking', group_size: groupSize, budget: budget,
        })
        if (ctrl.signal.aborted) return
        if (data?.routes) setRoutes(data.routes)
      } else if (subMode === 'transport') {
        if (transportType === 'direct') {
          const [pricesRes, driveRes] = await Promise.allSettled([
            getRidePrices(sourceQuery || 'Source', destQuery || 'Destination',
              srcLoc[0], srcLoc[1], dstLoc[0], dstLoc[1]),
            planRoute({
              source_lat: srcLoc[0], source_lng: srcLoc[1],
              dest_lat: dstLoc[0], dest_lng: dstLoc[1],
              mode: 'personal', group_size: groupSize, budget: budget,
            }),
          ])
          if (!ctrl.signal.aborted) {
            setRidePrices(pricesRes.status === 'fulfilled' ? (pricesRes.value?.prices || []) : [])
            if (driveRes.status === 'fulfilled' && driveRes.value?.routes) {
              setRoutes(driveRes.value.routes)
            }
            setShowPrices(true)
          }
        } else {
          // Load planRoute first — show routes immediately
          let routesData: any = null
          try {
            routesData = await planRoute({
              source_lat: srcLoc[0], source_lng: srcLoc[1],
              dest_lat: dstLoc[0], dest_lng: dstLoc[1],
              mode: 'public', group_size: groupSize, budget: budget,
            })
          } catch {}
          if (ctrl.signal.aborted) return
          if (routesData?.routes) setRoutes(routesData.routes)

          // Load getAllSegments asynchronously with own loading state
          setSegmentsLoading(true)
          getAllSegments(
            srcLoc[0], srcLoc[1], sourceQuery || 'Current Location',
            dstLoc[0], dstLoc[1], destQuery || 'Destination',
            groupSize, budget, 3
          ).then(segRes => {
            if (ctrl.signal.aborted) return
            if (segRes?.data?.segments?.length) {
              setSegments(segRes.data.segments)
              setShowSegmentModal(true)
            }
          }).catch(() => {}).finally(() => {
            if (!ctrl.signal.aborted) setSegmentsLoading(false)
          })
          const prices = await getRidePrices(
            sourceQuery || 'Source', destQuery || 'Destination',
            srcLoc[0], srcLoc[1],
            dstLoc[0], dstLoc[1],
          )
          if (!ctrl.signal.aborted) setRidePrices(prices?.prices || [])
        }
      }
    } catch (err) {
      if (!ctrl.signal.aborted) setError('Failed to find routes. Please try again.')
    } finally { if (!ctrl.signal.aborted) setLoading(false) }
  }, [sourceLocation, destLocation, subMode, transportType, groupSize, budget, sourceQuery, destQuery, onRouteGeometry, userLocation])

  useEffect(() => {
    const route = routes.find(r => getRouteKey(r) === selectedRouteKey)
    if (!selectedRouteKey || !route) {
      onRouteGeometry(null); return
    }
    const parseCoord = (c: any): [number, number] => {
      if (Array.isArray(c) && c.length === 2) return [Number(c[0]), Number(c[1])]
      if (typeof c === 'string') {
        const parts = c.split(' ').map(Number)
        if (parts.length === 2 && !isNaN(parts[0])) return [parts[0], parts[1]]
        const partsC = c.split(',').map(Number)
        if (partsC.length === 2 && !isNaN(partsC[0])) return [partsC[0], partsC[1]]
      }
      return [0, 0]
    }
    const geo: MapRouteGeometry[] = []
    if (route.geometry?.coordinates) {
      geo.push({
        type: 'route', color: 'var(--primary)', weight: 5,
        coordinates: route.geometry.coordinates.map((c: any) => [c[1], c[0]]),
      })
    }
    route.legs?.forEach((leg, i) => {
      if (leg.path && leg.path.length > 0) {
        const coords = (leg.path as any[]).map(parseCoord).filter((c: [number,number]) => c[0] !== 0 || c[1] !== 0)
        if (coords.length > 0) {
          geo.push({
            type: 'segment', color: leg.mode === 'walk' ? 'var(--secondary)' : 'var(--primary)',
            weight: leg.mode === 'walk' ? 3 : 4,
            dashArray: leg.mode === 'walk' ? '8, 4' : undefined,
            coordinates: coords,
            label: `${leg.from} → ${leg.to}`,
          })
        }
      }
    })
    onRouteGeometry(geo)
  }, [selectedRouteKey, routes, onRouteGeometry])

  const swapLocations = useCallback(() => {
    setSourceQuery(destQuery); setDestQuery(sourceQuery)
    setSourceLocation(destLocation); setDestLocation(sourceLocation)
  }, [sourceQuery, destQuery, sourceLocation, destLocation, setSourceQuery, setDestQuery, setSourceLocation, setDestLocation])

  const TRANSIT_MODES = new Set(['bus_ordinary', 'bus_ac_vajra', 'kia_bus', 'metro', 'metro_interchange', 'bus_to_metro', 'metro_to_bus', 'walk', 'multi_modal', 'astar'])
  const RIDE_MODES = new Set(['cab', 'auto', 'bike'])

  const getTopRoutes = () => {
    let filtered = [...routes]
    if (subMode === 'transport' && transportType === 'segment') {
      filtered = filtered.filter(r => TRANSIT_MODES.has(r.type) || r.type === 'walk')
    } else if (subMode === 'transport' && transportType === 'direct') {
      filtered = filtered.filter(r => RIDE_MODES.has(r.type) || r.type === 'car' || r.type === 'drive')
    }
    const sorted = filtered.sort((a, b) => (b.overall_score || 0) - (a.overall_score || 0))
    return { top5: sorted.slice(0, 5), all: sorted }
  }

  const { top5, all } = getTopRoutes()

  return (
    <div>
      <div className="glass-strong ambient-shadow" style={{ padding: 12, borderRadius: 'var(--radius-xl)', marginBottom: 12, position: 'relative' }}>
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', marginBottom: 6, borderRadius: 'var(--radius-md)', background: 'var(--surface-container-lowest)', border: sourceLocation ? '1px solid var(--secondary)' : '1px solid var(--outline-variant)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--secondary)', fontVariationSettings: "'FILL' 1" }}>{sourceLocation ? 'check_circle' : 'my_location'}</span>
            <input type="text" placeholder="Current Location..."
              value={sourceQuery}
              onChange={(e) => setSourceQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') pickSource(sourceQuery) }}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, background: 'transparent', color: 'var(--text)' }}
            />
            {sourceQuery && (
              <>
                <button onClick={() => pickSource(sourceQuery)}
                  style={{ background: 'var(--primary)', border: 'none', borderRadius: 'var(--radius-sm)', color: 'white', cursor: 'pointer', padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                  OK
                </button>
                <button onClick={() => { setSourceQuery(''); setSourceLocation(null) }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                </button>
              </>
            )}
          </div>
          {sourceSuggestions.length > 0 && (
            <div className="glass" style={{ position: 'absolute', left: 0, right: 0, top: 48, zIndex: 100, borderRadius: 'var(--radius-md)', boxShadow: '0 8px 32px var(--shadow-primary)', maxHeight: 160, overflowY: 'auto' }}>
              {sourceSuggestions.map((s, i) => (
                <div key={i} onClick={() => pickSource(s)}
                  style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 13, borderBottom: i < sourceSuggestions.length - 1 ? '1px solid var(--outline-variant)' : 'none', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)' }}>location_on</span>
                  {s}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative' }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 'var(--radius-md)', background: 'var(--surface-container-lowest)', border: destLocation ? '1px solid var(--error)' : '1px solid var(--outline-variant)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--error)', fontVariationSettings: "'FILL' 1" }}>{destLocation ? 'check_circle' : 'location_on'}</span>
            <input type="text" placeholder="Where to?"
              value={destQuery}
              onChange={(e) => setDestQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') pickDest(destQuery) }}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, background: 'transparent', color: 'var(--text)' }}
            />
            {destQuery && (
              <>
                <button onClick={() => pickDest(destQuery)}
                  style={{ background: 'var(--primary)', border: 'none', borderRadius: 'var(--radius-sm)', color: 'white', cursor: 'pointer', padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                  OK
                </button>
                <button onClick={() => { setDestQuery(''); setDestLocation(null) }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                </button>
              </>
            )}
          </div>
          <button onClick={swapLocations}
            style={{ width: 36, height: 36, borderRadius: '50%', border: '1px solid var(--outline-variant)', background: 'var(--surface-container-lowest)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--text-muted)' }}>swap_vert</span>
          </button>
        </div>
        {destSuggestions.length > 0 && (
          <div className="glass" style={{ position: 'absolute', left: 0, right: 52, zIndex: 100, borderRadius: 'var(--radius-md)', boxShadow: '0 8px 32px var(--shadow-primary)', maxHeight: 160, overflowY: 'auto' }}>
            {destSuggestions.map((s, i) => (
              <div key={i} onClick={() => pickDest(s)}
                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 13, borderBottom: i < destSuggestions.length - 1 ? '1px solid var(--outline-variant)' : 'none', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)' }}>location_on</span>
                {s}
              </div>
            ))}
          </div>
        )}

        <div className="mode-selector" style={{ marginTop: 8 }}>
          {([
            { key: 'transport', icon: 'directions_transit', label: 'Public / Online' },
            { key: 'drive', icon: 'directions_car', label: 'Drive' },
            { key: 'walk', icon: 'directions_walk', label: 'Walk' },
          ] as { key: SubMode; icon: string; label: string }[]).map(m => (
            <button key={m.key}
              onClick={() => setSubMode(m.key)}
              className={`mode-btn${subMode === m.key ? ' active' : ''}`}>
              <span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: 'middle', marginRight: 4 }}>{m.icon}</span>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {subMode === 'transport' && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
          {([
            { key: 'segment', icon: 'layers', label: 'Multi-Hop Transit' },
            { key: 'direct', icon: 'local_taxi', label: 'Direct Ride' },
          ] as { key: TransportType; icon: string; label: string }[]).map(t => (
            <button key={t.key} onClick={() => setTransportType(t.key)}
              className={`mode-btn${transportType === t.key ? ' active' : ''}`}
              style={{ fontSize: 12, padding: '8px 10px' }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 4 }}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>
      )}

      <div className="preferences-panel">
        <div className="pref-row">
          <span><span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: 'middle', marginRight: 4 }}>group</span> Group Size</span>
          <input type="number" min={1} max={20} value={groupSize}
            onChange={(e) => setGroupSize(Math.max(1, parseInt(e.target.value) || 1))} />
        </div>
        <div className="pref-row">
          <span><span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: 'middle', marginRight: 4 }}>payments</span> Budget (₹)</span>
          <input type="number" min={0} placeholder="No limit" value={budget || ''}
            onChange={(e) => setBudget(e.target.value ? parseInt(e.target.value) : undefined)} />
        </div>
      </div>

      <button onClick={handleFindRoutes} disabled={loading || !sourceLocation || !destLocation} className="go-btn">
        <><span className="material-symbols-outlined" style={{ fontSize: 18, verticalAlign: 'middle', marginRight: 6 }}>route</span> Find Routes</>
      </button>

      {loading && (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto 10px' }} />
          <div style={{ fontSize: 13 }}>Finding routes<span className="loading">...</span></div>
        </div>
      )}

      {segmentsLoading && !loading && (
        <div style={{ padding: '12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <div className="spinner" style={{ width: 16, height: 16 }} />
          Loading multi-hop segments<span className="loading">...</span>
        </div>
      )}

      {error && (
        <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-md)', background: 'var(--error-container)', color: 'var(--error)', fontSize: 13, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>error</span>
          {error}
        </div>
      )}

      {transportType === 'direct' && subMode === 'transport' && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--primary)' }}>local_taxi</span>
            <span className="text-headline-sm">Ride Options</span>
            <button onClick={() => setShowPrices(!showPrices)}
              style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: 12 }}>
              {showPrices ? 'Hide' : 'Show prices'}
            </button>
          </div>
          {showPrices && ridePrices.length > 0 && ridePrices.map((p, i) => {
            const driveRoute = routes.find(r => r.type === 'car' || r.type === 'drive' || r.type === 'personal')
            const isSelected = selectedRouteKey === `ride-${i}`
            return (
            <div key={i} onClick={() => {
              setSelectedRouteKey(`ride-${i}`)
              if (driveRoute?.geometry?.coordinates) {
                onRouteGeometry([{
                  type: 'route', color: 'var(--primary)', weight: 5,
                  coordinates: driveRoute.geometry.coordinates.map((c: any) => [c[1], c[0]]),
                }])
              }
            }}
              className={`scale-in${isSelected ? ' route-card selected' : ''}`}
              style={{
                padding: '10px 14px', marginBottom: 6, borderRadius: 'var(--radius-md)',
                background: isSelected ? 'var(--primary-container)' : 'var(--surface-container)',
                border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--outline-variant)'}`,
                cursor: 'pointer', transition: 'all 0.15s',
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--primary)' }}>
                    {p.mode === 'auto' ? 'pedal_bike' : p.mode === 'bike' ? 'motorcycle' : 'local_taxi'}
                  </span>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>{p.provider}</span>
                    <span className="text-body-sm" style={{ color: 'var(--text-muted)', marginLeft: 6 }}>{p.mode}</span>
                  </div>
                </div>
                <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--primary)' }}>₹{p.price}</div>
              </div>
              <div className="text-body-sm" style={{ color: 'var(--text-muted)', marginTop: 2 }}>
                ETA: {p.eta_minutes} min {p.note ? `• ${p.note}` : ''}
              </div>
            </div>
          )})}
          {showPrices && ridePrices.length === 0 && (
            <div className="text-body-md" style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 12 }}>
              Click "Find Routes" to see ride prices
            </div>
          )}
        </div>
      )}

      {transportType !== 'segment' && top5.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--primary)' }}>route</span>
            <span className="text-headline-sm">{subMode === 'transport' ? 'Ride Options' : subMode === 'drive' ? 'Driving Options' : 'Walking Routes'}</span>
          </div>

          {top5.map((route, idx) => {
            const isBest = idx === 0
            const routeKey = getRouteKey(route)
            const isSelected = selectedRouteKey === routeKey
            return (
              <div key={routeKey} onClick={() => setSelectedRouteKey(routeKey)}
                className={`route-card${isSelected ? ' selected' : ''}`} style={{
                  borderLeft: `4px solid ${getScoreColor(route.overall_score)}`,
                  padding: 12, marginBottom: 8,
                }}>
                {isBest && (
                  <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                    <span className="badge-best">Best Match</span>
                    <span className="reliability-pill" style={{ background: getScoreColor(route.overall_score), color: 'white' }}>
                      Score: {route.overall_score}
                    </span>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span className="text-headline-sm">
                    <span className="material-symbols-outlined" style={{ fontSize: 18, verticalAlign: 'middle', marginRight: 4 }}>
                      {route.type === 'car' || route.type === 'drive' ? 'directions_car' :
                       route.type === 'walk' ? 'directions_walk' : 'directions_transit'}
                    </span>
                    {route.provider || getModeLabel(route.type)}
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--primary)' }}>{formatRupees(route.total_fare)}</span>
                </div>

                <div className="route-stats">
                  <span><span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 2 }}>schedule</span> {formatDuration(route.total_duration_minutes)}</span>
                  <span><span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 2 }}>straighten</span> {route.total_distance_km} km</span>
                  {route.total_walking_km > 0 && <span>🚶 {route.total_walking_km} km walk</span>}
                  {route.route_numbers?.length ? <span>🚌 {route.route_numbers.join(', ')}</span> : null}
                </div>

                <div className="score-bar" style={{ marginTop: 6, height: 5, borderRadius: 3 }}>
                  <div className="score-fill" style={{ width: `${route.overall_score}%`, background: getScoreColor(route.overall_score) }} />
                </div>

                {route.score_explanation && (
                  <div className="text-body-sm" style={{ color: 'var(--text-muted)', marginTop: 4 }}>
                    {route.score_explanation}
                  </div>
                )}

                {isSelected && !showHopFlow && (
                  <button onClick={(e) => {
                    e.stopPropagation()
                    setShowHopFlow(true)
                    setActiveHopIndex(0)
                    const fl = route.legs?.[0]
                    if (fl?.path && onRouteGeometry) onRouteGeometry([{ type: 'route', coordinates: fl.path.map(p => [p[1], p[0]]), color: 'var(--primary)', weight: 4 }])
                  }}
                    style={{ width: '100%', padding: '8px', marginTop: 8, border: '1px dashed var(--primary)', borderRadius: 'var(--radius-md)', background: 'transparent', color: 'var(--primary)', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>route</span>
                    View Steps
                  </button>
                )}

                {isSelected && showHopFlow && activeHopIndex < (route.legs?.length ?? 0) && (() => {
                  const leg = route.legs![activeHopIndex]
                  const isLast = activeHopIndex === route.legs!.length - 1
                  const modeIcon = leg.mode === 'walk' ? 'directions_walk'
                    : leg.mode === 'car' || leg.mode === 'drive' ? 'directions_car'
                    : leg.mode === 'metro' ? 'subway'
                    : leg.mode === 'train' ? 'train'
                    : 'directions_bus'
                  const modeLabel = leg.mode === 'walk' ? 'Walk'
                    : leg.mode === 'car' || leg.mode === 'drive' ? 'Drive'
                    : leg.mode === 'metro' ? 'Metro'
                    : leg.mode === 'train' ? 'Train'
                    : 'Bus'
                  return (
                    <div style={{ marginTop: 8, padding: '12px', background: 'var(--surface-container)', borderRadius: 'var(--radius-md)', border: '1px solid var(--primary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                          Step {activeHopIndex + 1} of {route.legs!.length}
                        </span>
                        <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--primary-container)', color: 'var(--primary)', fontWeight: 600 }}>
                          {modeLabel}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 6 }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 20, color: 'var(--primary)' }}>{modeIcon}</span>
                        <span style={{ fontWeight: 600, flex: 1 }}>{leg.from}</span>
                        <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--text-muted)' }}>arrow_forward</span>
                        <span style={{ fontWeight: 600, flex: 1, textAlign: 'right' }}>{leg.to}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', marginBottom: leg.instructions ? 6 : 0, flexWrap: 'wrap' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}><span className="material-symbols-outlined" style={{ fontSize: 14 }}>schedule</span> {formatDuration(leg.duration_minutes)}</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}><span className="material-symbols-outlined" style={{ fontSize: 14 }}>straighten</span> {leg.distance_km} km</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}><span className="material-symbols-outlined" style={{ fontSize: 14 }}>payments</span> ₹{leg.fare}</span>
                      </div>
                      {leg.instructions && (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 4, padding: '6px 8px', background: 'var(--surface-container-lowest)', borderRadius: 'var(--radius-sm)' }}>
                          {leg.instructions}
                        </div>
                      )}
                      {leg.route_numbers && leg.route_numbers.length > 0 && (
                        <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                          {leg.route_numbers.map((rn, ri) => (
                            <span key={ri} style={{ fontSize: 10, padding: '2px 10px', borderRadius: 'var(--radius-full)', background: 'var(--primary-container)', color: 'var(--primary)', fontWeight: 600 }}>
                              {rn}
                            </span>
                          ))}
                        </div>
                      )}
                      <button onClick={(e) => {
                        e.stopPropagation()
                        const nextIdx = activeHopIndex + 1
                        setActiveHopIndex(nextIdx)
                        if (nextIdx < route.legs!.length) {
                          const nextLeg = route.legs![nextIdx]
                          if (nextLeg?.path && onRouteGeometry) onRouteGeometry([{ type: 'route', coordinates: nextLeg.path.map(p => [p[1], p[0]]), color: 'var(--primary)', weight: 4 }])
                        }
                      }}
                        style={{ width: '100%', padding: '8px', marginTop: 8, border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--secondary)', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                        {isLast ? 'Finish' : 'Next'} <span className="material-symbols-outlined" style={{ fontSize: 14 }}>arrow_forward</span>
                      </button>
                    </div>
                  )
                })()}

                {isSelected && showHopFlow && activeHopIndex >= (route.legs?.length ?? 0) && (
                  <div style={{ marginTop: 8, padding: '16px', background: 'var(--secondary-container)', borderRadius: 'var(--radius-md)', border: '1px solid var(--secondary)', textAlign: 'center' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 32, color: 'var(--secondary)' }}>location_on</span>
                    <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--secondary)', marginTop: 4 }}>Arrived at Destination!</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>You have reached {destQuery || 'your destination'}</div>
                    <button onClick={(e) => { e.stopPropagation(); setShowHopFlow(false); setActiveHopIndex(0); if (onRouteGeometry) onRouteGeometry(null) }}
                      style={{ marginTop: 8, padding: '6px 16px', border: '1px solid var(--text-muted)', borderRadius: 'var(--radius-md)', background: 'transparent', color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer' }}>
                      Reset
                    </button>
                  </div>
                )}

                {isSelected && (
                  <button onClick={(e) => {
                    e.stopPropagation(); startJourney()
                    if (!showHopFlow) {
                      setShowHopFlow(true); setActiveHopIndex(0)
                      const fl = route.legs?.[0]
                      if (fl?.path && onRouteGeometry) onRouteGeometry([{ type: 'route', coordinates: fl.path.map(p => [p[1], p[0]]), color: 'var(--primary)', weight: 4 }])
                    }
                  }}
                    style={{
                      width: '100%', padding: '10px', marginTop: 8, border: 'none',
                      borderRadius: 'var(--radius-md)', background: 'var(--secondary)',
                      color: 'white', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span>
                    Start Journey
                  </button>
                )}
              </div>
            )
          })}

          {all.length > 5 && (
            <details style={{ marginTop: 4 }}>
              <summary>Show all {all.length} options</summary>
              {all.slice(5).map((route, idx) => {
                const routeKey = getRouteKey(route)
                const isSelected = selectedRouteKey === routeKey
                return (
              <div key={routeKey} onClick={() => { setSelectedRouteKey(routeKey); setShowHopFlow(false); setActiveHopIndex(0) }}
                    className={`route-card${isSelected ? ' selected' : ''}`}
                    style={{ borderLeft: `3px solid ${getScoreColor(route.overall_score)}`, padding: 10, marginBottom: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>
                        {route.provider || getModeLabel(route.type)}
                      </span>
                      <span style={{ fontWeight: 700, color: 'var(--primary)', fontSize: 14 }}>{formatRupees(route.total_fare)}</span>
                    </div>
                    <div className="route-stats">
                      <span>{formatDuration(route.total_duration_minutes)}</span>
                      <span>{route.total_distance_km} km</span>
                    </div>
                    <div className="score-bar" style={{ marginTop: 4 }}>
                      <div className="score-fill" style={{ width: `${route.overall_score}%`, background: getScoreColor(route.overall_score) }} />
                    </div>
                  </div>
                )
              })}
            </details>
          )}

        </div>
      )}

      {showSegmentModal && segments.length > 0 && (
            <div className="fade-in" style={{
              position: 'fixed', inset: 0, zIndex: 10000,
              background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }} onClick={() => setShowSegmentModal(false)}>
              <div className="scale-in" style={{
                width: '90%', maxWidth: 960, maxHeight: '85vh',
                background: 'var(--surface)', borderRadius: 'var(--radius-xl)',
                border: '1px solid var(--outline-variant)',
                boxShadow: '0 24px 80px var(--shadow-primary)',
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
              }} onClick={e => e.stopPropagation()}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '14px 18px', borderBottom: '1px solid var(--outline-variant)',
                  background: 'var(--surface-container)',
                }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--primary)' }}>layers</span>
                  <span className="text-headline-sm" style={{ flex: 1 }}>Multi-Hop Transit Planner</span>
                  <button onClick={() => setShowSegmentModal(false)}
                    style={{ width: 32, height: 32, border: 'none', borderRadius: 'var(--radius-full)',
                      background: 'var(--surface-container-high)', color: 'var(--text-muted)',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 16 }}>
                    <span className="material-symbols-outlined">close</span>
                  </button>
                </div>
                <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
                  <SegmentFlowView
                    segments={segments}
                    sourceName={sourceQuery || 'Current Location'}
                    destName={destQuery || 'Destination'}
                    destLat={destLocation?.[0]}
                    destLng={destLocation?.[1]}
                    onRouteGeometry={onRouteGeometry}
                  />
                </div>
              </div>
            </div>
          )}
    </div>
  )
}
