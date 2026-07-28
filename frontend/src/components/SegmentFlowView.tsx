import { useState, useCallback, useMemo } from 'react'
import type { AllSegment, SegmentDestination, TransitOption, SegmentStepOption } from '../types'
import { getModeIconName, formatDuration, formatRupees, getScoreColor } from '../utils/helpers'
import { extendSegment } from '../services/api'

interface RoutePath {
  legs: { from: string; to: string; mode: string; route_number: string; distance_km: number; duration_minutes: number; fare: number; departure_times?: string[]; shape_path?: number[][]; is_running?: boolean; time_status?: string }[]
  total_fare: number
  total_duration_minutes: number
  total_distance_km: number
  total_walking_km: number
  transfers: number
}

interface SegmentFlowViewProps {
  segments: AllSegment[]
  sourceName: string
  destName: string
  destLat?: number
  destLng?: number
  onRouteGeometry: (geo: any) => void
}

type StepState = 'pick_dest' | 'pick_transit'

export default function SegmentFlowView({ segments, sourceName, destName, destLat, destLng, onRouteGeometry }: SegmentFlowViewProps) {
  const [activeSegIdx, setActiveSegIdx] = useState(0)
  const [selectedDest, setSelectedDest] = useState<SegmentDestination | null>(null)
  const [selectedTransit, setSelectedTransit] = useState<TransitOption | null>(null)
  const [stepState, setStepState] = useState<StepState>('pick_dest')
  const [chosenPath, setChosenPath] = useState<{ seg: number; dest: SegmentDestination; transit: TransitOption }[]>([])
  const [finished, setFinished] = useState(false)
  const [extending, setExtending] = useState(false)

  const currentSeg = segments[activeSegIdx]

  const totalFare = useMemo(() => chosenPath.reduce((sum, s) => sum + (s.transit.fare || 0), 0), [chosenPath])
  const totalDuration = useMemo(() => chosenPath.reduce((sum, s) => sum + (s.transit.duration_minutes || 0) + (s.dest.reach_options?.[0]?.duration_minutes || 0), 0), [chosenPath])

  const handleSelectDest = useCallback((dest: SegmentDestination) => {
    setSelectedDest(dest)
    setStepState('pick_transit')
    setSelectedTransit(null)
    const walkOpt = dest.reach_options?.find(o => o.mode === 'walk')
    if (walkOpt?.path) {
      onRouteGeometry([{
        type: 'segment', color: 'var(--secondary)', weight: 3, dashArray: '8,4',
        coordinates: walkOpt.path.map((c: any) => [c[0], c[1]]),
      }])
    }
  }, [onRouteGeometry])

  const handleSelectTransit = useCallback((transit: TransitOption) => {
    setSelectedTransit(transit)
    const geo: any[] = []
    // Reach path (walk/cab to stop)
    if (selectedDest) {
      const walkOpt = selectedDest.reach_options?.find(o => o.mode === 'walk')
      if (walkOpt?.path) {
        geo.push({
          type: 'segment', color: 'var(--secondary)', weight: 3, dashArray: '8,4',
          coordinates: walkOpt.path.map((c: any) => [c[0], c[1]]),
        })
      }
    }
    // Transit path
    if (transit.path) {
      geo.push({
        type: 'segment', color: 'var(--primary)', weight: 4,
        coordinates: transit.path.map((c: any) => [c[0], c[1]]),
      })
    }
    // Next_transit paths
    if (transit.next_transit) {
      for (const nt of transit.next_transit) {
        if (nt.path) {
          geo.push({
            type: 'segment', color: '#f59e0b', weight: 3,
            coordinates: nt.path.map((c: any) => [c[0], c[1]]),
          })
        }
      }
    }
    // Final options paths (drop-off to destination)
    if (transit.final_options) {
      for (const fo of transit.final_options) {
        if (fo.path) {
          geo.push({
            type: 'segment',
            color: fo.mode === 'walk' ? 'var(--secondary)' : '#f97316',
            weight: fo.mode === 'walk' ? 3 : 4,
            dashArray: fo.mode === 'walk' ? '8,4' : undefined,
            coordinates: fo.path.map((c: any) => [c[0], c[1]]),
          })
        }
      }
    }
    onRouteGeometry(geo)
  }, [onRouteGeometry, selectedDest])

  const handleConfirmTransit = useCallback(async () => {
    if (!selectedDest || !selectedTransit) return
    const transitEndsAtDest = !selectedTransit.arrives_at_stop && selectedTransit.mode === 'walk'
    const newPath = [...chosenPath, { seg: activeSegIdx, dest: selectedDest, transit: selectedTransit }]
    setChosenPath(newPath)

    // Check if there's a pre-computed next segment
    let nextIdx = selectedTransit.next_segment_index !== undefined && selectedTransit.next_segment_index !== null
      ? selectedTransit.next_segment_index
      : (activeSegIdx + 1 < segments.length ? activeSegIdx + 1 : null)

    // If no pre-computed next segment and transit arrives at a stop (not destination), try live extension
    if (nextIdx === null && !transitEndsAtDest && selectedTransit.to_lat && selectedTransit.to_lng) {
      setExtending(true)
      try {
        // Calculate arrival_seconds for time progression
        const now = new Date()
        let arrivalSec = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()
        for (const step of newPath) {
          if (step.transit.duration_minutes) arrivalSec += step.transit.duration_minutes * 60
          if (step.dest.reach_options?.[0]?.duration_minutes) arrivalSec += step.dest.reach_options[0].duration_minutes * 60
        }
        const dl = destLat ?? segments[activeSegIdx]?.from?.lat
        const dn = destLng ?? segments[activeSegIdx]?.from?.lng
        const res = await extendSegment(
          selectedTransit.to_lat, selectedTransit.to_lng, selectedTransit.to || 'Stop',
          dl, dn, destName,
          1, undefined, segments.length, arrivalSec
        )
        if (res?.status === 'success' && res?.segment) {
          const newSegment = res.segment
          newSegment.segment_index = segments.length
          segments.push(newSegment)
          nextIdx = segments.length - 1
        }
      } catch {
      } finally {
        setExtending(false)
      }
    }

    // Show accumulated journey paths on map after each confirmation
    const accGeo: any[] = []
    for (const step of newPath) {
      const walkOpt = step.dest.reach_options?.find(o => o.mode === 'walk')
      if (walkOpt?.path) {
        accGeo.push({ type: 'segment' as const, color: 'var(--secondary)', weight: 3, dashArray: '8,4' as const,
          coordinates: walkOpt.path.map((c: any) => [c[0], c[1]]) })
      }
      if (step.transit.path) {
        accGeo.push({ type: 'segment' as const, color: 'var(--primary)', weight: 4,
          coordinates: step.transit.path.map((c: any) => [c[0], c[1]]) })
      }
      if (step.transit.next_transit) {
        for (const nt of step.transit.next_transit) {
          if (nt.path) {
            accGeo.push({ type: 'segment' as const, color: '#f59e0b', weight: 3,
              coordinates: nt.path.map((c: any) => [c[0], c[1]]) })
          }
        }
      }
      if (step.transit.final_options) {
        for (const fo of step.transit.final_options) {
          if (fo.path) {
            accGeo.push({ type: 'segment' as const, color: '#f97316', weight: 4,
              coordinates: fo.path.map((c: any) => [c[0], c[1]]) })
          }
        }
      }
    }
    onRouteGeometry(accGeo)

    if (nextIdx === null || transitEndsAtDest) {
      setFinished(true)
      return
    }
    setActiveSegIdx(nextIdx)
    setSelectedDest(null)
    setSelectedTransit(null)
    setStepState('pick_dest')
  }, [selectedDest, selectedTransit, chosenPath, activeSegIdx, segments, onRouteGeometry])

  const handleReset = useCallback(() => {
    setActiveSegIdx(0)
    setSelectedDest(null)
    setSelectedTransit(null)
    setStepState('pick_dest')
    setChosenPath([])
    setFinished(false)
    onRouteGeometry(null)
  }, [onRouteGeometry])

  const getLocationName = (segIdx: number) => {
    if (segIdx === 0) return sourceName
    const prev = chosenPath[segIdx - 1]
    if (prev) {
      const transitTo = prev.transit.to || prev.transit.label
      return transitTo
    }
    return `Step ${segIdx + 1}`
  }

  const getModeIcon = (mode: string) => {
    switch (mode) {
      case 'walk': return 'directions_walk'
      case 'bus_ordinary': case 'bus_ac_vajra': case 'kia_bus': return 'directions_bus'
      case 'metro': return 'subway'
      case 'train': return 'train'
      case 'cab': case 'cab_xl': case 'cab_women': case 'cab_pet': return 'local_taxi'
      case 'auto': return 'pedal_bike'
      case 'bike': return 'motorcycle'
      default: return 'directions_transit'
    }
  }

  const getModeLabel = (mode: string) => {
    switch (mode) {
      case 'walk': return 'Walk'
      case 'bus_ordinary': return 'Bus'
      case 'bus_ac_vajra': return 'AC Bus'
      case 'kia_bus': return 'KIA Bus'
      case 'metro': return 'Metro'
      case 'train': return 'Train'
      case 'cab': case 'cab_xl': case 'cab_women': case 'cab_pet': return 'Cab'
      case 'auto': return 'Auto'
      case 'bike': return 'Bike'
      default: return mode
    }
  }

  if (!currentSeg || segments.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
        <span className="material-symbols-outlined" style={{ fontSize: 48, marginBottom: 12, opacity: 0.5 }}>alt_route</span>
        <div style={{ fontSize: 15, fontWeight: 500 }}>No route segments available</div>
        <div style={{ fontSize: 12, marginTop: 4 }}>Try a different source or destination</div>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 20, color: 'var(--primary)' }}>layers</span>
        <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>Multi-Hop Transit Planner</span>
        <button onClick={handleReset}
          style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11, padding: '4px 8px', borderRadius: 'var(--radius-md)' }}>
          Reset
        </button>
      </div>

      {/* Breadcrumb */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 4, marginBottom: 16,
        padding: '10px 14px', borderRadius: 'var(--radius-md)',
        background: 'var(--surface-container)', flexWrap: 'wrap', fontSize: 12,
      }}>
        <span style={{
          padding: '3px 8px', borderRadius: 'var(--radius-full)', fontWeight: 600,
          background: activeSegIdx === 0 ? 'var(--primary)' : 'var(--primary-container)',
          color: activeSegIdx === 0 ? 'var(--on-primary)' : 'var(--primary)',
          display: 'flex', alignItems: 'center', gap: 3,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>my_location</span>
          {sourceName}
        </span>
        {chosenPath.map((step, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)' }}>arrow_forward</span>
            <span style={{
              padding: '3px 8px', borderRadius: 'var(--radius-full)', fontWeight: 500,
              background: 'var(--surface-container-high)', color: 'var(--text)',
              display: 'flex', alignItems: 'center', gap: 3,
            }}>
              <span className="material-symbols-outlined" style={{ fontSize: 11 }}>
                {step.transit.mode === 'walk' ? 'directions_walk' :
                 step.transit.mode === 'bus_ordinary' || step.transit.mode === 'bus_ac_vajra' ? 'directions_bus' :
                 step.transit.mode === 'metro' ? 'subway' : 'local_taxi'}
              </span>
              {step.transit.route_number || getModeLabel(step.transit.mode)}
            </span>
            <span className="text-body-sm" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {step.transit.to || step.dest.stop.name}
            </span>
          </span>
        ))}
        {activeSegIdx > 0 && chosenPath.length < activeSegIdx + 1 && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)' }}>arrow_forward</span>
            <span style={{
              padding: '3px 8px', borderRadius: 'var(--radius-full)', fontWeight: 500,
              background: 'var(--surface-container-high)', color: 'var(--text)',
            }}>
              {getLocationName(activeSegIdx)}
            </span>
          </span>
        )}
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 'auto' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)' }}>arrow_forward</span>
          <span style={{
            padding: '3px 8px', borderRadius: 'var(--radius-full)', fontWeight: 600,
            background: finished ? 'var(--secondary-container)' : 'var(--surface-container-high)',
            color: finished ? 'var(--secondary)' : 'var(--text-muted)',
          }}>
            <span className="material-symbols-outlined" style={{ fontSize: 11, verticalAlign: 'middle', marginRight: 2 }}>location_on</span>
            {destName}
          </span>
        </span>
      </div>

      {/* Completed journey */}
      {finished && (
        <div style={{
          padding: 24, textAlign: 'center', borderRadius: 'var(--radius-lg)',
          background: 'var(--secondary-container)', border: '1px solid var(--secondary)',
          marginBottom: 16,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--secondary)' }}>location_on</span>
          <div style={{ fontWeight: 700, fontSize: 18, color: 'var(--secondary)', marginTop: 8 }}>Journey Complete!</div>
          <div style={{ fontSize: 14, color: 'var(--text)', marginTop: 4 }}>
            You have reached <strong>{destName}</strong>
          </div>
          <div style={{
            display: 'flex', gap: 24, justifyContent: 'center', marginTop: 12,
            fontSize: 13, color: 'var(--text-muted)',
          }}>
            <span><strong style={{ color: 'var(--text)' }}>{formatDuration(totalDuration)}</strong> total time</span>
            <span><strong style={{ color: 'var(--primary)' }}>{formatRupees(totalFare)}</strong> total fare</span>
            <span><strong style={{ color: 'var(--text)' }}>{chosenPath.length}</strong> segments</span>
          </div>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
            {chosenPath.map((step, i) => (
              <span key={i} style={{
                padding: '4px 10px', borderRadius: 'var(--radius-full)', fontSize: 11,
                background: 'rgba(255,255,255,0.3)', fontWeight: 500,
                display: 'flex', alignItems: 'center', gap: 4,
              }}>
                <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                  {step.transit.mode === 'walk' ? 'directions_walk' : step.transit.mode === 'metro' ? 'subway' : 'directions_bus'}
                </span>
                {step.transit.route_number || getModeLabel(step.transit.mode)} → {step.transit.to || step.dest.stop.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Current Step */}
      {!finished && (
        <>
          {/* Location header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px', marginBottom: 12,
            borderRadius: 'var(--radius-md)',
            background: 'var(--primary-container)',
            border: '1px solid var(--primary)',
          }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--primary)' }}>
              {activeSegIdx === 0 ? 'my_location' : 'location_on'}
            </span>
            <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--primary)' }}>
              You are at:
            </span>
            <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)', flex: 1 }}>
              {getLocationName(activeSegIdx)}
            </span>
            <span style={{
              padding: '2px 8px', borderRadius: 'var(--radius-full)', fontSize: 10,
              background: 'rgba(255,255,255,0.4)', fontWeight: 600, color: 'var(--text-muted)',
            }}>
              Step {activeSegIdx + 1} of {segments.length}
            </span>
          </div>

          {stepState === 'pick_dest' && (
            <>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', marginBottom: 10 }}>
                Where do you want to go?
              </div>
              <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 6 }}>
                {currentSeg.destinations.map((dest, di) => {
                  const walkOpt = dest.reach_options?.find(o => o.mode === 'walk')
                  const rideOpt = dest.reach_options?.find(o => o.mode !== 'walk')
                  const isSelected = selectedDest?.stop.name === dest.stop.name
                  return (
                    <div key={di}
                      onClick={() => handleSelectDest(dest)}
                      className="scale-in"
                      style={{
                        minWidth: 200, maxWidth: 240, flexShrink: 0,
                        borderRadius: 'var(--radius-lg)',
                        background: isSelected ? 'var(--primary-container)' : 'var(--surface-container)',
                        border: `2px solid ${isSelected ? 'var(--primary)' : 'var(--outline-variant)'}`,
                        cursor: 'pointer', overflow: 'hidden',
                        transition: 'all 0.15s',
                      }}>
                      {/* Stop header */}
                      <div style={{
                        padding: '10px 12px',
                        background: isSelected ? 'var(--primary)' : 'var(--surface-container-high)',
                        color: isSelected ? 'var(--on-primary)' : 'var(--text)',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                            {dest.stop.type === 'metro_station' ? 'subway' : 'directions_bus'}
                          </span>
                          <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{dest.stop.name}</span>
                        </div>
                        <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>
                          {dest.stop.type?.replace(/_/g, ' ') || 'Bus Stop'}
                          {dest.distance_from_current ? ` · ${dest.distance_from_current.toFixed(2)}km` : ''}
                        </div>
                      </div>
                      {/* Reach options */}
                      <div style={{ padding: '8px 10px' }}>
                        {walkOpt && (
                          <div style={{
                            display: 'flex', alignItems: 'center', gap: 6, fontSize: 11,
                            padding: '5px 8px', borderRadius: 'var(--radius-sm)',
                            background: 'var(--surface-container-lowest)',
                            color: 'var(--text-muted)', marginBottom: 4,
                          }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 13, color: 'var(--secondary)' }}>directions_walk</span>
                            <span>Walk {walkOpt.distance_km}km · {formatDuration(walkOpt.duration_minutes)}</span>
                            <span style={{ marginLeft: 'auto', color: 'var(--secondary)', fontWeight: 600 }}>Free</span>
                          </div>
                        )}
                        {rideOpt && (
                          <div style={{
                            display: 'flex', alignItems: 'center', gap: 6, fontSize: 11,
                            padding: '5px 8px', borderRadius: 'var(--radius-sm)',
                            background: 'var(--surface-container-lowest)',
                            color: 'var(--text-muted)',
                          }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 13, color: 'var(--error)' }}>
                              {rideOpt.mode === 'auto' ? 'pedal_bike' : rideOpt.mode === 'bike' ? 'motorcycle' : 'local_taxi'}
                            </span>
                            <span>{getModeLabel(rideOpt.mode)} {rideOpt.distance_km}km</span>
                            <span style={{ marginLeft: 'auto', fontWeight: 600, color: 'var(--primary)' }}>
                              {formatRupees(rideOpt.fare)}
                            </span>
                          </div>
                        )}
                        {!walkOpt && !rideOpt && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: 4 }}>
                            No direct reach options
                          </div>
                        )}
                        {dest.transit_options.length > 0 && (
                          <div style={{
                            marginTop: 6, fontSize: 10, fontWeight: 600,
                            color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: 3,
                          }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>directions_bus</span>
                            {dest.transit_options.length} transit option{dest.transit_options.length > 1 ? 's' : ''}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
              {currentSeg.destinations.length === 0 && (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                  No nearby stops found for this segment
                </div>
              )}
            </>
          )}

          {stepState === 'pick_transit' && selectedDest && (
            <>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
                padding: '8px 12px', borderRadius: 'var(--radius-md)',
                background: 'var(--surface-container-lowest)',
              }}>
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--secondary)' }}>check_circle</span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Selected stop:</span>
                <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{selectedDest.stop.name}</span>
                <button onClick={() => setStepState('pick_dest')}
                  style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: 11, fontWeight: 500 }}>
                  Change
                </button>
              </div>

              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', marginBottom: 10 }}>
                Choose transit from {selectedDest.stop.name}:
              </div>

              {/* Time-of-day safety advisory */}
              {(() => {
                const period = (window as any).__TIME_PERIOD__ || (new Date().getHours() >= 22 || new Date().getHours() < 1 ? 'late_night' : new Date().getHours() < 6 ? 'early_morning' : 'daytime')
                if (period === 'late_night') {
                  return (
                    <div style={{
                      padding: '8px 12px', marginBottom: 8, fontSize: 11,
                      borderRadius: 'var(--radius-md)',
                      background: 'rgba(251, 191, 36, 0.15)',
                      border: '1px solid rgba(251, 191, 36, 0.3)',
                      color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 6,
                    }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14, color: '#f59e0b' }}>dark_mode</span>
                      <span>It's late — cab/auto is safest right now. Buses may be limited or not running.</span>
                    </div>
                  )
                }
                if (period === 'early_morning') {
                  return (
                    <div style={{
                      padding: '8px 12px', marginBottom: 8, fontSize: 11,
                      borderRadius: 'var(--radius-md)',
                      background: 'rgba(96, 165, 250, 0.15)',
                      border: '1px solid rgba(96, 165, 250, 0.3)',
                      color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 6,
                    }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14, color: '#60a5fa' }}>wb_twilight</span>
                      <span>Early morning — bus service may be limited. Cabs are reliable at this hour.</span>
                    </div>
                  )
                }
                return null
              })()}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {selectedDest.transit_options.slice(0, 8).map((to, ti) => {
                  const isSelectedTransit = selectedTransit?.route_number === to.route_number && selectedTransit?.to === to.to
                  const isBusNotRunning = to.is_running === false
                  return (
                    <div key={ti}
                      onClick={() => handleSelectTransit(to)}
                      className="scale-in"
                      style={{
                        borderRadius: 'var(--radius-md)',
                        border: `2px solid ${isSelectedTransit ? 'var(--primary)' : isBusNotRunning ? 'rgba(239, 68, 68, 0.3)' : 'var(--outline-variant)'}`,
                        background: isSelectedTransit ? 'var(--primary-container)' : isBusNotRunning ? 'rgba(239, 68, 68, 0.05)' : 'var(--surface-container)',
                        cursor: 'pointer', overflow: 'hidden',
                        opacity: isBusNotRunning ? 0.7 : 1,
                      }}>
                      <div style={{ padding: '10px 12px' }}>
                        {/* Row 1: Mode icon + Route badge + Fare/Duration */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                          <span className="material-symbols-outlined" style={{
                            fontSize: 20, color: 'var(--primary)',
                            padding: 6, borderRadius: 'var(--radius-sm)',
                            background: 'var(--surface-container-high)',
                          }}>
                            {to.mode === 'walk' ? 'directions_walk' :
                             to.mode === 'metro' ? 'subway' :
                             to.mode === 'train' ? 'train' : 'directions_bus'}
                          </span>
                          {to.route_number && (
                            <span style={{
                              fontWeight: 700, fontSize: 13, letterSpacing: '0.02em',
                              padding: '2px 8px', borderRadius: 'var(--radius-full)',
                              background: to.mode === 'metro'
                                ? (to.route_number.toLowerCase().includes('purple') ? 'rgba(126,34,206,0.2)' :
                                   to.route_number.toLowerCase().includes('green') ? 'rgba(22,163,74,0.2)' : 'var(--primary-container)')
                                : 'var(--primary-container)',
                              color: to.mode === 'metro'
                                ? (to.route_number.toLowerCase().includes('purple') ? '#7E22CE' :
                                   to.route_number.toLowerCase().includes('green') ? '#16A34A' : 'var(--primary)')
                                : 'var(--primary)',
                            }}>
                              {to.route_number}
                            </span>
                          )}
                          {!to.route_number && (
                            <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
                              {getModeLabel(to.mode)}
                            </span>
                          )}
                          <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--primary)', lineHeight: 1.2 }}>
                              {formatRupees(to.fare)}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                              {formatDuration(to.duration_minutes)}
                            </div>
                          </div>
                        </div>

                        {/* Row 2: From → To stop names */}
                        <div style={{
                          fontSize: 12, color: 'var(--text)', marginBottom: 6,
                          padding: '4px 8px', borderRadius: 'var(--radius-sm)',
                          background: 'var(--surface-container-lowest)',
                          display: 'flex', alignItems: 'center', gap: 6,
                        }}>
                          <span style={{ fontWeight: 500, maxWidth: '40%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={to.from || getLocationName(activeSegIdx)}>
                            {to.from || getLocationName(activeSegIdx)}
                          </span>
                          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)', flexShrink: 0 }}>arrow_forward</span>
                          <span style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={to.to || ''}>
                            {to.to || 'towards destination'}
                          </span>
                        </div>

                        {/* Row 3: Departure/arrival times */}
                        {to.departure_time && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>schedule</span>
                            <span><strong>Dep:</strong> {to.departure_time}</span>
                            {to.arrival_time && <span><strong>Arr:</strong> {to.arrival_time}</span>}
                          </div>
                        )}

                        {/* Row 4: Time status badge */}
                        {to.is_running === false && to.time_status && (
                          <div style={{
                            marginTop: 6, padding: '4px 8px', fontSize: 10,
                            borderRadius: 'var(--radius-sm)',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            color: '#ef4444',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>schedule</span>
                            <span>{to.time_status}</span>
                          </div>
                        )}
                        {to.is_running !== false && to.time_status && (
                          <div style={{
                            marginTop: 6, padding: '4px 8px', fontSize: 10,
                            borderRadius: 'var(--radius-sm)',
                            background: 'rgba(34, 197, 94, 0.1)',
                            border: '1px solid rgba(34, 197, 94, 0.2)',
                            color: '#22c55e',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>check_circle</span>
                            <span>{to.time_status}</span>
                          </div>
                        )}

                        {/* Row 5: Bus departure frequency */}
                        {to.bus_times && to.bus_times.length > 0 && !isBusNotRunning && (
                          <div style={{ marginTop: 6 }}>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3, fontWeight: 500 }}>
                              Next departures:
                            </div>
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                              {to.bus_times.slice(0, 6).map((bt, bti) => (
                                <span key={bti} style={{
                                  fontSize: 10, padding: '2px 6px',
                                  borderRadius: 'var(--radius-sm)',
                                  background: 'var(--surface-container-high)',
                                  color: 'var(--text-muted)',
                                  fontVariantNumeric: 'tabular-nums',
                                }}>
                                  {bt.departure_time}
                                </span>
                              ))}
                              {to.bus_times.length > 6 && (
                                <span style={{ fontSize: 10, padding: '2px 6px', color: 'var(--text-muted)' }}>
                                  +{to.bus_times.length - 6} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Fallback alternatives when bus not running */}
                        {isBusNotRunning && to.alternative_options && to.alternative_options.length > 0 && (
                          <div style={{
                            marginTop: 6, padding: '6px 8px',
                            borderRadius: 'var(--radius-sm)',
                            background: 'rgba(251, 191, 36, 0.1)',
                            border: '1px solid rgba(251, 191, 36, 0.2)',
                            fontSize: 11,
                          }}>
                            <div style={{ fontWeight: 500, color: '#f59e0b', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                              <span className="material-symbols-outlined" style={{ fontSize: 12 }}>lightbulb</span>
                              Based on the current time, here's what we recommend instead:
                            </div>
                            {to.alternative_options.slice(0, 3).map((alt, ai) => (
                              <div key={ai} style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                padding: '2px 0', fontSize: 11, color: 'var(--text)',
                              }}>
                                <span className="material-symbols-outlined" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                  {alt.mode === 'walk' ? 'directions_walk' : alt.mode === 'auto' ? 'pedal_bike' : 'local_taxi'}
                                </span>
                                <span>{alt.label || getModeLabel(alt.mode)}</span>
                                <span>· {formatDuration(alt.duration_minutes)}</span>
                                {alt.fare > 0 && <span>· {formatRupees(alt.fare)}</span>}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Next transit chain */}
                        {to.next_transit && to.next_transit.length > 0 && (
                          <div style={{
                            marginTop: 6, padding: '6px 8px',
                            borderRadius: 'var(--radius-sm)',
                            background: 'var(--surface-container-lowest)',
                            fontSize: 11, color: 'var(--text-muted)',
                          }}>
                            <span style={{ fontWeight: 500 }}>Then:</span>
                            {to.next_transit.map((nt, nti) => (
                              <span key={nti} style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                                <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                                  {nt.mode === 'walk' ? 'directions_walk' :
                                   nt.mode === 'metro' ? 'subway' : 'directions_bus'}
                                </span>
                                <span style={{ fontWeight: 500 }}>
                                  {nt.route_number ? `${nt.route_number}` : getModeLabel(nt.mode)}
                                </span>
                                <span>→ {nt.to || 'destination'}</span>
                                <span style={{ marginLeft: 'auto' }}>
                                  {formatDuration(nt.duration_minutes)} · {formatRupees(nt.fare)}
                                </span>
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Final reach options */}
                        {to.final_options && to.final_options.length > 0 && (
                          <div style={{
                            marginTop: 6, fontSize: 11, color: 'var(--text-muted)',
                            display: 'flex', gap: 4, flexWrap: 'wrap',
                          }}>
                            <span style={{ fontWeight: 500 }}>Drop-off options:</span>
                            {to.final_options.slice(0, 3).map((fo, foi) => (
                              <span key={foi} style={{
                                padding: '1px 6px', borderRadius: 'var(--radius-sm)',
                                background: 'var(--surface-container-lowest)',
                              }}>
                                {fo.mode === 'walk' ? '🚶' : fo.mode === 'auto' ? '🛺' : '🚕'}
                                {formatDuration(fo.duration_minutes)}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Confirm button */}
                        {isSelectedTransit && (
                          <button onClick={handleConfirmTransit} disabled={extending}
                            style={{
                              width: '100%', padding: '10px', marginTop: 8,
                              border: 'none', borderRadius: 'var(--radius-md)',
                              background: extending ? 'var(--text-muted)' : 'var(--secondary)',
                              color: 'white',
                              fontSize: 13, fontWeight: 600, cursor: extending ? 'wait' : 'pointer',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                              opacity: extending ? 0.7 : 1,
                            }}>
                            {extending ? (
                              <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Finding onward connections...</>
                            ) : (
                              <><span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span>
                              {selectedTransit?.next_segment_index !== undefined && selectedTransit?.next_segment_index !== null ? 'Continue to Next Step' : 'Find Onward Transit'}</>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}

                {selectedDest.transit_options.length === 0 && (
                  <div style={{
                    padding: 20, textAlign: 'center', color: 'var(--text-muted)',
                    borderRadius: 'var(--radius-md)', background: 'var(--surface-container)',
                    fontSize: 13,
                  }}>
                    No transit options available from this stop.
                    <button onClick={() => setStepState('pick_dest')}
                      style={{ display: 'block', margin: '8px auto 0', background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: 12, fontWeight: 500 }}>
                      Choose a different stop
                    </button>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Route paths suggestions */}
          {stepState === 'pick_dest' && currentSeg.route_paths && currentSeg.route_paths.length > 0 && (
            <div style={{ marginTop: 14 }}>
              {(() => {
                const h = new Date().getHours()
                const hasLateRoutes = currentSeg.route_paths?.some(rp => rp.legs?.some(l => l.is_running === false))
                const isLate = h >= 22 || h < 1
                if (isLate || hasLateRoutes) {
                  return (
                    <div style={{
                      padding: '6px 10px', marginBottom: 8, fontSize: 10,
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(251, 191, 36, 0.12)',
                      border: '1px solid rgba(251, 191, 36, 0.25)',
                      color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 4,
                    }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 12, color: '#f59e0b' }}>info</span>
                      <span>Some bus routes may not be running at this hour — check individual options for details.</span>
                    </div>
                  )
                }
                return null
              })()}
              <div style={{
                fontSize: 11, fontWeight: 600, color: 'var(--text-muted)',
                textTransform: 'uppercase', marginBottom: 6,
                display: 'flex', alignItems: 'center', gap: 4,
              }}>
                <span className="material-symbols-outlined" style={{ fontSize: 13 }}>alt_route</span>
                Suggested multi-hop routes
              </div>
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto' }}>
                {currentSeg.route_paths.map((rp: RoutePath, ri: number) => (
                  <div key={ri} className="scale-in" style={{
                    minWidth: 220, maxWidth: 280, flexShrink: 0,
                    borderRadius: 'var(--radius-lg)',
                    background: 'var(--surface-container)',
                    overflow: 'hidden',
                    border: '1px solid var(--outline-variant)',
                  }}>
                    <div style={{
                      padding: '8px 10px',
                      background: 'var(--primary-container)',
                      display: 'flex', justifyContent: 'space-between',
                    }}>
                      <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--primary)' }}>
                        Route {ri + 1}
                      </span>
                      <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--primary)' }}>
                        {formatRupees(rp.total_fare)}
                      </span>
                    </div>
                    <div style={{ padding: '6px 10px' }}>
                      {rp.legs.map((leg, li) => {
                        const legNotRunning = leg.is_running === false
                        return (
                        <div key={li} style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          padding: '3px 0', fontSize: 11,
                          opacity: legNotRunning ? 0.5 : 1,
                        }}>
                          {legNotRunning ? (
                            <span className="material-symbols-outlined" style={{ fontSize: 12, color: '#ef4444' }}>block</span>
                          ) : (
                            <span className="material-symbols-outlined" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                              {leg.mode === 'walk' ? 'directions_walk' : leg.mode === 'metro' ? 'subway' : 'directions_bus'}
                            </span>
                          )}
                          <span style={{ fontWeight: 500, textDecoration: legNotRunning ? 'line-through' : 'none' }}>{leg.route_number || getModeLabel(leg.mode)}</span>
                          <span className="material-symbols-outlined" style={{ fontSize: 10, color: 'var(--text-muted)' }}>arrow_forward</span>
                          <span style={{ color: 'var(--text-muted)', flex: 1 }}>{leg.to}</span>
                          <span style={{ color: legNotRunning ? '#ef4444' : 'var(--text-muted)', fontSize: 10 }}>
                            {legNotRunning ? 'Not running' : `${leg.duration_minutes}min`}
                          </span>
                        </div>
                      )})}
                      <div style={{
                        display: 'flex', gap: 8, fontSize: 10,
                        color: 'var(--text-muted)', marginTop: 4,
                        paddingTop: 4, borderTop: '1px solid var(--outline-variant)',
                      }}>
                        <span>{rp.total_duration_minutes} min</span>
                        <span>{rp.total_distance_km} km</span>
                        <span>{rp.transfers} transfer{rp.transfers !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Total Bar */}
      {chosenPath.length > 0 && (
        <div style={{
          marginTop: 14, padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          background: 'var(--surface-container)',
          border: '1px solid var(--outline-variant)',
          display: 'flex', alignItems: 'center', gap: 12, fontSize: 12,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--primary)' }}>receipt_long</span>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <span>Total: <strong style={{ color: 'var(--primary)' }}>{formatRupees(totalFare)}</strong></span>
            <span>Duration: <strong>{formatDuration(totalDuration)}</strong></span>
            <span style={{ color: 'var(--text-muted)' }}>
              {chosenPath.length} segment{chosenPath.length > 1 ? 's' : ''} selected
            </span>
          </div>
        </div>
      )}

      <style>{`
        .scale-in { animation: scaleIn 0.2s ease-out; }
        @keyframes scaleIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
      `}</style>
    </div>
  )
}
