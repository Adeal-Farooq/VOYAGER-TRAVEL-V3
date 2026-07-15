import { useState, useCallback, useRef } from 'react'
import type { AppMode, PlaceResult, MapRouteGeometry, NewsItem } from '../types'
import { enrichPlace } from '../services/api'
import MapView from '../components/MapView'
import SearchPanel from '../components/SearchPanel'
import AToBPanel from '../components/AToBPanel'
import TripPanel from '../components/TripPanel'
import DiscoveryPanel from '../components/DiscoveryPanel'
import NewsOverlay from '../components/NewsOverlay'
import SegmentPanel from '../components/SegmentPanel'

interface MainPageProps {
  mode: AppMode
  onModeChange: (mode: AppMode) => void
  selectedPlace: PlaceResult | null
  onSelectPlace: (place: PlaceResult) => void
  mapCenter: [number, number]
  onMapCenterChange: (center: [number, number]) => void
  userLocation: [number, number] | null
  sourceLocation: [number, number] | null
  onSourceLocationChange: (loc: [number, number] | null) => void
  destLocation: [number, number] | null
  onDestLocationChange: (loc: [number, number] | null) => void
  onNavigateToPlace: (place: PlaceResult) => void
  mapRef: React.MutableRefObject<any>
  allMarkers: PlaceResult[]
  onMarkersUpdate: (markers: PlaceResult[]) => void
}

export default function MainPage({
  mode,
  onModeChange,
  selectedPlace,
  onSelectPlace,
  mapCenter,
  onMapCenterChange,
  userLocation,
  sourceLocation,
  onSourceLocationChange,
  destLocation,
  onDestLocationChange,
  onNavigateToPlace,
  mapRef,
  allMarkers,
  onMarkersUpdate,
}: MainPageProps) {
  const [showDiscovery, setShowDiscovery] = useState(false)
  const [discoveryPlace, setDiscoveryPlace] = useState<PlaceResult | null>(null)
  const [searchResults, setSearchResults] = useState<PlaceResult[]>([])
  const [nearbyResults, setNearbyResults] = useState<PlaceResult[]>([])
  const [searchCenter, setSearchCenter] = useState<[number, number] | null>(null)
  const [enrichingName, setEnrichingName] = useState<string | null>(null)
  const [routeGeometry, setRouteGeometry] = useState<MapRouteGeometry[]>([])
  const [newsItems, setNewsItems] = useState<NewsItem[]>([])
  const [mapWaypoints, setMapWaypoints] = useState<{ lat: number; lng: number; query: string }[]>([])

  const [segmentPanelOpen, setSegmentPanelOpen] = useState(false)
  const [segmentSourceName, setSegmentSourceName] = useState('')
  const [segmentDestName, setSegmentDestName] = useState('')
  const [segmentGroupSize, setSegmentGroupSize] = useState(1)
  const [segmentBudget, setSegmentBudget] = useState<number | undefined>(undefined)
  const [segmentGeometry, setSegmentGeometry] = useState<MapRouteGeometry[]>([])
  const [liveTrackingPos, setLiveTrackingPos] = useState<[number, number] | null>(null)
  const [trackingActive, setTrackingActive] = useState(false)
  const trackingWatcherRef = useRef<number | null>(null)

  const handleOpenSegmentPanel = useCallback((srcName: string, dstName: string, groupSize: number, budget?: number) => {
    setSegmentSourceName(srcName)
    setSegmentDestName(dstName)
    setSegmentGroupSize(groupSize)
    setSegmentBudget(budget)
    setSegmentGeometry([])
    setSegmentPanelOpen(true)
    setLiveTrackingPos(null)
    setTrackingActive(false)
    setTimeout(() => {
      if (mapRef.current) {
        mapRef.current.invalidateSize()
      }
    }, 100)
  }, [mapRef])

  const handleCloseSegmentPanel = useCallback(() => {
    setSegmentPanelOpen(false)
    setSegmentGeometry([])
    setRouteGeometry(prev => prev.filter(g => g.type !== 'segment' && g.type !== 'hover' && g.type !== 'stop'))
    if (trackingWatcherRef.current !== null) {
      navigator.geolocation.clearWatch(trackingWatcherRef.current)
      trackingWatcherRef.current = null
    }
    setLiveTrackingPos(null)
    setTrackingActive(false)
    setTimeout(() => {
      if (mapRef.current) {
        mapRef.current.invalidateSize()
      }
    }, 100)
  }, [mapRef])

  const handleStartJourney = useCallback(() => {
    if (!navigator.geolocation) return
    setTrackingActive(true)
    const watcherId = navigator.geolocation.watchPosition(
      (pos) => {
        setLiveTrackingPos([pos.coords.latitude, pos.coords.longitude])
      },
      (err) => {
        console.warn('GPS error:', err.message)
        setTrackingActive(false)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    )
    trackingWatcherRef.current = watcherId
  }, [])

  const handleSegmentGeometry = useCallback((geo: MapRouteGeometry[]) => {
    setSegmentGeometry(geo)
  }, [])

  const handleLocateNews = useCallback((item: NewsItem) => {
    if (item.lat && item.lng && mapRef.current) {
      mapRef.current.flyTo([item.lat, item.lng], 14, { duration: 1.5 })
    }
  }, [])

  const handleSearchResults = (results: PlaceResult[], center?: [number, number]) => {
    setNearbyResults([])
    setShowDiscovery(false)
    setDiscoveryPlace(null)
    setSearchResults(results)
    onMarkersUpdate(results)
    if (center) setSearchCenter(center)
  }

  const handleNearbyResults = (results: PlaceResult[]) => {
    setSearchResults([])
    setShowDiscovery(false)
    setDiscoveryPlace(null)
    setNearbyResults(results)
    onMarkersUpdate(results)
  }

  const handleViewOnMap = (place: PlaceResult) => {
    setDiscoveryPlace(place)
    setShowDiscovery(true)
    onSelectPlace(place)
  }

  const handleNearbyAroundPlace = (place: PlaceResult) => {
    setSearchCenter([place.lat, place.lng])
    onSelectPlace(place)
  }

  const handleViewDetails = async (place: PlaceResult) => {
    setShowDiscovery(false)
    setEnrichingName(place.name)
    try {
      const data = await enrichPlace(place)
      handleViewOnMap(data.place)
    } catch {
      handleViewOnMap(place)
    } finally {
      setEnrichingName(null)
    }
  }

  const handleModeChange = (newMode: AppMode) => {
    if (newMode !== mode) {
      setShowDiscovery(false)
      setDiscoveryPlace(null)
      setSearchResults([])
      setNearbyResults([])
      onMarkersUpdate([])
    }
    onModeChange(newMode)
  }

  const renderPanel = () => {
    switch (mode) {
      case 'search':
        return (
          <SearchPanel
            onSelectPlace={onSelectPlace}
            onNavigateToPlace={onNavigateToPlace}
            mapCenter={searchCenter || mapCenter}
            userLocation={userLocation}
            onSearchResults={handleSearchResults}
            onNearbyResults={handleNearbyResults}
            onViewOnMap={handleViewOnMap}
            onNearbyAroundPlace={handleNearbyAroundPlace}
            onMapCenterChange={onMapCenterChange}
            onViewDetails={handleViewDetails}
            enrichingName={enrichingName}
          />
        )
      case 'atob':
        return (
          <AToBPanel
            sourceLocation={sourceLocation || userLocation}
            destLocation={destLocation}
            onSourceLocationChange={onSourceLocationChange}
            onDestLocationChange={onDestLocationChange}
            onMapCenterChange={onMapCenterChange}
            mapRef={mapRef}
            onRouteGeometry={setRouteGeometry}
            onNewsUpdate={setNewsItems}
            onWaypointsChange={setMapWaypoints}
            onOpenSegmentPanel={handleOpenSegmentPanel}
          />
        )
      case 'trip':
        return <TripPanel />
    }
  }

  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="sidebar-header">
          <span style={{ fontSize: 28 }}>🧭</span>
          <h1>VOYAGER</h1>
          {userLocation && (
            <div onClick={() => onMapCenterChange(userLocation)}
              style={{
                width: 36, height: 36, borderRadius: '50%',
                background: '#1e3a5f', border: '2px solid #3b82f6',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', marginLeft: 'auto',
                fontSize: 18, transition: 'all 0.2s',
              }}
              title="Jump to my location"
              onMouseOver={(e) => (e.currentTarget.style.background = '#2563eb')}
              onMouseOut={(e) => (e.currentTarget.style.background = '#1e3a5f')}
            >
              📍
            </div>
          )}
        </div>

        <div className="mode-tabs">
          <button
            className={`mode-tab ${mode === 'search' ? 'active' : ''}`}
            onClick={() => handleModeChange('search')}
          >
            🔍 SEARCH
          </button>
          <button
            className={`mode-tab ${mode === 'atob' ? 'active' : ''}`}
            onClick={() => handleModeChange('atob')}
          >
            🗺️ A-TO-B
          </button>
          <button
            className={`mode-tab ${mode === 'trip' ? 'active' : ''}`}
            onClick={() => handleModeChange('trip')}
          >
            📋 TRIP
          </button>
        </div>

        <div className="sidebar-content scrollable-content">
          {renderPanel()}
        </div>
      </div>

      <div className="map-container" style={{ paddingBottom: segmentPanelOpen ? '2px' : 0 }}>
        <MapView
          center={mapCenter}
          onCenterChange={onMapCenterChange}
          selectedPlace={selectedPlace}
          userLocation={liveTrackingPos || userLocation}
          sourceLocation={sourceLocation}
          destLocation={destLocation}
          mapRef={mapRef}
          allMarkers={allMarkers}
          onMarkerClick={handleViewOnMap}
          routeGeometry={[...routeGeometry, ...segmentGeometry]}
          newsItems={newsItems}
          waypoints={mapWaypoints}
          liveTrackingPos={liveTrackingPos}
          trackingActive={trackingActive}
        />
        <NewsOverlay
          news={newsItems}
          loading={false}
          onLocateNews={handleLocateNews}
        />

        {showDiscovery && discoveryPlace && (
          <DiscoveryPanel
            place={discoveryPlace}
            onClose={() => setShowDiscovery(false)}
          />
        )}

        {segmentPanelOpen && sourceLocation && destLocation && (
          <SegmentPanel
            sourceLocation={sourceLocation}
            destLocation={destLocation}
            sourceName={segmentSourceName}
            destName={segmentDestName}
            groupSize={segmentGroupSize}
            budget={segmentBudget}
            onClose={handleCloseSegmentPanel}
            onGeometryChange={handleSegmentGeometry}
            onStartJourney={handleStartJourney}
            trackingActive={trackingActive}
          />
        )}
      </div>
    </div>
  )
}
