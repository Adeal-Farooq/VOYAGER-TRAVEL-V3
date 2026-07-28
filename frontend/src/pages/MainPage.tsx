import { useCallback, useState } from 'react'
import { useApp } from '../context/AppContext'
import SearchPanel from '../components/SearchPanel'
import AToBPanel from '../components/AToBPanel'
import TripPanel from '../components/TripPanel'
import DiscoveryPanel from '../components/DiscoveryPanel'
import MapView from '../components/MapView'
import HeaderBar from '../components/HeaderBar'
import NewsPopup from '../components/NewsPopup'
import type { PlaceResult, MapRouteGeometry } from '../types'
import { enrichPlace } from '../services/api'

export default function MainPage() {
  const {
    mode, setMode, tabs,
    mapCenter, setMapCenter, mapRef,
    selectedPlace, setSelectedPlace,
    allMarkers, setAllMarkers,
    sourceLocation, destLocation,
    userLocation, trackingActive, liveTrackingPos,
    routeGeometry, setRouteGeometry,
    newsItems, setNewsItems,
    openDiscovery, showDiscovery, discoveryPlace,
    searchCenter, searchRadius,
  } = useApp()

  const [enrichingName, setEnrichingName] = useState<string | null>(null)

  const handleViewOnMap = useCallback((place: PlaceResult) => {
    setSelectedPlace(place)
    setMapCenter([place.lat, place.lng])
    if (mapRef.current) mapRef.current.flyTo([place.lat, place.lng], 15)
  }, [setSelectedPlace, setMapCenter, mapRef])

  const handleViewDetails = useCallback(async (place: PlaceResult) => {
    setEnrichingName(place.name)
    setSelectedPlace(place)
    setMapCenter([place.lat, place.lng])
    if (mapRef.current) mapRef.current.flyTo([place.lat, place.lng], 16, { duration: 0.8 })
    try {
      const enriched = await enrichPlace(place)
      if (enriched?.status === 'success' && enriched.place) {
        const fullPlace = { ...place, ...enriched.place }
        setSelectedPlace(fullPlace)
        openDiscovery(fullPlace)
        // Propagate enriched data back to markers so list card also reflects real rating
        setAllMarkers(allMarkers.map(p =>
          p.name === fullPlace.name && Math.abs(p.lat - fullPlace.lat) < 0.001 ? fullPlace : p
        ))
      } else {
        openDiscovery(place)
      }
    } catch {
      openDiscovery(place)
    }
    setEnrichingName(null)
  }, [setSelectedPlace, openDiscovery, setMapCenter, mapRef, setAllMarkers])

  const {
    setSourceLocation: setSrcLoc,
    setDestLocation: setDstLoc,
    setSourceQuery: setSrcQ,
    setDestQuery: setDstQ,
    closeDiscovery,
  } = useApp()

  const handleNavigateToPlace = useCallback((place: PlaceResult) => {
    setMode('atob')
    setSrcLoc(userLocation || [12.9716, 77.5946])
    setDstLoc([place.lat, place.lng])
    setSrcQ(userLocation ? 'Current Location' : 'Bengaluru Central')
    setDstQ(place.name)
  }, [setMode, userLocation, setSrcLoc, setDstLoc, setSrcQ, setDstQ])

  const handleModeChange = useCallback((newMode: 'search' | 'atob' | 'trip') => {
    setMode(newMode)
    setRouteGeometry(null)
  }, [setMode, setRouteGeometry])

  const handleMarkerClick = useCallback((place: PlaceResult) => {
    setSelectedPlace(place)
    setMapCenter([place.lat, place.lng])
  }, [setSelectedPlace, setMapCenter])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', position: 'relative', overflow: 'hidden' }}>
      <HeaderBar />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      <div className="sidebar glass-strong" style={{
        width: 420, minWidth: 420, display: 'flex', flexDirection: 'column', zIndex: 1000,
        borderRight: '1px solid var(--glass-border)', position: 'relative',
      }}>

        <div style={{ display: 'flex', padding: '8px 16px', gap: 4, borderBottom: '1px solid rgba(198,197,212,0.2)' }}>
          {tabs.map(tab => (
            <button key={tab.key}
              onClick={() => handleModeChange(tab.key)}
              style={{
                flex: 1, padding: '8px 12px', border: 'none', borderRadius: 'var(--radius-full)',
                background: mode === tab.key ? 'var(--primary)' : 'transparent',
                color: mode === tab.key ? 'var(--on-primary)' : 'var(--text-muted)',
                fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.2s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: mode === 'search' ? 0 : '14px 16px' }}>
          {mode === 'search' && (
            <SearchPanel
              onSelectPlace={(place) => {
                setSelectedPlace(place)
                setDstLoc([place.lat, place.lng])
                setDstQ(place.name)
                handleViewOnMap(place)
              }}
              onViewOnMap={handleViewOnMap}
              onViewDetails={handleViewDetails}
              onNavigateToPlace={handleNavigateToPlace}
              enrichingName={enrichingName}
            />
          )}
          {mode === 'atob' && (
            <AToBPanel
              onRouteGeometry={setRouteGeometry}
              onNewsUpdate={setNewsItems}
            />
          )}
          {mode === 'trip' && <TripPanel />}
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative' }}>
        <button className="live-loc-btn" onClick={() => {
          const loc = liveTrackingPos || userLocation
          if (loc && mapRef.current) mapRef.current.flyTo(loc, 15)
        }} title="Return to my location">
          <span className="material-symbols-outlined">{liveTrackingPos ? 'my_location' : 'location_searching'}</span>
        </button>
        <NewsPopup />
        <MapView
          mapRef={mapRef}
          center={mapCenter}
          onCenterChange={setMapCenter}
          userLocation={userLocation}
          allMarkers={allMarkers}
          selectedPlace={selectedPlace}
          onMarkerClick={handleMarkerClick}
          routeGeometry={routeGeometry}
          sourceLocation={sourceLocation}
          destLocation={destLocation}
          liveTrackingPos={liveTrackingPos}
          trackingActive={trackingActive}
          newsItems={newsItems}
          searchCenter={searchCenter}
          searchRadius={searchRadius}
          numberedMarkers={!!searchCenter}
          highlightPlace={discoveryPlace || selectedPlace}
        />

        {showDiscovery && discoveryPlace && mode === 'search' && (
          <DiscoveryPanel
            place={discoveryPlace}
            onClose={closeDiscovery}
            onNavigate={handleNavigateToPlace}
            onShowOnMap={handleViewOnMap}
          />
        )}

        {!showDiscovery && enrichingName && mode === 'search' && (
          <div className="fade-in glass-strong" style={{
            position: 'absolute', top: 16, right: 16, width: 380, maxHeight: 'calc(100vh - 100px)',
            borderRadius: 'var(--radius-xl)', zIndex: 2000, overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(198,197,212,0.2)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--text-muted)' }}>discover</span>
              <span className="text-headline-sm" style={{ flex: 1 }}>Enriching...</span>
            </div>
            <div style={{ padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
              <div className="spinner" style={{ width: 32, height: 32 }} />
              <span className="text-body-md" style={{ color: 'var(--text-muted)' }}>{enrichingName}</span>
              <div className="loading-skeleton" style={{ width: '100%', height: 12, borderRadius: 6 }} />
              <div className="loading-skeleton" style={{ width: '80%', height: 12, borderRadius: 6 }} />
              <div className="loading-skeleton" style={{ width: '60%', height: 12, borderRadius: 6 }} />
            </div>
          </div>
        )}
      </div>
      </div>

      <div className="bottom-pill-nav">
        {tabs.map(tab => (
          <button key={tab.key}
            onClick={() => handleModeChange(tab.key)}
            className={`bottom-pill-tab${mode === tab.key ? ' active' : ''}`}>
            <span className={`material-symbols-outlined${mode === tab.key ? ' fill' : ''}`} style={{ fontSize: 18 }}>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
