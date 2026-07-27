import axios from 'axios'
import type { SearchResponse, NearbyResponse, RoutePlanResponse, RidePriceResponse, EnrichSingleResponse, AllSegmentsResponse } from '../types'
import type { PlaceResult } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export async function searchPlaces(q: string, lat?: number, lng?: number, signal?: AbortSignal): Promise<SearchResponse> {
  const params: any = { q }
  if (lat !== undefined) params.lat = lat
  if (lng !== undefined) params.lng = lng
  const { data } = await api.get<SearchResponse>('/search/places', { params, signal })
  return data
}

export async function getNearbyPlaces(
  lat: number,
  lng: number,
  radiusKm: number = 2,
  placeType?: string
): Promise<NearbyResponse> {
  const params: any = { lat, lng, radius_km: radiusKm }
  if (placeType) params.place_type = placeType
  const { data } = await api.get<NearbyResponse>('/search/nearby', { params })
  return data
}

export async function getSuggestions(q: string): Promise<string[]> {
  const { data } = await api.get('/search/suggestions', { params: { q } })
  return data.suggestions || []
}

export async function verifyPlace(name: string, address?: string): Promise<any> {
  const params: any = { name }
  if (address) params.address = address
  const { data } = await api.get('/search/verify-place', { params })
  return data
}

export async function planRoute(params: {
  source_lat: number
  source_lng: number
  dest_lat: number
  dest_lng: number
  mode?: string
  budget?: number
  group_size?: number
  waypoints?: { lat: number; lng: number; name: string }[]
}): Promise<RoutePlanResponse> {
  const { data } = await api.post<RoutePlanResponse>('/routes/plan', params)
  return data
}

export async function getMetroStations(line?: string): Promise<any> {
  const params: any = {}
  if (line) params.line = line
  const { data } = await api.get('/routes/metro-stations', { params })
  return data
}

export async function getBusStops(nearLat?: number, nearLng?: number, radius?: number): Promise<any> {
  const params: any = {}
  if (nearLat !== undefined) params.near_lat = nearLat
  if (nearLng !== undefined) params.near_lng = nearLng
  if (radius !== undefined) params.radius = radius
  const { data } = await api.get('/routes/bus-stops', { params })
  return data
}

export async function getRidePrices(
  source: string, destination: string,
  sourceLat?: number, sourceLng?: number,
  destLat?: number, destLng?: number,
): Promise<RidePriceResponse> {
  const params: any = { source, destination }
  if (sourceLat !== undefined) params.source_lat = sourceLat
  if (sourceLng !== undefined) params.source_lng = sourceLng
  if (destLat !== undefined) params.dest_lat = destLat
  if (destLng !== undefined) params.dest_lng = destLng
  const { data } = await api.get<RidePriceResponse>('/search/ride-prices', { params })
  return data
}

export async function enrichPlace(place: PlaceResult): Promise<EnrichSingleResponse> {
  const { data } = await api.post<EnrichSingleResponse>('/search/enrich-place', {
    name: place.name,
    lat: place.lat,
    lng: place.lng,
    place_type: place.place_type,
    address: place.address,
  })
  return data
}

export async function getSegmentStep(
  fromLat: number, fromLng: number, fromName: string,
  destLat: number, destLng: number, destName: string,
  groupSize: number = 1, budget?: number
): Promise<{ status: string; step: any }> {
  const params: any = {
    from_lat: fromLat, from_lng: fromLng, from_name: fromName,
    dest_lat: destLat, dest_lng: destLng, dest_name: destName,
    group_size: groupSize,
  }
  if (budget !== undefined) params.budget = budget
  const { data } = await api.get('/routes/segment-step', { params })
  return data
}

export async function getWeather(lat: number, lng: number): Promise<{ condition?: string; temp?: number; humidity?: number } | null> {
  try {
    const { data } = await api.get('/search/weather', { params: { lat, lng } })
    if (data?.status === 'success' && data.weather?.condition) {
      const w = data.weather
      return { condition: w.condition, temp: w.temperature_celsius ?? w.temp, humidity: w.humidity }
    }
  } catch { /* ignore */ }
  return null
}

export async function getNews(lat?: number, lng?: number): Promise<any[]> {
  try {
    const { data } = await api.get('/search/current-events', { params: { lat, lng } })
    if (data?.status === 'success') return data.events || []
  } catch { /* ignore */ }
  return []
}

export async function getAllSegments(
  fromLat: number, fromLng: number, fromName: string,
  destLat: number, destLng: number, destName: string,
  groupSize: number = 1, budget?: number, maxDepth: number = 3
): Promise<AllSegmentsResponse> {
  const params: any = {
    from_lat: fromLat, from_lng: fromLng, from_name: fromName,
    dest_lat: destLat, dest_lng: destLng, dest_name: destName,
    group_size: groupSize, max_depth: maxDepth,
  }
  if (budget !== undefined) params.budget = budget
  const { data } = await api.get<AllSegmentsResponse>('/routes/all-segments', { params })
  return data
}


export async function getCompleteJourney(
  fromLat: number, fromLng: number, fromName: string,
  destLat: number, destLng: number, destName: string,
  groupSize: number = 1, budget?: number
): Promise<{ status: string; journey: any }> {
  const params: any = {
    from_lat: fromLat, from_lng: fromLng, from_name: fromName,
    dest_lat: destLat, dest_lng: destLng, dest_name: destName,
    group_size: groupSize,
  }
  if (budget !== undefined) params.budget = budget
  const { data } = await api.get('/routes/complete-journey', { params })
  return data
}

export default api
