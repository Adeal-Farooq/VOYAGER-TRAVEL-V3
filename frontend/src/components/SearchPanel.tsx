import { useState, useCallback, useEffect, useRef } from 'react'
import type { PlaceResult } from '../types'
import { searchPlaces, getNearbyPlaces, getSuggestions } from '../services/api'
import { getPlaceIconName, getScoreLabel, getScoreColor } from '../utils/helpers'
import { useApp } from '../context/AppContext'

interface SearchPanelProps {
  onSelectPlace: (place: PlaceResult) => void
  onViewOnMap: (place: PlaceResult) => void
  onViewDetails: (place: PlaceResult) => void
  onNavigateToPlace: (place: PlaceResult) => void
  enrichingName?: string | null
}

const NEARBY_TAGS = [
  { key: 'all', icon: 'explore', label: 'All' },
  { key: 'atm', icon: 'account_balance', label: 'ATM' },
  { key: 'bank', icon: 'account_balance', label: 'Bank' },
  { key: 'hospital', icon: 'local_hospital', label: 'Hospital' },
  { key: 'pharmacy', icon: 'local_pharmacy', label: 'Pharmacy' },
  { key: 'restaurant', icon: 'restaurant', label: 'Restaurant' },
  { key: 'cafe', icon: 'local_cafe', label: 'Cafe' },
  { key: 'hotel', icon: 'hotel', label: 'Hotel' },
  { key: 'mall', icon: 'local_mall', label: 'Mall' },
  { key: 'petrol_pump', icon: 'local_gas_station', label: 'Petrol' },
  { key: 'charging_station', icon: 'ev_station', label: 'EV Station' },
  { key: 'supermarket', icon: 'local_grocery_store', label: 'Market' },
  { key: 'park', icon: 'park', label: 'Park' },
  { key: 'bus_stop', icon: 'directions_bus', label: 'Bus Stop' },
  { key: 'metro_station', icon: 'subway', label: 'Metro' },
  { key: 'temple', icon: 'temple_hindu', label: 'Temple' },
  { key: 'police', icon: 'local_police', label: 'Police' },
  { key: 'school', icon: 'school', label: 'School' },
  { key: 'gym', icon: 'fitness_center', label: 'Gym' },
  { key: 'cinema', icon: 'theater_comedy', label: 'Cinema' },
]

export default function SearchPanel({
  onSelectPlace, onViewOnMap, onViewDetails, onNavigateToPlace, enrichingName,
}: SearchPanelProps) {
  const { userLocation, setAllMarkers } = useApp()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlaceResult[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [radius, setRadius] = useState(2)
  const [activeTag, setActiveTag] = useState('all')
  const [nearbyResults, setNearbyResults] = useState<PlaceResult[]>([])
  const [tab, setTab] = useState<'search' | 'nearby'>('search')
  const [searchedPlace, setSearchedPlace] = useState<PlaceResult | null>(null)
  const searchAbortRef = useRef<AbortController | null>(null)

  const handleSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) return
    if (searchAbortRef.current) searchAbortRef.current.abort()
    const ctrl = new AbortController()
    searchAbortRef.current = ctrl
    setLoading(true); setError('')
    try {
      const centerLat = userLocation?.[0] ?? 12.9716
      const centerLng = userLocation?.[1] ?? 77.5946
      const data = await searchPlaces(q, centerLat, centerLng, ctrl.signal)
      if (ctrl.signal.aborted) return
      const places = data.results || []
      setResults(places); setSuggestions([]); setAllMarkers(places)
      if (places.length > 0) {
        setSearchedPlace(places[0])
        onSelectPlace(places[0])
      } else setError(`No results found for "${q}". Try a different search.`)
    } catch (err) {
      if (ctrl.signal.aborted) return
      setError('Search failed. Please try again.')
    } finally { setLoading(false) }
  }, [query, onSelectPlace, userLocation])

  useEffect(() => {
    if (!query || query.length < 2) { setSuggestions([]); return }
    const timer = setTimeout(async () => {
      try { const sugg = await getSuggestions(query); setSuggestions(sugg) }
      catch { setSuggestions([]) }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const handleNearby = useCallback(async (tag: string) => {
    setActiveTag(tag); setLoading(true); setError('')
    try {
      const lat = searchedPlace?.lat ?? userLocation?.[0] ?? 12.9716
      const lng = searchedPlace?.lng ?? userLocation?.[1] ?? 77.5946
      const data = await getNearbyPlaces(lat, lng, radius, tag === 'all' ? undefined : tag)
      const places = data.results || []
      setNearbyResults(places); setAllMarkers(places)
      if (places.length === 0) setError(`No ${tag} found within ${radius}km. Try increasing radius.`)
    } catch { setError('Nearby search failed.') }
    finally { setLoading(false) }
  }, [radius, searchedPlace, userLocation])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }, [handleSearch])

  return (
    <div style={{ padding: 0 }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(198,197,212,0.15)' }}>
        <div style={{ display: 'flex', gap: 8, position: 'relative' }}>
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px', borderRadius: 'var(--radius-lg)',
            background: 'rgba(0,0,0,0.03)', border: '1px solid var(--outline-variant)',
          }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--text-muted)' }}>search</span>
            <input type="text" placeholder="Search any place in Bengaluru..."
              value={query} onChange={(e) => {
                setQuery(e.target.value)
                if (!e.target.value.trim()) {
                  setResults([]); setSuggestions([]); setAllMarkers([])
                }
              }}
              onKeyDown={handleKeyDown}
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontSize: 14, color: 'var(--text)' }}
            />
          </div>
          <button onClick={handleSearch} disabled={loading}
            style={{
              padding: '10px 20px', border: 'none', borderRadius: 'var(--radius-lg)',
              background: 'var(--primary)', color: 'var(--on-primary)',
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
              opacity: loading ? 0.6 : 1,
            }}>
            {loading ? '...' : 'Search'}
          </button>
        </div>

        {suggestions.length > 0 && (
          <div className="glass" style={{
            position: 'absolute', left: 16, right: 100, top: 108, zIndex: 10000,
            borderRadius: 'var(--radius-md)', maxHeight: 200, overflowY: 'auto',
            boxShadow: '0 8px 32px var(--shadow-primary)',
          }}>
            {suggestions.map((s, i) => (
              <div key={i} onClick={() => { setQuery(s); setSuggestions([]) }}
                style={{ padding: '10px 14px', cursor: 'pointer', fontSize: 13, borderBottom: i < suggestions.length - 1 ? '1px solid var(--outline-variant)' : 'none', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--text-muted)' }}>location_on</span>
                {s}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 0, padding: '8px 16px', borderBottom: '1px solid rgba(198,197,212,0.15)' }}>
        {['search', 'nearby'].map(t => (
          <button key={t} onClick={() => setTab(t as typeof tab)}
            style={{
              flex: 1, padding: '8px 12px', border: 'none', borderRadius: 'var(--radius-full)',
              background: tab === t ? 'var(--primary)' : 'transparent',
              color: tab === t ? 'var(--on-primary)' : 'var(--text-muted)',
              fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{t === 'search' ? 'search' : 'near_me'}</span>
            {t === 'search' ? 'Search Specific' : 'Search Nearby'}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ margin: '8px 16px', padding: '10px 14px', borderRadius: 'var(--radius-md)', background: 'var(--error-container)', color: 'var(--error)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>error</span>
          {error}
        </div>
      )}

      {tab === 'search' && (
        <div style={{ padding: '8px 16px' }}>
          {loading && [1,2,3].map(i => (
            <div key={i} style={{ padding: 14, marginBottom: 8, borderRadius: 'var(--radius-lg)', background: 'var(--surface-container)' }}>
              <div className="loading-skeleton" style={{ width: `${60 + i * 20}%`, height: 14, marginBottom: 6 }} />
              <div className="loading-skeleton" style={{ width: '40%', height: 12 }} />
            </div>
          ))}
          {results.map((place, i) => (
            <PlaceCard key={i} place={place}
              onView={() => { onSelectPlace(place); onViewOnMap(place) }}
              onNavigate={() => onNavigateToPlace(place)}
              onViewDetails={() => onViewDetails(place)}
              isLoading={enrichingName === place.name}
            />
          ))}
          {results.length === 0 && !loading && !error && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
              <span className="material-symbols-outlined" style={{ fontSize: 48, display: 'block', marginBottom: 12, color: 'var(--outline-variant)' }}>search</span>
              <div className="text-body-md">Search any place or landmark in Bengaluru</div>
            </div>
          )}
        </div>
      )}

      {tab === 'nearby' && (
        <div>
          {searchedPlace && (
            <div style={{ margin: '8px 16px', padding: '8px 12px', borderRadius: 'var(--radius-md)', background: 'var(--primary-fixed)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--primary)' }}>near_me</span>
              <span>Around: <strong>{searchedPlace.name}</strong></span>
              <button onClick={() => setSearchedPlace(null)}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
                Use my location
              </button>
            </div>
          )}

          <div style={{ padding: '8px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              <span>Radius: {radius} km</span>
              <span>{nearbyResults.length} places found</span>
            </div>
            <input type="range" min={0.5} max={10} step={0.5} value={radius}
              onChange={(e) => setRadius(parseFloat(e.target.value))}
              style={{ width: '100%', marginBottom: 8 }} />
          </div>

          <div className="hide-scrollbar" style={{
            display: 'flex', gap: 6, padding: '0 16px 8px', overflowX: 'auto',
          }}>
            {NEARBY_TAGS.map((tag) => (
              <button key={tag.key} onClick={() => handleNearby(tag.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap',
                  padding: '6px 14px', border: '1px solid var(--outline-variant)',
                  borderRadius: 'var(--radius-full)',
                  background: activeTag === tag.key ? 'var(--primary)' : 'var(--surface-container)',
                  color: activeTag === tag.key ? 'var(--on-primary)' : 'var(--text-muted)',
                  fontSize: 12, cursor: 'pointer', fontWeight: 500, transition: 'all 0.15s',
                }}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{tag.icon}</span>
                {tag.label}
              </button>
            ))}
          </div>

          <div style={{ padding: '8px 16px' }}>
            {loading && [1,2,3].map(i => (
              <div key={i} style={{ padding: 14, marginBottom: 8, borderRadius: 'var(--radius-lg)', background: 'var(--surface-container)' }}>
                <div className="loading-skeleton" style={{ width: `${50 + i * 20}%`, height: 14, marginBottom: 6 }} />
                <div className="loading-skeleton" style={{ width: '30%', height: 12 }} />
              </div>
            ))}
            {nearbyResults.map((place, i) => (
              <PlaceCard key={i} place={place}
                onView={() => { onSelectPlace(place); onViewOnMap(place) }}
                onNavigate={() => onNavigateToPlace(place)}
                onViewDetails={() => onViewDetails(place)}
                isLoading={enrichingName === place.name}
              />
            ))}
            {nearbyResults.length === 0 && !loading && !error && (
              <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
                Click a category to find nearby places
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function PlaceCard({ place, onView, onNavigate, onViewDetails, isLoading }: {
  place: PlaceResult; onView: () => void; onNavigate: () => void; onViewDetails?: () => void; isLoading?: boolean
}) {
  const score = place.reliability_score || 0.5
  const [imgError, setImgError] = useState(false)
  const [showReviews, setShowReviews] = useState(false)
  const reviews = place.reviews?.slice(0, 3) || []

  return (
    <div onClick={onView} className="slide-up" style={{
      padding: 14, marginBottom: 10, borderRadius: 'var(--radius-lg)', cursor: 'pointer',
      background: getScoreColor(score * 100) === '#22c55e' ? '#f0fdf4' : getScoreColor(score * 100) === '#eab308' ? '#fffbeb' : '#fef2f2',
      border: `1px solid ${getScoreColor(score * 100) === '#22c55e' ? '#bbf7d0' : getScoreColor(score * 100) === '#eab308' ? '#fde68a' : '#fecaca'}`,
      borderLeft: `3px solid ${getScoreColor(score * 100)}`,
      transition: 'all 0.2s',
    }}>
      {place.image_url && !imgError && (
        <div style={{ width: '100%', height: 110, overflow: 'hidden', borderRadius: 'var(--radius-md)', marginBottom: 8 }}>
          <img src={place.image_url} alt={place.name}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={() => setImgError(true)} />
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span className="material-symbols-outlined fill" style={{
          fontSize: 20, color: getScoreColor(score * 100),
        }}>{getPlaceIconName(place.place_type)}</span>
        <span className="text-headline-sm" style={{ flex: 1 }}>{place.name}</span>
        <span className="reliability-pill" style={{ background: getScoreColor(score * 100), color: 'white', fontSize: 11, padding: '2px 10px' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>{score >= 0.6 ? 'verified' : 'warning'}</span>
          {getScoreLabel(score * 100)} ({(score * 100).toFixed(0)}%)
        </span>
      </div>

      {place.address && (
        <div className="text-body-sm" style={{ color: 'var(--text-muted)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>location_on</span>
          {place.address}
        </div>
      )}

      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, flexWrap: 'wrap' }}>
        {place.distance_km !== undefined && <span>📍 {place.distance_km} km</span>}
        {place.rating && (
          <span>
            <span className="material-symbols-outlined" style={{ fontSize: 12, verticalAlign: 'middle', color: '#f59e0b' }}>star</span>
            {' '}{place.rating.toFixed(1)}
          </span>
        )}
        <span className="place-type-badge">{place.place_type.replace(/_/g, ' ')}</span>
      </div>

      {place.hotel_prices && place.hotel_prices.avg_price > 0 && (
        <div style={{ fontSize: 12, color: '#b45309', fontWeight: 600, marginBottom: 4 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle', marginRight: 2 }}>payments</span>
          ₹{place.hotel_prices.min_price} - ₹{place.hotel_prices.max_price} / night
        </div>
      )}

      {place.review_summary && (
        <div className="text-body-sm" style={{
          padding: '6px 10px', borderRadius: 'var(--radius-md)',
          background: 'var(--surface-container)', fontStyle: 'italic', marginBottom: 6,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 12, verticalAlign: 'middle', marginRight: 2, color: 'var(--primary)' }}>rate_review</span>
          {place.review_summary}
        </div>
      )}

      {reviews.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <button onClick={(e) => { e.stopPropagation(); setShowReviews(!showReviews) }}
            style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: 12, cursor: 'pointer', fontWeight: 500, padding: 0 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, verticalAlign: 'middle' }}>{showReviews ? 'expand_less' : 'expand_more'}</span>
            {showReviews ? 'Hide' : 'Show'} reviews ({reviews.length})
          </button>
          {showReviews && reviews.map((rv, idx) => (
            <div key={idx} style={{ marginTop: 4, padding: '6px 8px', background: 'var(--surface-container-lowest)', borderRadius: 'var(--radius-md)', fontSize: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
                <span style={{ fontWeight: 500 }}>{rv.user}</span>
                <span>{Array.from({length: rv.rating}, () => '⭐').join('')} <span style={{ fontSize: 11 }}>{rv.date}</span></span>
              </div>
              <div style={{ fontStyle: 'italic', marginTop: 2, color: 'var(--text-muted)' }}>"{rv.text}"</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button onClick={(e) => { e.stopPropagation(); onViewDetails?.() }} disabled={isLoading}
          style={{ padding: '6px 14px', border: '1px solid var(--outline-variant)', borderRadius: 'var(--radius-full)', background: 'var(--surface-container)', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>info</span>
          Details
        </button>
        <button onClick={(e) => { e.stopPropagation(); onNavigate() }}
          style={{ padding: '6px 14px', border: 'none', borderRadius: 'var(--radius-full)', background: 'var(--primary)', color: 'var(--on-primary)', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>directions_transit</span>
          Navigate
        </button>
      </div>
    </div>
  )
}
