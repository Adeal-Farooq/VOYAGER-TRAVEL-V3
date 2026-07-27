import { useState } from 'react'
import { useApp } from '../context/AppContext'

export default function TripPanel() {
  const { startJourney, stopJourney, trackingActive, liveTrackingPos, ridePrices, setMode } = useApp()
  const [activeDay, setActiveDay] = useState(0)

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div className="insights-box" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 20, color: 'var(--primary)' }}>auto_awesome</span>
          <div>
            <div className="text-body-md" style={{ fontWeight: 600 }}>AI Travel Insight</div>
            <div className="text-body-sm" style={{ color: 'var(--text-muted)' }}>
              Plan your trip with real-time transit data, weather, and traffic updates.
              Add stops and let VOYAGER optimize your route.
            </div>
          </div>
        </div>
      </div>

      <button onClick={() => { setMode('atob') }}
        style={{
          width: '100%', padding: 16, marginBottom: 16, border: '2px dashed var(--outline-variant)',
          borderRadius: 'var(--radius-xl)', background: 'transparent', cursor: 'pointer',
          textAlign: 'center', transition: 'all 0.2s',
        }}>
        <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--primary-container)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 24, color: 'var(--primary)' }}>add</span>
        </div>
        <div className="text-headline-sm" style={{ marginBottom: 4 }}>Create New Trip</div>
        <div className="text-body-sm" style={{ color: 'var(--text-muted)' }}>Plan a journey with multiple stops</div>
      </button>

      <div className="text-headline-sm" style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--primary)' }}>schedule</span>
        Your Trips
      </div>

      <div style={{ textAlign: 'center', padding: '40px 20px' }}>
        <span className="material-symbols-outlined" style={{ fontSize: 48, display: 'block', marginBottom: 12, color: 'var(--outline-variant)' }}>map</span>
        <div className="text-body-md" style={{ color: 'var(--text-muted)' }}>No trips planned yet.</div>
        <div className="text-body-sm" style={{ color: 'var(--text-muted)', marginTop: 4 }}>Search for a place and start navigating to create your first trip.</div>
      </div>

      {trackingActive && (
        <div style={{
          padding: 14, borderRadius: 'var(--radius-lg)', marginTop: 12,
          background: 'var(--primary-fixed)', border: '1px solid var(--primary-container)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', animation: 'pulse-dot 2s ease-in-out infinite' }} />
            <span className="text-headline-sm">Active Journey</span>
          </div>
          {liveTrackingPos && (
            <div className="text-body-sm" style={{ color: 'var(--text-muted)' }}>
              📍 {liveTrackingPos[0].toFixed(4)}, {liveTrackingPos[1].toFixed(4)}
            </div>
          )}
          <button onClick={stopJourney}
            style={{ marginTop: 8, padding: '8px 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--error)', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 4 }}>stop</span>
            End Journey
          </button>
        </div>
      )}
    </div>
  )
}
