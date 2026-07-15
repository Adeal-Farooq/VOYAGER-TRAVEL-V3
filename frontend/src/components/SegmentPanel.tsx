import { useState, useCallback, useRef, useEffect } from 'react'
import type { CompleteJourneySegment, CompleteJourneyDestOption, SegmentStepOption, MapRouteGeometry, PlaceResult } from '../types'
import { getCompleteJourney, searchPlaces } from '../services/api'
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
}

interface SelectionItem {
  dest: CompleteJourneyDestOption
  transport: SegmentStepOption
  segIdx: number
}

export default function SegmentPanel({
  sourceLocation, destLocation, sourceName, destName,
  groupSize, budget, onClose, onGeometryChange,
}: SegmentPanelProps) {
  const [segments, setSegments] = useState<CompleteJourneySegment[]>([])
  const [loading, setLoading] = useState(true)
  const [selections, setSelections] = useState<SelectionItem[]>([])
  const [hoveredOption, setHoveredOption] = useState<SegmentStepOption | null>(null)
  const [customInput, setCustomInput] = useState('')
  const [customSuggestions, setCustomSuggestions] = useState<PlaceResult[]>([])
  const [customLoading, setCustomLoading] = useState(false)
  const [showCustomInput, setShowCustomInput] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getCompleteJourney(
      sourceLocation[0], sourceLocation[1], sourceName,
      destLocation[0], destLocation[1], destName,
      groupSize, budget
    ).then(res => {
      if (!cancelled && res.journey?.segments) {
        setSegments(res.journey.segments)
      }
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [sourceLocation, destLocation, sourceName, destName, groupSize, budget])

  const rootSegment = segments[0]
  const activeSegments: { seg: CompleteJourneyDestOption[]; level: number; parentIdx: number | null }[] = []

  // Build active segments based on selections
  if (rootSegment) {
    activeSegments.push({
      seg: rootSegment.destinations,
      level: 0,
      parentIdx: null,
    })
  }

  // Follow the chain of selections to determine which levels are visible
  let currentDestinations: CompleteJourneyDestOption[] = rootSegment?.destinations || []
  for (let i = 0; i < selections.length; i++) {
    const sel = selections[i]
    if (sel.dest?.next?.destinations?.length) {
      activeSegments.push({
        seg: sel.dest.next.destinations,
        level: i + 1,
        parentIdx: i,
      })
      currentDestinations = sel.dest.next.destinations
    } else {
      break
    }
  }

  const handleSelect = useCallback((dest: CompleteJourneyDestOption, transport: SegmentStepOption, level: number) => {
    setSelections(prev => {
      const existing = prev.findIndex(s => s.segIdx === level)
      const newSel: SelectionItem = { dest, transport, segIdx: level }
      if (existing >= 0) {
        const updated = prev.slice(0, existing + 1)
        updated[existing] = newSel
        return updated
      }
      return [...prev, newSel]
    })
  }, [])

  const handleReset = useCallback(() => {
    setSelections([])
    setHoveredOption(null)
  }, [])

  const builtPath: SegmentStepOption[] = selections.map(s => s.transport)
  const totalFare = builtPath.reduce((s, o) => s + (o.fare || 0), 0)
  const totalDuration = builtPath.reduce((s, o) => s + (o.duration_minutes || 0), 0)
  const totalDistance = builtPath.reduce((s, o) => s + (o.distance_km || 0), 0)
  const isComplete = selections.length >= activeSegments.length && selections.length > 0

  // Map geometry
  useEffect(() => {
    const geo: MapRouteGeometry[] = []
    builtPath.forEach((opt, idx) => {
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
    // Show all reachable stops
    activeSegments.forEach((as, si) => {
      as.seg.forEach((dest, di) => {
        const isPicked = selections.some(s => s.dest === dest && s.segIdx === as.level)
        if (!isPicked && dest.transport_options.length > 0) {
          const t = dest.transport_options[0]
          if (t.to_lat && t.to_lng) {
            geo.push({ type: 'stop', coordinates: [[t.to_lat, t.to_lng]] as [number, number][], color: '#3b82f6', label: `🚏 ${dest.to.name}` })
          }
        }
      })
    })
    onGeometryChange(geo)
  }, [builtPath, hoveredOption, activeSegments, selections, onGeometryChange])

  const renderTransportOption = (opt: SegmentStepOption, idx: number, compact?: boolean) => {
    const rn = (opt as any).route_numbers
    const routeNum = (opt as any).route_number
    const busTimes = (opt as any).bus_times
    const subLegs = (opt as any).sub_legs
    const tn = (opt as any).train_number
    const dep = (opt as any).departure_time || (opt as any).departure
    const arr = (opt as any).arrival_time || (opt as any).arrival
    const cap = (opt as any).group_capacity

    return (
      <div key={idx}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <span style={{ fontSize: compact ? 11 : 13 }}>{opt.icon || getModeIcon(opt.mode)}</span>
          <span style={{ fontWeight: 600, fontSize: compact ? 9 : 11, color: '#e2e8f0' }}>{opt.label || getModeLabel(opt.mode)}</span>
          {routeNum && (
            <span style={{ fontSize: compact ? 8 : 10, color: '#60a5fa', background: '#1e3a5f', padding: '1px 5px', borderRadius: 4, fontWeight: 700 }}>
              {routeNum}
            </span>
          )}
          {!routeNum && rn?.length > 0 && (
            <span style={{ fontSize: 7, color: '#60a5fa', background: '#1e3a5f', padding: '1px 3px', borderRadius: 3 }}>
              {rn.slice(0, 2).join(', ')}
            </span>
          )}
          {tn && <span style={{ fontSize: compact ? 8 : 9, color: '#a855f7', fontWeight: 600 }}>#{tn}</span>}
        </div>
        <div style={{ fontSize: compact ? 8 : 9, color: '#64748b', marginTop: 1, display: 'flex', gap: compact ? 3 : 6, flexWrap: 'wrap' }}>
          {dep && arr && <span style={{ color: '#a855f7' }}>🕐 {dep}→{arr}</span>}
          <span>{formatDuration(opt.duration_minutes)}</span>
          <span>{opt.distance_km.toFixed(2)}km</span>
          <span style={{ color: '#fbbf24' }}>{formatRupees(opt.fare)}</span>
          {cap && <span style={{ color: '#64748b' }}>👥{cap}</span>}
        </div>
        {busTimes?.length > 0 && (
          <div style={{ fontSize: 7, color: '#f59e0b', marginTop: 1, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            ⏰ {busTimes.slice(0, 4).map((bt: any, bi: number) => (
              <span key={bi} style={{ background: '#1e3a5f', padding: '1px 3px', borderRadius: 2, color: '#fbbf24' }}>
                {bt.departure_time}
              </span>
            ))}
          </div>
        )}
        {opt.mode.startsWith('bus_') && (!busTimes || busTimes.length === 0) && (
          <div style={{ fontSize: 7, color: '#64748b', fontStyle: 'italic' }}>
            No schedule
          </div>
        )}
        {subLegs?.length > 0 && (
          <div style={{ fontSize: 7, color: '#94a3b8', marginTop: 1 }}>
            {subLegs.map((sl: any, si: number) => (
              <span key={si}>{getModeIcon(sl.mode)} {sl.from}→{sl.to}{sl.fare ? ` ₹${sl.fare}` : ''}{si < subLegs.length - 1 ? ' + ' : ''}</span>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      maxHeight: '70vh', background: '#0f172a',
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
          <span style={{ fontWeight: 700, fontSize: 13, color: '#e2e8f0' }}>🔧 All Segments</span>
          <span style={{ fontSize: 10, color: '#64748b' }}>📍 {sourceName} → 🏁 {destName}</span>
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {data && (
            <span style={{ fontSize: 8, color: '#64748b' }}>{builtPath.length}/{data.total_segments} segments</span>
          )}
          {builtPath.length > 0 && (
            <button onClick={handleReset} style={{
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

      {/* TIMELINE */}
      <div style={{
        padding: '6px 14px', borderBottom: '1px solid #1e293b',
        overflowX: 'auto', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: 10, whiteSpace: 'nowrap', paddingBottom: 2 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40 }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, border: '2px solid #60a5fa' }}>📍</div>
            <span style={{ color: '#e2e8f0', fontSize: 8, marginTop: 1, maxWidth: 50, overflow: 'hidden', textOverflow: 'ellipsis' }}>{sourceName.slice(0, 8)}</span>
          </div>
          {builtPath.map((opt, idx) => {
            const color = idx < SEGMENT_COLORS.length ? SEGMENT_COLORS[idx] : '#94a3b8'
            return (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <div style={{ width: 16, height: 3, background: color, borderRadius: 2 }} />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40 }}>
                  <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#1a2332', border: `2px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>
                    {opt.icon || getModeIcon(opt.mode)}
                  </div>
                  <span style={{ color: '#cbd5e1', fontSize: 8, marginTop: 1, maxWidth: 50, overflow: 'hidden', textOverflow: 'ellipsis' }}>{opt.to.length > 8 ? opt.to.slice(0, 8) + '..' : opt.to}</span>
                  <span style={{ color: '#fbbf24', fontSize: 8, fontWeight: 500 }}>{formatRupees(opt.fare)}</span>
                </div>
              </div>
            )
          })}
          <div style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <div style={{ width: 16, height: 3, background: isComplete ? '#22c55e' : '#334155', borderRadius: 2 }} />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40 }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: isComplete ? '#0f2d1a' : '#1e293b', border: isComplete ? '2px solid #22c55e' : '2px dashed #334155', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>🏁</div>
              <span style={{ color: isComplete ? '#22c55e' : '#64748b', fontSize: 8, marginTop: 1, maxWidth: 50, overflow: 'hidden', textOverflow: 'ellipsis' }}>{destName.length > 8 ? destName.slice(0, 8) + '..' : destName}</span>
            </div>
          </div>
        </div>
      )}

      {/* SUMMARY BAR */}
      {builtPath.length > 0 && (
        <div style={{
          display: 'flex', gap: 10, padding: '4px 14px', background: '#1a2332',
          borderBottom: '1px solid #1e293b', fontSize: 9, color: '#94a3b8', flexShrink: 0, alignItems: 'center',
        }}>
          <span>💰 <strong style={{ color: '#fbbf24' }}>{formatRupees(totalFare)}</strong></span>
          <span>⏱️ <strong style={{ color: '#e2e8f0' }}>{formatDuration(totalDuration)}</strong></span>
          <span>📏 <strong style={{ color: '#e2e8f0' }}>{totalDistance.toFixed(1)}km</strong></span>
          <span style={{ fontSize: 7, color: '#64748b' }}>{builtPath.length} step{builtPath.length !== 1 ? 's' : ''}</span>
          {budget && budget > 0 && (
            <div style={{ flex: 1, maxWidth: 120, marginLeft: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 7, marginBottom: 1 }}>
                <span style={{ color: totalFare > budget ? '#ef4444' : '#94a3b8' }}>{Math.round((totalFare / budget) * 100)}%</span>
                <span style={{ color: '#64748b' }}>of ₹{budget}</span>
              </div>
              <div style={{ height: 4, background: '#1e293b', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.min(100, (totalFare / budget) * 100)}%`, background: totalFare > budget ? '#ef4444' : '#22c55e', borderRadius: 4, transition: 'width 0.3s' }} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* SEGMENTS */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', padding: '8px 14px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 12 }}>⏳ Building journey tree...</div>
        )}

        {!loading && activeSegments.length === 0 && (
          <div style={{ textAlign: 'center', padding: 20, color: '#64748b', fontSize: 12 }}>No route options available</div>
        )}

        {!loading && activeSegments.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {activeSegments.map((as, lvl) => {
              const segColor = SEGMENT_COLORS[lvl % SEGMENT_COLORS.length]
              const selectionAtLevel = selections.find(s => s.segIdx === as.level)
              const isModeChoice = as.seg.some(d => d.to.type === 'mode_choice')

              return (
                <div key={lvl} style={{
                  background: '#131e2b', borderRadius: 10,
                  border: `1px solid ${selectionAtLevel ? '#22c55e' : segColor}`,
                  overflow: 'hidden',
                }}>
                  {!isModeChoice && (
                    <div style={{
                      padding: '6px 10px', background: '#1a2332',
                      borderBottom: '1px solid #1e293b',
                      fontSize: 11, fontWeight: 700, color: selectionAtLevel ? '#22c55e' : segColor,
                      display: 'flex', alignItems: 'center', gap: 4,
                    }}>
                      <span>✦ S{lvl + 1}</span>
                      <span style={{ fontSize: 9, color: '#64748b', fontWeight: 400, marginLeft: 4 }}>
                        {as.level === 0 ? sourceName : (selections[lvl - 1]?.dest.to.name || '')} → {destName}
                      </span>
                      {selectionAtLevel && <span style={{ marginLeft: 'auto', color: '#22c55e', fontSize: 9 }}>✅ {selectionAtLevel.transport.mode}</span>}
                    </div>
                  )}

                  {as.seg.length === 0 && (
                    <div style={{ padding: 12, fontSize: 10, color: '#64748b', textAlign: 'center' }}>
                      No onward options available from this stop
                    </div>
                  )}

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: isModeChoice ? 8 : 6 }}>
                    {(() => {
                      if (isModeChoice) {
                        // Show mode selection cards (Bus, Ride)
                        const modeConfig: Record<string, { icon: string; label: string; color: string }> = {
                          Bus: { icon: '🚌', label: 'Bus', color: '#3b82f6' },
                          'Ride (Cab/Auto/Bike)': { icon: '🚗', label: 'Ride', color: '#f97316' },
                        }
                        return as.seg.map((dest, di) => {
                          const mc = modeConfig[dest.to.name] || { icon: '⚡', label: dest.to.name, color: '#64748b' }
                          const isPicked = selectionAtLevel?.dest === dest
                          return (
                            <button key={di} onClick={() => {
                              if (dest.next?.destinations?.length) {
                                handleSelect(dest, dest.transport_options[0], as.level)
                              } else {
                                handleSelect(dest, dest.transport_options[0], as.level)
                              }
                            }}
                              style={{
                                display: 'flex', alignItems: 'center', gap: 12,
                                padding: '12px 14px',
                                background: isPicked ? '#0f2d1a' : '#1a2332',
                                border: `2px solid ${isPicked ? '#22c55e' : mc.color}`,
                                borderRadius: 10, color: '#e2e8f0',
                                cursor: 'pointer', fontSize: 13, textAlign: 'left',
                                width: '100%',
                                opacity: isPicked ? 1 : 0.85,
                              }}
                            >
                              <span style={{ fontSize: 24 }}>{mc.icon}</span>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 700, fontSize: 14, color: '#e2e8f0' }}>{mc.label}</div>
                                <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                                  {dest.transport_options.length} option{dest.transport_options.length !== 1 ? 's' : ''} · {dest.next ? 'continues to next stop' : 'direct to destination'}
                                </div>
                              </div>
                              <span style={{ fontSize: 11, color: mc.color }}>
                                {dest.next ? '→' : '🏁'}
                              </span>
                            </button>
                          )
                        })
                      }

                      // Show transport option cards (segment 1+)
                      const modeLabels: Record<string, string> = { ride: '🚗 Cab / Auto / Bike', bus: '🚌 Bus Routes', other: 'Other' }
                      return as.seg.map((dest, di) => {
                        const isPicked = selectionAtLevel?.dest === dest
                        const tropt = dest.transport_options[0]
                        if (!tropt) return null
                        const isTransportPicked = isPicked && selectionAtLevel?.transport === tropt
                        return (
                          <div key={di} style={{
                            background: '#0f172a',
                            border: `1px solid ${isPicked ? '#22c55e' : '#1e293b'}`,
                            borderRadius: 8, overflow: 'hidden',
                          }}>
                            <div style={{
                              padding: '4px 8px', background: '#1a2332', borderBottom: '1px solid #1e293b',
                              fontSize: 9, fontWeight: 600, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4,
                            }}>
                              <span>{modeLabels[dest.to.type] || dest.to.type}</span>
                              <span style={{ marginLeft: 'auto' }}>→ {dest.to.name}</span>
                            </div>
                            <div style={{ padding: 5, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                              <button
                                onClick={() => handleSelect(dest, tropt, as.level)}
                                onMouseEnter={() => setHoveredOption(tropt)}
                                onMouseLeave={() => setHoveredOption(null)}
                                style={{
                                  flex: '1 1 100%',
                                  padding: '6px 8px',
                                  background: isTransportPicked ? '#0f2d1a' : '#1a2332',
                                  border: `1px solid ${isTransportPicked ? '#22c55e' : MODE_COLORS[tropt.mode] || '#334155'}`,
                                  borderRadius: 6, color: '#cbd5e1',
                                  cursor: 'pointer', fontSize: 10, textAlign: 'left',
                                  borderLeft: `3px solid ${MODE_COLORS[tropt.mode] || '#64748b'}`,
                                  opacity: selectionAtLevel && !isTransportPicked ? 0.5 : 1,
                                }}
                              >
                                {renderTransportOption(tropt, di, lvl > 0)}
                                {dest.from_stops?.length > 0 && (
                                  <div style={{ fontSize: 7, color: '#64748b', marginTop: 3, borderTop: '1px dashed #1e293b', paddingTop: 3 }}>
                                    ↓ Arrive at {dest.to.name}: {dest.from_stops.slice(0, 2).map(fs => `${fs.to.name}`).join(', ')}
                                  </div>
                                )}
                              </button>
                            </div>
                          </div>
                        )
                      })
                    })()}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* BUILT PATH SUMMARY */}
        {builtPath.length > 0 && (
          <div style={{ marginTop: 8, padding: 10, background: '#1a2332', borderRadius: 8, border: '1px solid #22c55e' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#22c55e', marginBottom: 8 }}>✅ Selected Path</div>
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
                      {(opt as any).train_number && (
                        <span style={{ color: '#a855f7' }}>🚆 #{(opt as any).train_number}</span>
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
                onChange={(e) => {
                  const v = e.target.value; setCustomInput(v)
                  if (v.length < 2) { setCustomSuggestions([]); return }
                  if (abortRef.current) abortRef.current.abort()
                  if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
                  setCustomLoading(true)
                  searchTimerRef.current = setTimeout(async () => {
                    const ctrl = new AbortController(); abortRef.current = ctrl
                    try {
                      const data = await searchPlaces(v, destLocation[0], destLocation[1], ctrl.signal)
                      if (!ctrl.signal.aborted) setCustomSuggestions((data.results || []).slice(0, 5))
                    } catch { if (ctrl.signal.aborted) return; setCustomSuggestions([]) }
                    finally { setCustomLoading(false) }
                  }, 300)
                }}
                style={{
                  width: '100%', padding: '8px 10px', fontSize: 12, border: '1px solid #475569',
                  borderRadius: 6, background: '#1e293b', color: '#e2e8f0', outline: 'none',
                }} />
              {customLoading && <div style={{ padding: '4px 10px', fontSize: 10, color: '#64748b' }}>Searching...</div>}
              {!customLoading && customSuggestions.length > 0 && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100, background: '#1e293b', border: '1px solid #475569', borderRadius: 5, marginTop: 2, maxHeight: 140, overflowY: 'auto' }}>
                  {customSuggestions.map((place, i) => (
                    <div key={i} onClick={() => {
                      setCustomInput(''); setCustomSuggestions([]); setShowCustomInput(false)
                    }}
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
