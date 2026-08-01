export type Coord = [number, number];

// ============================================================ shared
export type ScoreClass = "green" | "yellow" | "orange" | "red";

export interface LatLng {
  lat: number;
  lng: number;
  name?: string;
}

// ============================================================ weather
export interface WeatherNow {
  temp_c: number | null;
  condition: string;
  weather_code?: number;
  humidity?: number;
  wind_kmh?: number;
  is_day?: boolean;
  rain_next_hour?: boolean;
  source?: string;
}

// ============================================================ news
export interface NewsItem {
  title: string;
  text?: string;
  url?: string;
  source?: string;
  category?: "traffic" | "weather" | "event" | "general";
  geo?: { name?: string; lat: number; lng: number } | null;
  summary?: string;
  ts?: number;
}

// ============================================================ places
export interface PlaceResult {
  place_id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  rating: number | null;
  user_rating_count: number | null;
  price_level?: number | null;
  business_status?: string | null;
  open_now?: boolean | null;
  weekday_hours?: string[];
  types?: string[];
  primary_type?: string | null;
  photo_name?: string | null;
  distance_km?: number | null;
  query?: string;
}

export interface Review {
  author_name: string;
  rating: number;
  text: string;
  date: string;
  source: string;
}

export interface PlaceDetails extends PlaceResult {
  phone?: string | null;
  website?: string | null;
  reviews: Review[];
  sentiment_avg?: number | null;
  reliability_score?: number | null;
  pin_class?: "green" | "yellow" | "red" | null;
  summary?: string;
  concerns?: string[];
}

// ============================================================ rides
export interface RidePrice {
  provider: string;
  mode: string;
  total: number;
  per_person: number;
  eta_min?: number | null;
  source: "live" | "estimated";
  note?: string;
}

// ============================================================ routes / segments
export interface PlaceModel {
  lat: number;
  lng: number;
  name: string;
}

export interface StopRef {
  name: string;
  lat: number;
  lng: number;
}

export interface HopOption {
  optionId: string;
  mode: "walk" | "bus" | "metro" | "train" | "ride" | string;
  routeNumber?: string;
  fromStop?: StopRef;
  destinationStop: StopRef;
  departureTime?: string;
  arrivalTime?: string;
  durationMin?: number;
  distanceKm?: number;
  fare?: number | null;
  perPersonFare?: number | null;
  walk_to_board?: number | null;
  geometry?: Coord[] | number[][] | null;
  geometrySource?: string;
  status?: string;
  isTopRecommended?: boolean;
  isMetroTransfer?: boolean;
  transitOptionsFromThisStop?: number;
  connectedFrom?: string | null;
  probeNext?: ProbeOption[];
  exceedsBudget?: boolean;
}

export interface ProbeOption {
  destinationStop: StopRef;
  mode: string;
  routeNumber?: string;
  departureTime?: string;
  arrivalTime?: string;
  fare?: number;
  isProbe?: boolean;
}

export interface Segment {
  from?: StopRef | null;
  to?: StopRef | null;
  title?: string;
  options: HopOption[];
}

export interface SegmentResponse {
  journey: Record<string, unknown>;
  segments: Segment[];
  probes?: ProbeOption[];
  warnings?: string[];
  journeyComplete: boolean;
  timeline?: unknown[];
}

export interface JourneyComplete {
  totalTimeMin?: number;
  totalFare?: number;
  segmentCount?: number;
  timeline?: unknown[];
}

// ============================================================ langgraph live context
export interface LiveContext {
  weather: WeatherNow;
  traffic: { ratio?: number; label?: string; source?: string; alerts?: string[] } | Record<string, never>;
  news: NewsItem[];
  prices: RidePrice[];
  reviews?: PlaceDetails | null;
  factors?: {
    time_of_day?: string;
    rain_next_hour?: boolean;
    traffic_label?: string;
    safety?: string;
  };
  errors?: string[];
}

export interface ScoredRoute {
  legs: unknown[];
  total_fare: number;
  total_duration_min: number;
  total_walk_km: number;
  transfers: number;
  per_person_fare: number;
  scores: Record<string, number | string>;
  cc_score: number;
  rank: number;
  best_match: boolean;
  explanation?: string | null;
}
