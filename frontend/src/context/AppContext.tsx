import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react'
import type { PlaceResult, AppMode, NewsItem, MapRouteGeometry, NavTab, RidePrice } from '../types'

interface AppState {
  mode: AppMode
  setMode: (mode: AppMode) => void
  tabs: NavTab[]

  userLocation: [number, number] | null
  setUserLocation: (loc: [number, number] | null) => void
  mapCenter: [number, number]
  setMapCenter: (center: [number, number]) => void
  mapRef: React.MutableRefObject<any>
  liveTrackingPos: [number, number] | null
  trackingActive: boolean

  sourceLocation: [number, number] | null
  setSourceLocation: (loc: [number, number] | null) => void
  destLocation: [number, number] | null
  setDestLocation: (loc: [number, number] | null) => void
  sourceQuery: string
  setSourceQuery: (q: string) => void
  destQuery: string
  setDestQuery: (q: string) => void

  selectedPlace: PlaceResult | null
  setSelectedPlace: (place: PlaceResult | null) => void
  allMarkers: PlaceResult[]
  setAllMarkers: (markers: PlaceResult[]) => void
  searchResults: PlaceResult[]
  setSearchResults: (results: PlaceResult[]) => void
  nearbyResults: PlaceResult[]
  setNearbyResults: (results: PlaceResult[]) => void
  searchCenter: [number, number] | null
  setSearchCenter: (center: [number, number] | null) => void
  searchRadius: number
  setSearchRadius: (radius: number) => void

  showDiscovery: boolean
  discoveryPlace: PlaceResult | null
  openDiscovery: (place: PlaceResult) => void
  closeDiscovery: () => void

  routeGeometry: MapRouteGeometry[] | null
  setRouteGeometry: (geo: MapRouteGeometry[] | null) => void
  newsItems: NewsItem[]
  setNewsItems: (items: NewsItem[]) => void
  ridePrices: RidePrice[]
  setRidePrices: (prices: RidePrice[]) => void

  groupSize: number
  setGroupSize: (size: number) => void
  budget: number | undefined
  setBudget: (budget: number | undefined) => void
  travelMode: 'public' | 'personal' | 'walking'
  setTravelMode: (mode: 'public' | 'personal' | 'walking') => void

  startJourney: () => void
  stopJourney: () => void

  darkMode: boolean
  toggleDarkMode: () => void
  weather: { condition?: string; temp?: number; humidity?: number } | null
  setWeather: (w: { condition?: string; temp?: number; humidity?: number } | null) => void
}

const AppContext = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AppMode>('search')
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number]>([12.9716, 77.5946])
  const mapRef = useRef<any>(null)
  const [liveTrackingPos, setLiveTrackingPos] = useState<[number, number] | null>(null)
  const [trackingActive, setTrackingActive] = useState(false)
  const trackingWatcher = useRef<number | null>(null)

  const [sourceLocation, setSourceLocation] = useState<[number, number] | null>(null)
  const [destLocation, setDestLocation] = useState<[number, number] | null>(null)
  const [sourceQuery, setSourceQuery] = useState('')
  const [destQuery, setDestQuery] = useState('')

  const [selectedPlace, setSelectedPlace] = useState<PlaceResult | null>(null)
  const [allMarkers, setAllMarkers] = useState<PlaceResult[]>([])
  const [searchResults, setSearchResults] = useState<PlaceResult[]>([])
  const [nearbyResults, setNearbyResults] = useState<PlaceResult[]>([])
  const [searchCenter, setSearchCenter] = useState<[number, number] | null>(null)
  const [searchRadius, setSearchRadius] = useState(2)

  const [showDiscovery, setShowDiscovery] = useState(false)
  const [discoveryPlace, setDiscoveryPlace] = useState<PlaceResult | null>(null)

  const [routeGeometry, setRouteGeometry] = useState<MapRouteGeometry[] | null>(null)
  const [newsItems, setNewsItems] = useState<NewsItem[]>([])
  const [ridePrices, setRidePrices] = useState<RidePrice[]>([])

  const [groupSize, setGroupSize] = useState(1)
  const [budget, setBudget] = useState<number | undefined>(undefined)
  const [travelMode, setTravelMode] = useState<'public' | 'personal' | 'walking'>('public')
  const [darkMode, setDarkMode] = useState(() => window.matchMedia('(prefers-color-scheme: dark)').matches)
  const toggleDarkMode = useCallback(() => setDarkMode(p => !p), [])
  const [weather, setWeather] = useState<{ condition?: string; temp?: number; humidity?: number } | null>(null)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  const tabs: NavTab[] = [
    { key: 'search', label: 'Search', icon: 'search' },
    { key: 'atob', label: 'A to B', icon: 'directions_transit' },
    { key: 'trip', label: 'Trip', icon: 'map' },
  ]

  const openDiscovery = useCallback((place: PlaceResult) => {
    setDiscoveryPlace(place)
    setShowDiscovery(true)
  }, [])

  const closeDiscovery = useCallback(() => {
    setShowDiscovery(false)
    setDiscoveryPlace(null)
  }, [])

  const startJourney = useCallback(() => {
    if (!navigator.geolocation) return
    setTrackingActive(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => setLiveTrackingPos([pos.coords.latitude, pos.coords.longitude]),
      () => {},
      { enableHighAccuracy: true, timeout: 5000 }
    )
    trackingWatcher.current = navigator.geolocation.watchPosition(
      (pos) => setLiveTrackingPos([pos.coords.latitude, pos.coords.longitude]),
      () => {},
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    )
  }, [])

  const stopJourney = useCallback(() => {
    if (trackingWatcher.current !== null) {
      navigator.geolocation.clearWatch(trackingWatcher.current)
      trackingWatcher.current = null
    }
    setTrackingActive(false)
    setLiveTrackingPos(null)
  }, [])

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc: [number, number] = [pos.coords.latitude, pos.coords.longitude]
          setUserLocation(loc)
          setMapCenter(loc)
          if (mapRef.current) mapRef.current.flyTo(loc, 14)
        },
        () => {},
        { enableHighAccuracy: true, timeout: 10000 }
      )
    }
  }, [])

  return (
    <AppContext.Provider value={{
      mode, setMode, tabs,
      userLocation, setUserLocation, mapCenter, setMapCenter, mapRef,
      liveTrackingPos, trackingActive,
      sourceLocation, setSourceLocation, destLocation, setDestLocation,
      sourceQuery, setSourceQuery, destQuery, setDestQuery,
      selectedPlace, setSelectedPlace, allMarkers, setAllMarkers,
      searchResults, setSearchResults, nearbyResults, setNearbyResults,
      searchCenter, setSearchCenter, searchRadius, setSearchRadius,
      showDiscovery, discoveryPlace, openDiscovery, closeDiscovery,
      routeGeometry, setRouteGeometry, newsItems, setNewsItems,
      ridePrices, setRidePrices,
      groupSize, setGroupSize, budget, setBudget, travelMode, setTravelMode,
      startJourney, stopJourney,
      darkMode, toggleDarkMode, weather, setWeather,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp(): AppState {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
