import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { LatLng, LiveContext, NewsItem, PlaceDetails, PlaceResult, RidePrice, SegmentResponse, WeatherNow } from "../types";

export type Mode = "search" | "atob" | "trip";

export interface JourneyState {
  segments: SegmentResponse | null;
  chosenLegs: unknown[];
  active: boolean;
  position: LatLng | null;
}

interface AppState {
  mode: Mode;
  setMode: (m: Mode) => void;
  dark: boolean;
  toggleDark: () => void;

  userLoc: LatLng | null;
  setUserLoc: (p: LatLng | null) => void;

  source: LatLng | null;
  dest: LatLng | null;
  setSource: (p: LatLng | null) => void;
  setDest: (p: LatLng | null) => void;
  swap: () => void;

  weather: WeatherNow | null;
  setWeather: (w: WeatherNow | null) => void;

  places: PlaceResult[];
  setPlaces: (p: PlaceResult[]) => void;
  selected: PlaceDetails | null;
  setSelected: (p: PlaceDetails | null) => void;
  showDiscovery: boolean;
  setShowDiscovery: (v: boolean) => void;

  prices: RidePrice[];
  setPrices: (p: RidePrice[]) => void;

  liveContext: LiveContext | null;
  setLiveContext: (c: LiveContext | null) => void;

  news: NewsItem[];
  setNews: (n: NewsItem[]) => void;

  journey: JourneyState;
  setJourney: (j: Partial<JourneyState>) => void;

  flyTo: LatLng | null;
  setFlyTo: (p: LatLng | null) => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("search");
  const [dark, setDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);
  const [userLoc, setUserLoc] = useState<LatLng | null>(null);
  const [source, setSource] = useState<LatLng | null>(null);
  const [dest, setDest] = useState<LatLng | null>(null);
  const [weather, setWeather] = useState<WeatherNow | null>(null);
  const [places, setPlaces] = useState<PlaceResult[]>([]);
  const [selected, setSelected] = useState<PlaceDetails | null>(null);
  const [showDiscovery, setShowDiscovery] = useState(false);
  const [prices, setPrices] = useState<RidePrice[]>([]);
  const [liveContext, setLiveContext] = useState<LiveContext | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [journey, setJourneyState] = useState<JourneyState>({
    segments: null,
    chosenLegs: [],
    active: false,
    position: null,
  });
  const [flyTo, setFlyTo] = useState<LatLng | null>(null);

  const toggleDark = () => {
    setDark((d) => {
      const next = !d;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  };

  const setJourney = (patch: Partial<JourneyState>) => setJourneyState((j) => ({ ...j, ...patch }));

  const swap = () => {
    setSource(dest);
    setDest(source);
  };

  const value = useMemo<AppState>(() => ({
    mode, setMode, dark, toggleDark,
    userLoc, setUserLoc,
    source, dest, setSource, setDest, swap,
    weather, setWeather,
    places, setPlaces,
    selected, setSelected, showDiscovery, setShowDiscovery,
    prices, setPrices,
    liveContext, setLiveContext,
    news, setNews,
    journey, setJourney,
    flyTo, setFlyTo,
  }), [mode, dark, userLoc, source, dest, weather, places, selected, showDiscovery,
      prices, liveContext, news, journey, flyTo]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export function scoreClass(score: number | null | undefined): "green" | "yellow" | "orange" | "red" {
  if (score == null) return "yellow";
  if (score >= 70) return "green";
  if (score >= 50) return "yellow";
  if (score >= 30) return "orange";
  return "red";
}

export function scoreColor(score: number | null | undefined): string {
  const c = scoreClass(score);
  const map = { green: "var(--score-green)", yellow: "var(--score-yellow)", orange: "var(--score-orange)", red: "var(--score-red)" };
  return map[c];
}
