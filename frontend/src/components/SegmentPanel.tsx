import { useState, useCallback, useRef, useEffect } from 'react'
import type { SegmentStepData, SegmentStepOption, MapRouteGeometry, PlaceResult } from '../types'
import { getSegmentStep, searchPlaces } from '../services/api'
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
      if (opt.path && opt.path.length >= 2) {
        geo.push({ type: 'segment', coordinates: opt.path as [number, number][], color, weight: 4, label: `${getModeLabel(opt.mode)}: ${opt.distance_km}km` })
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
        geo.push({ type: 'hover', coordinates: [[hoveredOption.from_lat, hoveredOption.from_lng], [hoveredOption.to_lat, hoveredOption.to_lng]], color: '#fbbf24', weight: 6 })
      }
    }
    onGeometryChange(geo)
  }, [builtPath, hoveredOption, columns, onGeometryChange])

  const optCardStyle = (opt: SegmentStepOption, isSelected?: boolean): React.CSSProperties => ({
    padding: '8px 10px',
    background: isSelected ? '#0f2d1a' : (opt.mode === 'walk' ? '#0f2d1a' : '#1a2332'),
    border: `1px solid ${isSelected ? '#22c55e' : MODE_COLORS[opt.mode] || '#334155'}`,
    borderRadius: 8,
    color: '#cbd5e1',
    cursor: 'pointer',
    fontSize: 10,
    textAlign: 'left',
    width: '100%',
    transition: 'all 0.15s',
    borderLeft: `4px solid ${MODE_COLORS[opt.mode] || '#64748b'}`,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
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

        {/* Route info */}
        <div style={{ fontSize: 9, color: '#64748b', marginTop: 1, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {dep && arr && <span style={{ color: '#a855f7' }}>🕐 {dep}→{arr}</span>}
          <span>{formatDuration(opt.duration_minutes)}</span>
          <span>{opt.distance_km.toFixed(2)}km</span>
          <span style={{ color: '#fbbf24' }}>{formatRupees(opt.fare)} {opt.per_person ? `(${formatRupees(opt.per_person)}/pp)` : ''}</span>
          {cap && <span style={{ color: '#64748b' }}>👥 up to {cap}</span>}
        </div>

        {/* Bus timings - individual route times */}
        {busTimes && busTimes.length > 0 && (
          <div style={{ fontSize: 8, color: '#f59e0b', marginTop: 2, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            ⏰ {busTimes.slice(0, 4).map((bt: any, bi: number) => (
              <span key={bi} style={{ background: '#1e3a5f', padding: '1px 4px', borderRadius: 3, color: '#fbbf24' }}>
                {bt.departure_time}
              </span>
            ))}
          </div>
        )}

        {/* No bus times available message */}
        {opt.mode.startsWith('bus_') && (!busTimes || busTimes.length === 0) && (
          <div style={{ fontSize: 8, color: '#64748b', marginTop: 2, fontStyle: 'italic' }}>
            Schedule data not available
          </div>
        )}

        {/* Sub legs */}
        {subLegs && subLegs.length > 0 && (
          <div style={{ fontSize: 8, color: '#94a3b8', marginTop: 2 }}>
            {subLegs.map((sl: any, si: number) => (
              <span key={si}>
                {getModeIcon(sl.mode)} {sl.from}→{sl.to}
                {sl.fare ? ` ₹${sl.fare}` : ''}
                {si < subLegs.length - 1 ? ' + ' : ''}
              </span>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      maxHeight: '65vh', background: '#0f172a',
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
          <span style={{ fontWeight: 700, fontSize: 13, color: '#e2e8f0' }}>🔧 Segment Builder</span>
          <span style={{ fontSize: 10, color: '#64748b' }}>📍 {sourceName} → 🏁 {destName}</span>
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {data && (
            <span style={{ fontSize: 8, color: '#64748b' }}>{builtPath.length}/{data.total_segments} segments</span>
          )}
          {builtPath.length > 0 && (
            <button onClick={handleStartBuilding} style={{
              background: '#1e293b', border: '1px solid #334155',
              borderRadius: 4, color: '#94a3b8', cursor: 'pointer',
              fontSize: 10, padding: '2px 8px',
            }}>🔄 Reset</button>
          )}
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#94a3b8',
            fontSize: 18, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
          }}>✕</button>
        </div>
      </div>

      {/* === TIMELINE === */}
      <div style={{
        padding: '6px 14px', borderBottom: '1px solid #1e293b',
        overflowX: 'auto', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: 10, whiteSpace: 'nowrap', paddingBottom: 2 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40, cursor: builtPath.length > 0 ? 'pointer' : 'default' }}
            onClick={() => builtPath.length > 0 && handleGoBack(-1)}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, border: '2px solid #60a5fa' }}>📍</div>
            <span style={{ color: '#e2e8f0', fontSize: 8, marginTop: 1, maxWidth: 50, overflow: 'hidden', textOverflow: 'ellipsis' }}>{sourceName.slice(0, 8)}</span>
          </div>
          {builtPath.map((opt, idx) => {
            const color = idx < SEGMENT_COLORS.length ? SEGMENT_COLORS[idx] : '#94a3b8'
            const isLast = idx === builtPath.length - 1
            return (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <div style={{ width: 16, height: 3, background: color, borderRadius: 2 }} />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40, cursor: 'pointer' }}
                  onClick={() => isLast ? null : handleGoBack(idx)}>
                  <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#1a2332', border: `2px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, position: 'relative' }}>
                    {opt.icon || getModeIcon(opt.mode)}
                    {!isLast && <span style={{ position: 'absolute', top: -6, right: -6, fontSize: 7, color: '#94a3b8' }}>✕</span>}
                  </div>
                  <span style={{ color: '#cbd5e1', fontSize: 8, marginTop: 1, maxWidth: 50, overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: isLast ? 600 : 400 }}>{opt.to.length > 8 ? opt.to.slice(0, 8) + '..' : opt.to}</span>
                  <span style={{ color: '#fbbf24', fontSize: 8, fontWeight: 500 }}>{formatRupees(opt.fare)}</span>
                </div>
              </div>
            )
          })}
          <div style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <div style={{ width: 16, height: 3, background: isComplete ? '#22c55e' : '#334155', borderRadius: 2 }} />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40 }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: isComplete ? '#0f2d1a' : '#1e293b', border: isComplete ? '2px solid #22c55e' : '2px dashed #334155', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>🏁</div>
              <span style={{ color: isComplete ? '#22c55e' : '#64748b', fontSize: 8, marginTop: 1, fontWeight: isComplete ? 700 : 400, maxWidth: 50, overflow: 'hidden', textOverflow: 'ellipsis' }}>{destName.length > 8 ? destName.slice(0, 8) + '..' : destName}</span>
            </div>
          </div>
        </div>
      )}

      {/* SUMMARY BAR */}
      {builtPath.length > 0 && (
        <div style={{
          display: 'flex', gap: 10, padding: '4px 14px', background: '#1a2332',
          borderBottom: '1px solid #1e293b', fontSize: 9, color: '#94a3b8', flexShrink: 0,
          alignItems: 'center',
        }}>
          <span>💰 <strong style={{ color: '#fbbf24' }}>{formatRupees(totalFare)}</strong>
            {totalPerPerson > 0 && <span style={{ color: '#64748b', fontSize: 8 }}> ({formatRupees(totalPerPerson)}/pp)</span>}
          </span>
          <span>⏱️ <strong style={{ color: '#e2e8f0' }}>{formatDuration(totalDuration)}</strong></span>
          <span>📏 <strong style={{ color: '#e2e8f0' }}>{totalDistance.toFixed(1)}km</strong></span>
          <span style={{ fontSize: 7, color: '#64748b' }}>{builtPath.length} step{builtPath.length !== 1 ? 's' : ''}</span>
          {budget && budget > 0 && (
            <div style={{ flex: 1, maxWidth: 120, marginLeft: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 7, marginBottom: 1 }}>
                <span style={{ color: totalFare > budget ? '#ef4444' : '#94a3b8' }}>
                  {Math.round((totalFare / budget) * 100)}%
                </span>
                <span style={{ color: '#64748b' }}>of ₹{budget}</span>
              </div>
              <div style={{ height: 4, background: '#1e293b', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${Math.min(100, (totalFare / budget) * 100)}%`,
                  background: totalFare > budget ? '#ef4444' : '#22c55e',
                  borderRadius: 4, transition: 'width 0.3s',
                }} />
              </div>
            </div>
          )}
          {isComplete && <span style={{ color: '#22c55e', marginLeft: 'auto', fontWeight: 700, fontSize: 10 }}>✅ Done!</span>}
        </div>
      )}

      {/* === SCROLLABLE COLUMNS === */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', padding: '8px 14px' }}>
        {segmentLoading && (
          <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 12 }}>⏳ Loading options...</div>
        )}

        {!segmentLoading && columns.length === 0 && builtPath.length === 0 && (
          <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 12 }}>Loading initial options...</div>
        )}

        {/* Columns layout */}
        {columns.length > 0 && !segmentLoading && (
          <div style={{
            display: 'flex', gap: 10,
            overflowX: 'auto', overflowY: 'visible',
            paddingBottom: 4,
          }}>
            {columns.map((col, colIdx) => {
              const isNext = colIdx > 0 && !columns[colIdx - 1].selectedOption
              if (isNext) return null

              return (
                <div key={colIdx} style={{
                  minWidth: 260, maxWidth: 320,
                  background: '#131e2b',
                  borderRadius: 10,
                  border: `1px solid ${col.selectedOption ? '#22c55e' : '#334155'}`,
                  flexShrink: 0,
                  display: 'flex', flexDirection: 'column',
                  maxHeight: '100%',
                }}>
                  {/* Column header */}
                  <div style={{
                    padding: '8px 10px',
                    background: col.selectedOption ? '#0f2d1a' : '#1a2332',
                    borderRadius: '10px 10px 0 0',
                    borderBottom: `1px solid ${col.selectedOption ? '#22c55e' : '#1e293b'}`,
                    fontSize: 10, fontWeight: 700, color: col.selectedOption ? '#22c55e' : '#e2e8f0',
                    display: 'flex', alignItems: 'center', gap: 4,
                    flexShrink: 0,
                  }}>
                    <span>{col.selectedOption ? '✅' : '⬜'}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{col.label}</span>
                    {col.fromName && (
                      <span style={{ fontSize: 8, color: '#64748b', marginLeft: 'auto' }}>
                        📍{col.fromName.slice(0, 12)}
                      </span>
                    )}
                  </div>

                  {/* Options list */}
                  <div style={{
                    padding: '6px 8px',
                    overflowY: 'auto',
                    flex: 1,
                    display: 'flex', flexDirection: 'column', gap: 4,
                  }}>
                    {col.selectedOption ? (
                      <div style={optCardStyle(col.selectedOption, true)}>
                        {renderOptionDetail(col.selectedOption, 0)}
                      </div>
                    ) : (
                      col.options.length > 0 ? (
                        col.options.map((opt, oi) => (
                          <button key={oi}
                            onClick={() => {
                              if (col.type === 'direct') handlePickDirect(opt)
                              else if (col.type === 'reach') handlePickReach(col.stageIdx, opt, segmentStep!)
                              else if (col.type === 'from') handlePickFrom(opt, colIdx)
                            }}
                            onMouseEnter={() => setHoveredOption(opt)}
                            onMouseLeave={() => setHoveredOption(null)}
                            style={optCardStyle(opt)}
                          >
                            {renderOptionDetail(opt, oi)}
                          </button>
                        ))
                      ) : (
                        <div style={{ fontSize: 10, color: '#64748b', padding: 8, textAlign: 'center' }}>
                          No options available
                        </div>
                      )
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* === BUILT PATH FULL DISPLAY === */}
        {builtPath.length > 0 && isComplete && (
          <div style={{ marginTop: 8, padding: 10, background: '#1a2332', borderRadius: 8, border: '1px solid #22c55e' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#22c55e', marginBottom: 8 }}>✅ Full Journey Path</div>
            {builtPath.map((opt, idx) => {
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
                      {(opt as any).route_number && (
                        <span style={{ color: '#60a5fa', fontWeight: 600 }}>🚌 {(opt as any).route_number}</span>
                      )}
                      {(opt as any).route_numbers && !(opt as any).route_number && (
                        <span style={{ color: '#60a5fa' }}>🚌 [{(opt as any).route_numbers.join(', ')}]</span>
                      )}
                      {(opt as any).train_number && (
                        <span style={{ color: '#a855f7' }}>🚆 #{(opt as any).train_number}</span>
                      )}
                      {(opt as any).departure_time && (
                        <span style={{ color: '#f59e0b' }}>🕐 {(opt as any).departure_time}</span>
                      )}
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
                style={{
                  width: '100%', padding: '8px 10px', fontSize: 12, border: '1px solid #475569',
                  borderRadius: 6, background: '#1e293b', color: '#e2e8f0', outline: 'none',
                }} />
              {customLoading && <div style={{ padding: '4px 10px', fontSize: 10, color: '#64748b' }}>Searching...</div>}
              {!customLoading && customSuggestions.length > 0 && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100, background: '#1e293b', border: '1px solid #475569', borderRadius: 5, marginTop: 2, maxHeight: 140, overflowY: 'auto' }}>
                  {customSuggestions.map((place, i) => (
                    <div key={i} onClick={() => handleAddCustomWaypoint(place)}
                      style={{ padding: '8px 10px', cursor: 'pointer', fontSize: 12, color: '#cbd5e1', borderBottom: '1px solid #334155' }}>
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
