export interface PlaceResult {
  name: string
  address?: string
  lat: number
  lng: number
  place_type: string
  reliability_score?: number
  rating?: number
  review_summary?: string
  price_info?: string
  is_recommended: boolean
  distance_km?: number
  image_url?: string
  hotel_prices?: HotelPriceInfo
  reviews?: PlaceReview[]
  review_source?: string
}

export interface HotelPriceInfo {
  min_price: number
  max_price: number
  avg_price: number
  currency: string
  source: string
  review_score?: number
  brief_summary?: string
}

export interface RidePrice {
  provider: string
  mode: string
  price: number
  eta_minutes: number
  note?: string
  source?: string
}

export interface RidePriceResponse {
  status: string
  source: string
  destination: string
  prices: RidePrice[]
}

export interface RouteLeg {
  from: string
  to: string
  mode: string
  distance_km: number
  duration_minutes: number
  fare: number
  line?: string
  instructions?: string
  route_numbers?: string[]
  from_lat?: number
  from_lng?: number
  to_lat?: number
  to_lng?: number
}

export interface RouteOption {
  type: string
  total_fare: number
  total_duration_minutes: number
  total_distance_km: number
  total_walking_km: number
  overall_score: number
  score_explanation?: string
  legs: RouteLeg[]
  geometry?: any
  route_id?: string
  route_info?: string
  route_numbers?: string[]
  provider?: string
}

export interface RoutePlanResponse {
  status: string
  source: { lat: number; lng: number; name?: string }
  destination: { lat: number; lng: number; name?: string }
  routes: RouteOption[]
  total_options: number
  travel_insights?: string
  recommendations?: any
  weather?: any
}

export interface SearchResponse {
  status: string
  results: PlaceResult[]
  total: number
}

export interface NearbyResponse {
  status: string
  center: { lat: number; lng: number }
  radius_km: number
  results: PlaceResult[]
  total: number
}

export interface MetroStation {
  name: string
  line: string
  lat: number
  lng: number
  distance_from_prev_km?: number
}

export type AppMode = 'search' | 'atob' | 'trip'

export interface PlaceReview {
  user: string
  rating: number
  text: string
  date: string
}

export interface EnrichSingleResponse {
  status: string
  place: PlaceResult
}

export interface UserPreferences {
  budget?: number
  groupSize: number
  priority: 'cost' | 'time' | 'comfort' | 'balanced'
}

export interface MiniPathTransitOption {
  mode: string
  from: string
  to: string
  distance_km: number
  duration_minutes: number
  fare: number
  per_person?: number
  label?: string
  icon?: string
  group_capacity?: number
  path?: number[][]
  stop?: any
  station?: any
  instructions?: string
  from_lat?: number
  from_lng?: number
  to_lat?: number
  to_lng?: number
  stop_name?: string
  stop_lat?: number
  stop_lng?: number
  station_name?: string
  station_lat?: number
  station_lng?: number
}

export interface MiniPathOptions {
  source_walk_options: MiniPathTransitOption[]
  direct_ride_options?: MiniPathTransitOption[]
  source_to_transit: {
    bus: MiniPathTransitOption[]
    metro: MiniPathTransitOption[]
  }
  transit_ride_options?: {
    bus: MiniPathTransitOption[]
    metro: MiniPathTransitOption[]
  }
  transit_to_dest: {
    bus: MiniPathTransitOption[]
    metro: MiniPathTransitOption[]
  }
  direct_distance_km: number
}

export interface MiniPathSegment {
  from: string
  to: string
  selectedOption: MiniPathTransitOption | null
  availableOptions: MiniPathTransitOption[]
  segmentIndex: number
}

export interface BuiltRoute {
  segments: MiniPathSegment[]
  totalFare: number
  totalDuration: number
  totalDistance: number
}

export interface SegmentStepOption {
  mode: string
  label?: string
  icon?: string
  from: string
  to: string
  distance_km: number
  duration_minutes: number
  fare: number
  per_person?: number
  group_capacity?: number
  path?: number[][]
  arrives_at_stop?: boolean
  from_lat?: number
  from_lng?: number
  to_lat?: number
  to_lng?: number
}

export interface SegmentStopInfo {
  name: string
  lat: number
  lng: number
  type: string
}

export interface SegmentStepData {
  from: { lat: number; lng: number; name: string }
  dest: { lat: number; lng: number; name: string }
  direct_options: SegmentStepOption[]
  via_stops: {
    stop: SegmentStopInfo
    reach_options: SegmentStepOption[]
    from_stop_options: SegmentStepOption[]
  }[]
}

// New flat multi-segment types
export interface AllSegmentsResponse {
  status: string
  data: {
    source: { lat: number; lng: number; name: string }
    dest: { lat: number; lng: number; name: string }
    segments: AllSegment[]
    total_segments: number
  }
}

export interface AllSegment {
  segment_index: number
  type: string
  from: { name: string; lat: number; lng: number }
  direct_options: SegmentStepOption[]
  destinations: SegmentDestination[]
}

export interface SegmentDestination {
  stop: SegmentStopInfo
  distance_from_current: number
  reach_options: SegmentStepOption[]
  transit_options: TransitOption[]
  all_buses?: Record<string, string[]>
}

export interface TransitOption extends SegmentStepOption {
  route_number?: string
  bus_times?: { departure_time: string; route: string }[]
  transit_type?: string
  departure_time?: string
  arrival_time?: string
  final_options: SegmentStepOption[]
  next_transit?: TransitOption[]
  next_segment_index?: number
  needs_next_segment?: boolean
  dropoff_walk_min?: number
  dropoff_to_dest_km?: number
}

export interface NewsItem {
  title: string
  description: string
  impact: 'positive' | 'negative' | 'info'
  source: string
  timestamp: string
  lat?: number
  lng?: number
}

export interface MapRouteGeometry {
  type: 'route' | 'segment' | 'hover' | 'stop'
  coordinates: [number, number][]  // [lat, lng] pairs for map
  color: string
  weight?: number
  dashArray?: string
  label?: string
}
