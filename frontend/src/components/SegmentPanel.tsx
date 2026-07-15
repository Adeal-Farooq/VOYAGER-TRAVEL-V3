import { useState, useCallback, useRef, useEffect } from 'react'
import type { SegmentStepOption, MapRouteGeometry, PlaceResult, AllSegmentsResponse, AllSegment, SegmentDestination, TransitOption } from '../types'
import { getAllSegments, searchPlaces } from '../services/api'
import { getModeIcon, getModeLabel, formatDuration, formatRupees } from '../utils/helpers'

const SEGMENT_COLORS = ['#3b82f6', '#22c55e', '#f97316', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4', '#ec4898']
const MODE_COLORS: Record<string, string> = {
  walk: '#22c55e', cab: '#f97316', auto: '#eab308', bike: '#8b5cf6',
  bus_ordinary: '#3b82f6', bus_ac_vajra: '#60a5fa', metro: '#22c55e',
  train: '#a855f7', custom: '#f59e0b',
}

interface SegmentPanelProps {
  sourceLocation: [number, number]
  destLocation: [number, number]
  sourceName: string
  destName: string
  groupSize: number
  budget?: number
  onClose: () => void
  onGeometryChange: (geometry: MapRouteGeometry[]) => void
  onSizeChange?: (width: number) => void
  onStartJourney?: () => void
  trackingActive?: boolean
}

interface BuiltStep {
  opt: SegmentStepOption
  label: string
}

export default function SegmentPanel({
  sourceLocation, destLocation, sourceName, destName,
  groupSize, budget, onClose, onGeometryChange, onSizeChange,
  onStartJourney, trackingActive,
}: SegmentPanelProps) {
  const [data, setData] = useState<AllSegmentsResponse['data'] | null>(null)
  const [loading, setLoading] = useState(false)
  const [hoveredOption, setHoveredOption] = useState<SegmentStepOption | null>(null)
  const [builtPath, setBuiltPath] = useState<BuiltStep[]>([])
  // Chained segment state: for each segment level we track selected dest + transit
  const [chainState, setChainState] = useState<{
    activeSegIdx: number
    selectedDest: SegmentDestination | null
    selectedTransit: TransitOption | null
    selectedFinal: SegmentStepOption | null
  }>({ activeSegIdx: 0, selectedDest: null, selectedTransit: null, selectedFinal: null })
  const [customInput, setCustomInput] = useState('')
  const [customSuggestions, setCustomSuggestions] = useState<PlaceResult[]>([])
  const [customLoading, setCustomLoading] = useState(false)
  const [showCustomInput, setShowCustomInput] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const segments = data?.segments ?? []
  const activeSegment: AllSegment | undefined = segments[chainState.activeSegIdx]
  const directOptions = activeSegment?.direct_options ?? []
  const destinations = activeSegment?.destinations ?? []

  // Fetch all segments on mount
  useEffect(() => {
    setLoading(true)
    getAllSegments(
      sourceLocation[0], sourceLocation[1], sourceName,
      destLocation[0], destLocation[1], destName,
      groupSize, budget, 3
    ).then(res => {
      if (res.data) setData(res.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [sourceLocation, sourceName, destLocation, destName, groupSize, budget])

  const handleReset = useCallback(() => {
    setBuiltPath([])
    setChainState({ activeSegIdx: 0, selectedDest: null, selectedTransit: null, selectedFinal: null })
    setHoveredOption(null)
  }, [])

  const handlePickDirect = useCallback((opt: SegmentStepOption) => {
    setBuiltPath([{ opt, label: `Direct: ${opt.label || getModeLabel(opt.mode)}` }])
    setChainState({ activeSegIdx: 0, selectedDest: null, selectedTransit: null, selectedFinal: opt })
  }, [])

  const handlePickReach = useCallback((dest: SegmentDestination, opt: SegmentStepOption) => {
    setChainState({ activeSegIdx: chainState.activeSegIdx, selectedDest: dest, selectedTransit: null, selectedFinal: null })
    setBuiltPath(prev => {
      const idx = chainState.activeSegIdx
      const filtered = prev.filter(s => s.opt.mode !== 'direct')
      return [...filtered.slice(0, idx), { opt, label: `To ${dest.stop.name}: ${opt.label || getModeLabel(opt.mode)}` }]
    })
  }, [chainState.activeSegIdx])

  const handlePickTransit = useCallback((opt: TransitOption) => {
    if (opt.next_segment_index != null && segments[opt.next_segment_index]) {
      // Move to next segment — show that segment's destinations
      setChainState({ activeSegIdx: opt.next_segment_index, selectedDest: null, selectedTransit: null, selectedFinal: null })
      setBuiltPath(prev => [...prev, { opt, label: `${opt.label || getModeLabel(opt.mode)} to ${opt.to}` }])
    } else if (opt.final_options && opt.final_options.length > 0) {
      // Show final mile options
      setChainState({ activeSegIdx: chainState.activeSegIdx, selectedDest: chainState.selectedDest, selectedTransit: opt, selectedFinal: null })
      setBuiltPath(prev => {
        const base = prev.slice(0, chainState.activeSegIdx + 1)
        return [...base, { opt, label: `${opt.label || getModeLabel(opt.mode)} to ${opt.to}` }]
      })
    } else {
      // No next segment and no final options — just select it
      setChainState({ activeSegIdx: chainState.activeSegIdx, selectedDest: chainState.selectedDest, selectedTransit: opt, selectedFinal: null })
      setBuiltPath(prev => [...prev, { opt, label: `${opt.label || getModeLabel(opt.mode)} to ${opt.to}` }])
    }
  }, [chainState.activeSegIdx, chainState.selectedDest, segments])

  const handlePickFinal = useCallback((opt: SegmentStepOption) => {
    setChainState(prev => ({ ...prev, selectedFinal: opt }))
    setBuiltPath(prev => [...prev, { opt, label: `Final: ${opt.label || getModeLabel(opt.mode)} to ${destName}` }])
  }, [destName])

  const handleGoBack = useCallback(() => {
    const { activeSegIdx, selectedDest, selectedTransit, selectedFinal } = chainState
    if (selectedFinal) {
      setChainState(prev => ({ ...prev, selectedFinal: null }))
      setBuiltPath(prev => prev.slice(0, -1))
      return
    }
    if (selectedTransit) {
      setChainState(prev => ({ ...prev, selectedTransit: null, selectedFinal: null }))
      setBuiltPath(prev => prev.slice(0, -1))
      return
    }
    if (selectedDest) {
      setChainState(prev => ({ ...prev, selectedDest: null, selectedTransit: null, selectedFinal: null }))
      setBuiltPath(prev => prev.slice(0, -1))
      return
    }
    // If in a child segment, go back to the parent segment
    const enterStep = [...builtPath].reverse().find(s => (s.opt as any).next_segment_index != null)
    if (enterStep) {
      const enterOpt = enterStep.opt as any
      const parentSegIdx = segments.findIndex(s =>
        s.segment_index === activeSegIdx - 1 &&
        Math.abs(s.from.lat - enterOpt.from_lat) < 0.01 &&
        Math.abs(s.from.lng - enterOpt.from_lng) < 0.01
      )
      if (parentSegIdx >= 0) {
        // Remove the transit step and all steps after it
        const enterIdx = builtPath.indexOf(enterStep)
        setChainState({ activeSegIdx: parentSegIdx, selectedDest: enterOpt.selectedDest || null, selectedTransit: null, selectedFinal: null })
        setBuiltPath(prev => prev.slice(0, enterIdx))
        return
      }
    }
    if (activeSegIdx > 0) {
      const fallbackIdx = segments.findIndex(s => s.segment_index === activeSegIdx - 1)
      if (fallbackIdx >= 0) {
        setChainState({ activeSegIdx: fallbackIdx, selectedDest: null, selectedTransit: null, selectedFinal: null })
        setBuiltPath(prev => prev.slice(0, fallbackIdx + 1))
        return
      }
    }
    handleReset()
  }, [chainState, segments, builtPath, handleReset])

  const handleAddCustomWaypoint = useCallback((place: PlaceResult) => {
    setShowCustomInput(false)
    setCustomInput('')
    setCustomSuggestions([])
    const destName = chainState.selectedDest?.stop.name || sourceName
    setBuiltPath(prev => [...prev, { opt: {
      mode: 'custom', icon: '📍', label: place.name,
      from: destName, to: place.name,
      distance_km: 0, duration_minutes: 0, fare: 0, per_person: 0,
      arrives_at_stop: true, from_lat: sourceLocation[0], from_lng: sourceLocation[1],
      to_lat: place.lat, to_lng: place.lng,
    } as SegmentStepOption, label: `Custom: ${place.name}` }])
    setChainState({ activeSegIdx: 0, selectedDest: null, selectedTransit: null, selectedFinal: null })
    setLoading(true)
    getAllSegments(
      place.lat, place.lng, place.name,
      destLocation[0], destLocation[1], destName,
      groupSize, budget, 3
    ).then(res => {
      if (res.data) setData(res.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [chainState, sourceName, sourceLocation, destLocation, destName, groupSize, budget])

  const handleCustomInput = useCallback(async (value: string) => {
    setCustomInput(value)
    if (value.length < 2) { setCustomSuggestions([]); return }
    if (abortRef.current) abortRef.current.abort()
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    setCustomLoading(true)
    searchTimerRef.current = setTimeout(async () => {
      const ctrl = new AbortController()
      abortRef.current = ctrl
      try {
        const res = await searchPlaces(value, destLocation[0], destLocation[1], ctrl.signal)
        if (!ctrl.signal.aborted) setCustomSuggestions((res.results || []).slice(0, 5))
      } catch { if (ctrl.signal.aborted) return; setCustomSuggestions([]) }
      finally { setCustomLoading(false) }
    }, 300)
  }, [destLocation])

  // Map geometry
  useEffect(() => {
    const geo: MapRouteGeometry[] = []
    builtPath.forEach((entry, idx) => {
      const opt = entry.opt
      const color = idx < SEGMENT_COLORS.length ? SEGMENT_COLORS[idx] : '#94a3b8'
      const p = opt.path
      if (p && p.length >= 2) {
        geo.push({ type: 'segment', coordinates: p as [number, number][], color, weight: 4, label: `${getModeLabel(opt.mode)}: ${opt.distance_km}km` })
      } else if (opt.from_lat && opt.from_lng && opt.to_lat && opt.to_lng) {
        geo.push({ type: 'segment', coordinates: [[opt.from_lat, opt.from_lng], [opt.to_lat, opt.to_lng]], color, weight: 4, label: `${getModeLabel(opt.mode)}: ${opt.distance_km}km` })
      }
      if (opt.to_lat && opt.to_lng) {
        geo.push({ type: 'stop', coordinates: [[opt.to_lat, opt.to_lng]] as [number, number][], color, label: opt.to })
      }
    })
    if (hoveredOption) {
      const hp = hoveredOption.path
      if (hp && hp.length >= 2) {
        geo.push({ type: 'hover', coordinates: hp as [number, number][], color: '#fbbf24', weight: 6, label: `${getModeLabel(hoveredOption.mode)}: ${hoveredOption.distance_km}km` })
      } else if (hoveredOption.from_lat && hoveredOption.from_lng && hoveredOption.to_lat && hoveredOption.to_lng) {
        geo.push({ type: 'hover', coordinates: [[hoveredOption.from_lat, hoveredOption.from_lng], [hoveredOption.to_lat, hoveredOption.to_lng]], color: '#fbbf24', weight: 6, label: `${getModeLabel(hoveredOption.mode)}: ${hoveredOption.distance_km}km` })
      }
    }
    onGeometryChange(geo)
  }, [builtPath, hoveredOption, onGeometryChange])

  const totalFare = builtPath.reduce((sum, s) => sum + (s.opt.fare || 0), 0)
  const totalPerPerson = builtPath.reduce((sum, s) => sum + ((s.opt.per_person || 0)), 0)
  const totalDuration = builtPath.reduce((sum, s) => sum + (s.opt.duration_minutes || 0), 0)
  const totalDistance = builtPath.reduce((sum, s) => sum + (s.opt.distance_km || 0), 0)
  const isComplete = builtPath.length > 0 && chainState.selectedFinal !== null

  const optCardStyle = (opt: SegmentStepOption, isSelected?: boolean): React.CSSProperties => ({
    padding: '6px 8px',
    background: isSelected ? '#0f2d1a' : '#1a2332',
    border: `1px solid ${isSelected ? '#22c55e' : '#334155'}`,
    borderRadius: 6,
    color: '#cbd5e1',
    cursor: 'pointer',
    fontSize: 10,
    textAlign: 'left',
    width: '100%',
    borderLeft: `3px solid ${MODE_COLORS[opt.mode] || '#64748b'}`,
    display: 'flex',
    flexDirection: 'column',
    gap: 1,
  })

  const renderOptionDetail = (opt: any, idx: number) => {
    const routeNum = opt.route_number
    const busTimes = opt.bus_times
    const depOpt = opt.departure_time
    const arrOpt = opt.arrival_time
    const cap = opt.group_capacity
    const finalCount = opt.final_options?.length ?? 0
    const dwm = opt.dropoff_walk_min
    const dtd = opt.dropoff_to_dest_km
    return (
      <div key={idx}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12 }}>{opt.icon || getModeIcon(opt.mode)}</span>
          <span style={{ fontWeight: 600, fontSize: 10, color: '#e2e8f0' }}>{opt.label || getModeLabel(opt.mode)}</span>
          {routeNum && <span style={{ fontSize: 9, color: '#60a5fa', background: '#1e3a5f', padding: '1px 5px', borderRadius: 3, fontWeight: 700 }}>{routeNum}</span>}
          {depOpt && arrOpt && <span style={{ fontSize: 8, color: '#a855f7' }}>🕐 {depOpt}→{arrOpt}</span>}
        </div>
        <div style={{ fontSize: 8, color: '#64748b', marginTop: 1, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <span>{formatDuration(opt.duration_minutes)}</span>
          <span>{opt.distance_km?.toFixed(2)}km</span>
          <span style={{ color: '#fbbf24' }}>{formatRupees(opt.fare)} {opt.per_person ? `(${formatRupees(opt.per_person)}/pp)` : ''}</span>
          {cap && <span style={{ color: '#64748b' }}>👥{cap}</span>}
          {dwm != null && dwm > 0 && opt.transit_type && <span style={{ color: '#22c55e' }}>🚶+{dwm}min to {opt.to ? opt.to.slice(0,15) : 'dest'}</span>}
          {finalCount > 0 && <span style={{ color: '#22c55e' }}>🏁{finalCount} final opts</span>}
        </div>
        {routeNum && busTimes && busTimes.length > 0 && (
          <div style={{ fontSize: 7, color: '#f59e0b', marginTop: 1, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            ⏰ {busTimes.slice(0, 3).map((bt: any, bi: number) => (
              <span key={bi} style={{ background: '#1e3a5f', padding: '1px 3px', borderRadius: 2, color: '#fbbf24' }}>
                {bt.departure_time?.split(':').slice(0, 2).join(':')}
              </span>
            ))}
          </div>
        )}
        {dwm != null && opt.next_segment_index != null && (
          <div style={{ fontSize: 7, color: '#8b5cf6', marginTop: 1 }}>
            After {dwm}min walk from drop-off → more options available
          </div>
        )}
      </div>
    )
  }

  const renderColumn = (content: React.ReactNode, title: string, color: string, width?: number) => (
    <div style={{
      minWidth: width || 260, maxWidth: width || 320,
      background: '#131e2b', borderRadius: 8,
      border: `1px solid ${color}`, flexShrink: 0,
      display: 'flex', flexDirection: 'column', maxHeight: '100%',
    }}>
      <div style={{
        padding: '6px 10px', background: '#1a2332',
        borderRadius: '8px 8px 0 0',
        borderBottom: `1px solid ${color}`,
        fontSize: 10, fontWeight: 700, color: '#e2e8f0',
        display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0,
      }}>
        {title}
      </div>
      <div style={{ padding: '6px 6px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {content}
      </div>
    </div>
  )

  const renderContent = () => {
    if (loading && !data) {
      return <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 11 }}>⏳ Loading route options...</div>
    }
    if (!data) {
      return <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 11 }}>Loading...</div>
    }

    const cs = chainState
    const segLabel = data && data.total_segments > 1 ? ` (Seg ${cs.activeSegIdx + 1}/${data.total_segments})` : ''

    return (
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', overflowY: 'visible', paddingBottom: 4, alignItems: 'flex-start' }}>

        {/* COLUMN 0: DIRECT OPTIONS (from active segment) */}
        {directOptions.length > 0 && renderColumn(
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
              🏁 <span>Direct to {destName}</span>
            </div>
            {directOptions.map((opt, oi) => (
              <button key={oi}
                onClick={() => handlePickDirect(opt)}
                onMouseEnter={() => setHoveredOption(opt)}
                onMouseLeave={() => setHoveredOption(null)}
                style={{
                  ...optCardStyle(opt),
                  ...(cs.selectedFinal === opt ? { border: '1px solid #22c55e', background: '#0f2d1a' } : {}),
                }}
              >
                {renderOptionDetail(opt, oi)}
              </button>
            ))}
          </div>,
          `🚕 DIRECT${segLabel}`, '#22c55e', 240
        )}

        {/* COLUMN 1: NEARBY STOPS WITH REACH OPTIONS (from active segment's "from" location) */}
        <div style={{ display: 'flex', gap: 8 }}>
          {destinations.length > 0 && renderColumn(
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ fontSize: 9, fontWeight: 600, color: '#94a3b8', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                📍 From: <strong>{activeSegment?.from.name || sourceName}</strong>
              </div>
              {destinations.map((dest, di) => {
                const stopIcon = dest.stop.type === 'metro' ? '🚇' : dest.stop.type === 'railway' ? '🚆' : '🚏'
                const isSelected = cs.selectedDest?.stop.name === dest.stop.name
                const hasReach = dest.reach_options.length > 0
                return (
                  <div key={di} style={{
                    background: isSelected ? '#0a1a2e' : 'transparent',
                    border: `1px solid ${isSelected ? '#3b82f6' : 'transparent'}`,
                    borderRadius: 6, padding: '4px 6px',
                  }}>
                    <div style={{ fontSize: 9, fontWeight: 600, color: '#e2e8f0', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span>{stopIcon}</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{dest.stop.name}</span>
                      <span style={{ fontSize: 8, color: '#64748b' }}>{dest.stop.distance_km?.toFixed(2)}km</span>
                    </div>
                    {hasReach && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {dest.reach_options.map((opt, oi) => {
                          const reachLabel = opt.mode === 'walk' ? `🚶 Walk ${formatDuration(opt.duration_minutes)} to ${dest.stop.name}` : null
                          return (
                            <button key={oi}
                              onClick={() => handlePickReach(dest, opt)}
                              onMouseEnter={() => setHoveredOption(opt)}
                              onMouseLeave={() => setHoveredOption(null)}
                              style={optCardStyle(opt)}
                            >
                              {reachLabel ? (
                                <div style={{ fontSize: 10, color: '#22c55e', fontWeight: 600 }}>{reachLabel}</div>
                              ) : (
                                renderOptionDetail(opt, oi)
                              )}
                            </button>
                          )
                        })}
                      </div>
                    )}
                    {!hasReach && <div style={{ fontSize: 8, color: '#64748b', padding: '2px 0' }}>No reach options</div>}
                  </div>
                )
              })}
            </div>,
            `🚏 REACH A STOP${segLabel}`, '#3b82f6', 270
          )}

          {/* COLUMN 2: TRANSIT OPTIONS from selected stop */}
          {cs.selectedDest && (
            cs.selectedDest.transit_options.length > 0 ? renderColumn(
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ fontSize: 9, fontWeight: 600, color: '#60a5fa', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                  🚌 <span>From {cs.selectedDest.stop.name}</span>
                  <span style={{ fontSize: 8, color: '#64748b', marginLeft: 'auto' }}>{cs.selectedDest.transit_options.length} options</span>
                </div>
                {cs.selectedDest.transit_options.map((opt, oi) => {
                  const isSelected = cs.selectedTransit === opt
                  return (
                    <button key={oi}
                      onClick={() => handlePickTransit(opt)}
                      onMouseEnter={() => setHoveredOption(opt)}
                      onMouseLeave={() => setHoveredOption(null)}
                      style={{
                        ...optCardStyle(opt),
                        ...(isSelected ? { border: '1px solid #60a5fa', background: '#0a1a2e' } : {}),
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                        <span style={{ fontSize: 9, color: '#94a3b8' }}>📍{opt.from?.slice(0, 18)}</span>
                        <span style={{ fontSize: 8, color: '#64748b' }}>→</span>
                        <span style={{ fontSize: 9, color: '#e2e8f0' }}>{opt.to?.slice(0, 20)}</span>
                      </div>
                      {renderOptionDetail(opt, oi)}
                      {opt.next_segment_index != null && (
                        <div style={{ fontSize: 7, color: '#8b5cf6', marginTop: 2 }}>🔽 Transit continues → more options at {opt.to?.slice(0, 15)}</div>
                      )}
                      {opt.final_options && opt.final_options.length > 0 && !opt.next_segment_index && (
                        <div style={{ fontSize: 7, color: '#22c55e', marginTop: 2 }}>🏁 {opt.final_options.length} final mile options</div>
                      )}
                    </button>
                  )
                })}
              </div>,
              `🚌 TRANSIT: ${cs.selectedDest.stop.name}`, '#60a5fa', 280
            ) : (
              renderColumn(
                <div style={{ padding: 12, color: '#64748b', fontSize: 10, textAlign: 'center' }}>
                  No transit options found from this stop.
                  Try a different stop.
                </div>,
                `🚌 TRANSIT: ${cs.selectedDest.stop.name}`, '#60a5fa', 260
              )
            )
          )}

          {/* COLUMN 3: FINAL MILE */}
          {cs.selectedTransit && cs.selectedTransit.final_options && cs.selectedTransit.final_options.length > 0 && renderColumn(
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ fontSize: 9, fontWeight: 600, color: '#22c55e', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                🏁 <span>Final to {destName} from {cs.selectedTransit.to}</span>
                <span style={{ fontSize: 8, color: '#64748b', marginLeft: 'auto' }}>{cs.selectedTransit.final_options.length} options</span>
              </div>
              {cs.selectedTransit.final_options.map((opt, oi) => {
                const isSelected = cs.selectedFinal === opt
                return (
                  <button key={oi}
                    onClick={() => handlePickFinal(opt)}
                    onMouseEnter={() => setHoveredOption(opt)}
                    onMouseLeave={() => setHoveredOption(null)}
                    style={{
                      ...optCardStyle(opt),
                      ...(isSelected ? { border: '1px solid #22c55e', background: '#0f2d1a' } : {}),
                    }}
                  >
                    {renderOptionDetail(opt, oi)}
                  </button>
                )
              })}
            </div>,
            '🏁 FINAL MILE', '#22c55e', 260
          )}
        </div>

        {/* Empty state */}
        {directOptions.length === 0 && destinations.length === 0 && (
          <div style={{ padding: 20, color: '#64748b', fontSize: 11 }}>No route options available</div>
        )}
      </div>
    )
  }

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      maxHeight: '60vh', background: '#0f172a',
      borderTop: '2px solid #3b82f6', borderRadius: '16px 16px 0 0',
      zIndex: 9999, display: 'flex', flexDirection: 'column',
      boxShadow: '0 -8px 32px rgba(0,0,0,0.5)',
    }}>
      {/* HEADER */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 12px', borderBottom: '1px solid #1e293b',
        borderRadius: '16px 16px 0 0', background: '#1a2332', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontWeight: 700, fontSize: 11, color: '#e2e8f0' }}>🗺️ Route Finder</span>
          <span style={{ fontSize: 9, color: '#64748b' }}>📍 {sourceName} → 🏁 {destName}</span>
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {data && (
            <span style={{ fontSize: 8, color: '#64748b' }}>{builtPath.length}/{data.total_segments} segments</span>
          )}
          {builtPath.length > 0 && (
            <button onClick={handleGoBack} style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, color: '#94a3b8', cursor: 'pointer', fontSize: 9, padding: '2px 6px' }}>↩️ Back</button>
          )}
          <button onClick={handleReset} style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, color: '#94a3b8', cursor: 'pointer', fontSize: 9, padding: '2px 6px' }}>🔄 Reset</button>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: 16, cursor: 'pointer', padding: '0 4px', lineHeight: 1 }}>✕</button>
        </div>
      </div>

      {/* TIMELINE */}
      {builtPath.length > 0 && (
        <div style={{ padding: '4px 12px', borderBottom: '1px solid #1e293b', overflowX: 'auto', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: 9, whiteSpace: 'nowrap' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 30 }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, border: '2px solid #60a5fa' }}>📍</div>
              <span style={{ color: '#e2e8f0', fontSize: 7, marginTop: 1, maxWidth: 40, overflow: 'hidden', textOverflow: 'ellipsis' }}>{sourceName.slice(0, 6)}</span>
            </div>
            {builtPath.map((entry, idx) => {
              const color = idx < SEGMENT_COLORS.length ? SEGMENT_COLORS[idx] : '#94a3b8'
              return (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <div style={{ width: 12, height: 2, background: color, borderRadius: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 30 }}>
                    <div style={{ width: 18, height: 18, borderRadius: '50%', background: '#1a2332', border: `2px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>
                      {entry.opt.icon || getModeIcon(entry.opt.mode)}
                    </div>
                    <span style={{ color: '#cbd5e1', fontSize: 7, marginTop: 1, maxWidth: 40, overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.opt.to.length > 6 ? entry.opt.to.slice(0, 6) + '..' : entry.opt.to}</span>
                    <span style={{ color: '#fbbf24', fontSize: 7 }}>{formatRupees(entry.opt.fare)}</span>
                  </div>
                </div>
              )
            })}
            <div style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <div style={{ width: 12, height: 2, background: isComplete ? '#22c55e' : '#334155', borderRadius: 1 }} />
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 30 }}>
                <div style={{ width: 20, height: 20, borderRadius: '50%', background: isComplete ? '#0f2d1a' : '#1e293b', border: isComplete ? '2px solid #22c55e' : '2px dashed #334155', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>🏁</div>
                <span style={{ color: isComplete ? '#22c55e' : '#64748b', fontSize: 7, marginTop: 1, fontWeight: isComplete ? 700 : 400, maxWidth: 40, overflow: 'hidden', textOverflow: 'ellipsis' }}>{destName.length > 6 ? destName.slice(0, 6) + '..' : destName}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUMMARY BAR */}
      {builtPath.length > 0 && (
        <div style={{
          display: 'flex', gap: 8, padding: '3px 12px', background: '#1a2332',
          borderBottom: '1px solid #1e293b', fontSize: 8, color: '#94a3b8', flexShrink: 0, alignItems: 'center',
        }}>
          <span>💰 <strong style={{ color: '#fbbf24' }}>{formatRupees(totalFare)}</strong>{totalPerPerson > 0 && <span style={{ color: '#64748b', fontSize: 7 }}> ({formatRupees(totalPerPerson)}/pp)</span>}</span>
          <span>⏱️ <strong style={{ color: '#e2e8f0' }}>{formatDuration(totalDuration)}</strong></span>
          <span>📏 <strong style={{ color: '#e2e8f0' }}>{totalDistance.toFixed(1)}km</strong></span>
          <span style={{ fontSize: 7, color: '#64748b' }}>{builtPath.length} step{builtPath.length !== 1 ? 's' : ''}</span>
          {budget && budget > 0 && (
            <div style={{ flex: 1, maxWidth: 100 }}>
              <div style={{ height: 3, background: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.min(100, (totalFare / budget) * 100)}%`, background: totalFare > budget ? '#ef4444' : '#22c55e', borderRadius: 3 }} />
              </div>
            </div>
          )}
          {isComplete && (
            <button onClick={onStartJourney} style={{
              marginLeft: 'auto', padding: '3px 10px',
              background: trackingActive ? '#0f2d1a' : '#22c55e',
              border: `1px solid ${trackingActive ? '#22c55e' : '#16a34a'}`,
              borderRadius: 5, color: trackingActive ? '#22c55e' : '#fff',
              cursor: 'pointer', fontSize: 9, fontWeight: 700,
            }}>
              {trackingActive ? '🟢 Tracking' : '▶ Start Journey'}
            </button>
          )}
          {isComplete && !trackingActive && <span style={{ color: '#22c55e', fontSize: 9, fontWeight: 700 }}>✅ Route Planned!</span>}
        </div>
      )}

      {/* MAIN CONTENT - SCROLLABLE COLUMNS */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', padding: '6px 10px' }}>
        {renderContent()}

        {/* FULL PATH SUMMARY when complete */}
        {isComplete && builtPath.length > 0 && (
          <div style={{ marginTop: 8, padding: 8, background: '#1a2332', borderRadius: 8, border: '1px solid #22c55e' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#22c55e', marginBottom: 6 }}>✅ Full Journey Summary</div>
            {builtPath.map((entry, idx) => {
              const opt = entry.opt
              const color = idx < SEGMENT_COLORS.length ? SEGMENT_COLORS[idx] : '#94a3b8'
              return (
                <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, padding: '4px 6px', marginBottom: 3, background: '#0f172a', borderRadius: 4, borderLeft: `3px solid ${color}` }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color, minWidth: 16 }}>S{idx + 1}</div>
                  <div style={{ fontSize: 11, marginTop: -1 }}>{opt.icon || getModeIcon(opt.mode)}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10, color: '#e2e8f0', fontWeight: 500 }}>{opt.from} → {opt.to}</div>
                    <div style={{ fontSize: 8, color: '#64748b', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <span>{opt.label || getModeLabel(opt.mode)}</span>
                      <span>⏱️ {formatDuration(opt.duration_minutes)}</span>
                      <span>📏 {opt.distance_km?.toFixed(2)}km</span>
                      <span>💰 {formatRupees(opt.fare)}</span>
                      {(opt as any).route_number && <span style={{ color: '#60a5fa' }}>🚌 {(opt as any).route_number}</span>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* CUSTOM STOP */}
        <div style={{ display: 'flex', gap: 6, marginTop: 8, marginBottom: 4, flexShrink: 0 }}>
          {!showCustomInput ? (
            <button onClick={() => setShowCustomInput(true)} style={{
              flex: 1, padding: '6px', background: '#1e293b',
              border: '1px dashed #475569', borderRadius: 5, color: '#94a3b8',
              cursor: 'pointer', fontSize: 10,
            }}>
              ➕ Add Custom Stop
            </button>
          ) : (
            <div style={{ flex: 1, position: 'relative' }}>
              <input type="text" placeholder="Search a place to stop at..." value={customInput}
                onChange={(e) => handleCustomInput(e.target.value)}
                style={{ width: '100%', padding: '6px 8px', fontSize: 11, border: '1px solid #475569', borderRadius: 5, background: '#1e293b', color: '#e2e8f0', outline: 'none' }} />
              {customLoading && <div style={{ padding: '3px 8px', fontSize: 9, color: '#64748b' }}>Searching...</div>}
              {!customLoading && customSuggestions.length > 0 && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100, background: '#1e293b', border: '1px solid #475569', borderRadius: 5, marginTop: 2, maxHeight: 140, overflowY: 'auto' }}>
                  {customSuggestions.map((place, i) => (
                    <div key={i} onClick={() => handleAddCustomWaypoint(place)}
                      style={{ padding: '6px 8px', cursor: 'pointer', fontSize: 11, color: '#cbd5e1', borderBottom: '1px solid #334155' }}>
                      {getModeIcon(place.place_type)} {place.name}
                      <span style={{ fontSize: 9, color: '#64748b', marginLeft: 4 }}>{place.address?.slice(0, 25)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
