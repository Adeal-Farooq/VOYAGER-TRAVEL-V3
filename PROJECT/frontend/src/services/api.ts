import axios from "axios";
import type {
  LatLng,
  LiveContext,
  NewsItem,
  PlaceDetails,
  PlaceResult,
  RidePrice,
  SegmentResponse,
  WeatherNow,
} from "../types";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api",
  timeout: 120_000,
});

export interface Api {
  searchPlaces: (q: string, lat?: number, lng?: number, signal?: AbortSignal) => Promise<PlaceResult[]>;
  searchNearby: (lat: number, lng: number, radiusM: number, categories?: string[], keyword?: string, signal?: AbortSignal) => Promise<PlaceResult[]>;
  enrichPlace: (place: PlaceResult) => Promise<PlaceDetails>;
  verifyPlace: (name: string, lat: number, lng: number) => Promise<PlaceResult | null>;
  weather: (lat: number, lng: number) => Promise<WeatherNow | null>;
  news: (lat?: number, lng?: number, keyword?: string, limit?: number) => Promise<NewsItem[]>;
  ridePrices: (origin: LatLng, dest: LatLng, groupSize: number) => Promise<RidePrice[]>;
  routeSegments: (src: LatLng, dst: LatLng, groupSize: number, budget: number, currentTime?: string | null, signal?: AbortSignal) => Promise<SegmentResponse>;
  segmentNext: (journey: unknown, chosenLegs: unknown[], groupSize: number, budget: number) => Promise<SegmentResponse>;
  routeContext: (src: LatLng, dst: LatLng, groupSize: number, budget: number, place?: PlaceResult | null) => Promise<LiveContext>;
  liveTrains: (from: string, to: string) => Promise<{ trains: unknown[]; source: string; note?: string }>;
}

export const api: Api = {
  async searchPlaces(q, lat, lng, signal) {
    const { data } = await http.get<{ places: PlaceResult[] }>("/search/places", {
      params: { q, lat, lng }, signal,
    });
    return data.places;
  },

  async searchNearby(lat, lng, radiusM, categories = [], keyword = "", signal) {
    const { data } = await http.get<{ places: PlaceResult[] }>("/search/nearby", {
      params: { lat, lng, radius_m: radiusM, categories: categories.join(","), keyword }, signal,
    });
    return data.places;
  },

  async enrichPlace(place) {
    const { data } = await http.post<PlaceDetails>("/search/enrich", { place });
    return data;
  },

  async verifyPlace(name, lat, lng) {
    const { data } = await http.post<{ verified: PlaceResult | null }>("/search/verify", { name, lat, lng });
    return data.verified;
  },

  async weather(lat, lng) {
    const { data } = await http.get<WeatherNow>("/search/weather", { params: { lat, lng } });
    return data && data.condition !== "unavailable" ? data : null;
  },

  async news(lat, lng, keyword = "", limit = 15) {
    const { data } = await http.get<{ items: NewsItem[] }>("/search/news", {
      params: { lat, lng, keyword, limit },
    });
    return data.items;
  },

  async ridePrices(origin, dest, groupSize) {
    const { data } = await http.post<{ prices: RidePrice[] }>("/rides/prices", {
      origin: { ...origin, name: origin.name ?? "" },
      destination: { ...dest, name: dest.name ?? "" },
      group_size: groupSize,
    });
    return data.prices;
  },

  async routeSegments(src, dst, groupSize, budget, currentTime = null, signal) {
    const { data } = await http.post<SegmentResponse>("/routes/segments", {
      source: { ...src, name: src.name ?? "" },
      destination: { ...dst, name: dst.name ?? "" },
      group_size: groupSize,
      budget,
      current_time: currentTime,
    }, { signal });
    return data;
  },

  async segmentNext(journey, chosenLegs, groupSize, budget) {
    const { data } = await http.post<SegmentResponse>("/routes/segment-next", {
      journey,
      chosen_legs: chosenLegs,
      group_size: groupSize,
      budget,
    });
    return data;
  },

  async routeContext(src, dst, groupSize, budget, place = null) {
    const { data } = await http.post<LiveContext>("/langgraph/route-context", {
      source: { ...src, name: src.name ?? "" },
      destination: { ...dst, name: dst.name ?? "" },
      group_size: groupSize,
      budget,
      place: place ?? null,
    });
    return data;
  },

  async liveTrains(from, to) {
    const { data } = await http.get<{ trains: unknown[]; source: string; note?: string }>("/routes/live-trains", {
      params: { from_station: from, to_station: to },
    });
    return data;
  },
};
