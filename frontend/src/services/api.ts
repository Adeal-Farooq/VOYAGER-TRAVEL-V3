import axios from 'axios'
import type { SearchResponse, NearbyResponse, RoutePlanResponse, RidePriceResponse, EnrichSingleResponse, AllSegmentsResponse } from '../types'
import type { PlaceResult } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
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

export async function getRidePrices(source: string, destination: string): Promise<RidePriceResponse> {
  const { data } = await api.get<RidePriceResponse>('/search/ride-prices', { params: { source, destination } })
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

export async function getMiniPathOptions(
  sourceLat: number,
  sourceLng: number,
  destLat: number,
  destLng: number,
  groupSize: number = 1
): Promise<{ status: string; options: any }> {
  const { data } = await api.get('/routes/mini-path-options', {
    params: {
      source_lat: sourceLat,
      source_lng: sourceLng,
      dest_lat: destLat,
      dest_lng: destLng,
      group_size: groupSize,
    }
  })
  return data
}

export default api
