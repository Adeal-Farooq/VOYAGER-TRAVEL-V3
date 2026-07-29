# VOYAGER — Complete Feature Documentation

> A Bengaluru-focused urban mobility & place discovery platform combining real-time transit routing, ride hailing, AI recommendations, and place intelligence under one glassmorphism UI.

---

## 1. THREE CORE MODES (Navigation Tabs)

### 1.1 Search Mode
The default landing mode for discovering places in Bengaluru.

**Sub-features:**
- **Place Search** — Text-based search for any place/landmark in Bengaluru. Uses Google Maps Places API with keyword overlap verification and 15km Bangalore radius filter. Shows results as cards with name, address, distance, type badge, and star rating.
- **Autocomplete Suggestions** — As user types (≥2 chars), a debounced dropdown shows real-time search suggestions after 300ms. Clicking a suggestion triggers search automatically.
- **Search Specific tab** — The default search tab where user types a query and gets place results. Results display reliability score pill (0-100% with color coding: green ≥80, yellow ≥60, orange ≥40, red <40).
- **Search Nearby tab** — A separate tab that shows places around a chosen location. User picks a category chip (19 categories: ATM, Bank, Hospital, Pharmacy, Restaurant, Cafe, Hotel, Mall, Petrol Pump, EV Station, Supermarket, Park, Bus Stop, Metro, Temple, Police, School, Gym, Cinema) and a radius slider (0.5-10km). Results are numbered markers on map.
- **Place Cards** — Each result card shows: image (if available), category icon, place name, address, distance, type badge, hotel price range (if applicable), AI review summary, expandable real user reviews (3 shown, with star ratings, username, date, text). Two action buttons: "Details" and "Navigate".
- **Card Color Coding** — Card background and left border change color based on reliability score range (green/yellow/orange/red). Selected/highlighted cards get primary-fixed background.
- **Numbered Markers** — Nearby search results appear as numbered circular markers on the map with distinct colors (10-color cycle), matching the card index number.

### 1.2 A-to-B Mode
Route planning between source and destination with three travel sub-modes.

**Sub-features:**
- **Source Input** — Text input with autocomplete suggestions and OK button. Shows green check icon when source is confirmed. Green border highlight. Can type "Current Location" to use GPS position. Clear button to reset.
- **Destination Input** — Same as source but with red/branding. OK button resolves the typed query to coordinates. Swap button between source and destination. Map flies to destination when confirmed.
- **Travel Sub-Modes:**
  - **Public / Online Transport** — For public transit + ride hailing. Further splits into:
    - **Multi-Hop Transit** — Interactive step-by-step transit planner with bus/metro/train/walk segments. Opens a full-screen modal showing all segments.
    - **Direct Ride** — Shows ride-hailing options (Uber, Ola, Rapido, Auto) with live prices. User can expand/collapse price list.
  - **Drive** — Personal car mode. Shows driving route with estimated fuel cost based on petrol price and mileage. Uses local OSRM engine for real road-following geometry.
  - **Walk** — Walking mode for shorter distances. Simple point-to-point route with interpolated path and estimated walking time.
- **Group Size & Budget** — Numeric inputs for number of travelers and maximum budget (₹). Budget filters out routes exceeding the limit.
- **"Find Routes" Button** — Triggers route planning. Shows loading spinner with animation while computing.
- **Route Cards** — Each route displays: mode icon, provider/mode label, total fare (₹), duration, distance, walking distance, bus route numbers (if applicable), overall score (0-99%) with colored bar, and score explanation.
- **Best Match Badge** — Top-ranked route gets a green "Best Match" badge and score pill.
- **Step-by-Step Navigation** — Clicking a route card shows "View Steps" button, then step-by-step leg viewer with mode icons, from→to stops, duration, distance, fare per leg, and instructions text. "Next" button advances through legs. Final step shows "Arrived at Destination" with journey complete UI.
- **"Start Journey" Button** — Begins GPS live tracking (see GPS Tracking feature).
- **Show All Options** — Collapsible section to expand all routes beyond the top 5.
- **Multi-Stop Waypoints** — Route planning can accept intermediate waypoints between source and destination for complex multi-stop journeys.

### 1.3 Trip Mode
A trip management and journey monitoring dashboard.

**Sub-features:**
- **AI Travel Insight Box** — Static informational card explaining the trip planner's capabilities.
- **Create New Trip Button** — Dashed-border button that switches to A-to-B mode to start planning.
- **Your Trips Section** — Shows planned/saved trips (currently shows empty state with instructional message).
- **Active Journey Panel** — When GPS tracking is active, shows a panel with: pulsing green dot indicator, live coordinates (lat, lng), and "End Journey" button with red stop icon.
- **Multi-Day Planning** — Infrastructure for day-based trip planning (day tabs exist but feature is scaffolded).

---

## 2. MAP & VISUALIZATION

### 2.1 Interactive Map (Leaflet)
The central visualization layer using OpenStreetMap tiles.

**Sub-features:**
- **Tile Layer** — Standard OpenStreetMap tile layer with proper attribution.
- **Zoom Controls** — Default Leaflet zoom +/- buttons with glassmorphism styling.
- **Search Radius Circle** — Semi-transparent blue circle on map showing the nearby search radius area (0.5-10km).
- **User Location Marker** — Blue pulsing dot with ring animation showing user's current GPS location. Shows only when GPS is available and tracking is not active.
- **Live Tracking Marker** — Same as user location marker but active during journey tracking.

### 2.2 Markers & Pins
- **Place Markers** — Custom divIcon markers with colored background (based on reliability score), white Material Symbol icon, and white border. Each marker shows the place type icon (hospital, restaurant, bus stop, etc.).
- **Numbered Markers** — Circular markers with numbers 1-N in sequence for nearby search results. Each uses a distinct color from a 10-color palette. Clicking opens a popup with place name.
- **Highlighted Marker** — The currently selected/active place gets a larger marker (44px) with pulsing ring animation, star icon, and 3px white border.
- **Source Marker** — Green marker with "trip_origin" Material Symbol at start location.
- **Destination Marker** — Red marker with pulsing ring animation, "location_on" icon at destination.
- **News Event Markers** — Small circular markers with "!" icon at news event locations. Color-coded: green (positive), red (negative), blue (info). Clicking shows title and description popup.
- **Selected Place Marker** — Purple marker with star icon and pulsing ring for places selected from search but not in current markers list.

### 2.3 Route Geometry & Paths
- **Route Polylines** — Colored lines on map showing route paths. Colors match mode (primary for transit, secondary for walking).
- **Segment Polylines** — Individual route legs shown as separate polylines with different colors (primary for main transit, secondary for walking, orange for connecting transit, amber/orange for final drop-off).
- **Dashed Lines** — Walking segments shown as dashed polylines (8,4 dash pattern) with lighter weight (3 vs 4 for transit).
- **Stop Circle Markers** — Small circle markers (radius 6) at transit stop locations along the route, with popup labels.
- **Accumulated Paths** — In multi-hop mode, all confirmed segment paths accumulate on the map showing the full journey.

### 2.4 Map Controls
- **Live Location Button** — Bottom-right floating button to re-center map on user's current position. Shows pulsing animation when tracking is active. Blue default, green when tracking.
- **Mouse Interaction** — Click on markers opens popup with place info. Map pan/zoom standard behavior.

---

## 3. SEARCH & DISCOVERY

### 3.1 Place Search Engine
- **Multi-Source Search** — Primary source is Google Maps Places API. Falls back to DuckDuckGo search and local database when Google API is unavailable.
- **Coordinate Verification** — Search results are verified to be within Bangalore (15km radius of center by default, 50km for non-Bangalore queries).
- **Keyword Overlap Filter** — ≥40% keyword overlap required between query and result name/address to filter irrelevant results.
- **Result Deduplication** — Duplicate coordinates are filtered out (rounded to 4 decimal places).
- **24-hour Search Cache** — Results are cached for 24 hours to improve performance and reduce API calls.
- **Reliability Scoring** — Each place gets a 0-100% reliability score computed from Google rating (rating/5 × 100). Never trusts external scores.
- **Place Enrichment** — On "Details" click, a place gets enriched asynchronously: fetches real reviews, photos, hotel prices, and generates AI review summary. A loading skeleton UI is shown during enrichment (shimmer animation with place name).

### 3.2 Place Details (Discovery Panel)
A right-side glass panel that slides over the map showing comprehensive place information.

**Sub-features:**
- **Hero Image** — Large place photo (160px height) with rounded corners. Falls back gracefully on error.
- **Place Name Header** — Place name with reliability score pill (0-100%, color-coded, with verified/warning icon).
- **Type Badge** — Place type displayed in uppercase with letter-spacing.
- **Address** — Full address with location_on icon.
- **Rating Display** — Star rating with numeric value (e.g., 4.2) and "rating" label.
- **Distance Info** — "X km away" display.
- **Hotel Price Range** — If available, shows min-max price per night with average, currency, and brief summary in a styled card with primary-colored left border.
- **AI Review Summary Box** — Colored box (green/yellow/red based on reliability score) containing AI-generated summary of all reviews. Includes "concerns" section in red if any negative patterns detected.
- **Recent Reviews Section** — Up to 5 individual reviews showing: author name, star rating (emojis), date, and review text. Styled as card list with subtle background.
- **Action Buttons:**
  - "Show on Map" — Button with map icon, outlined style, flies map to place location.
  - "Navigate Here" — Filled primary button that switches to A-to-B mode and pre-fills destination with this place.

### 3.3 Nearby Place Categories
19 searchable categories with corresponding Material Symbols:
- All, ATM, Bank, Hospital, Pharmacy, Restaurant, Cafe, Hotel, Mall, Petrol Pump, EV Station, Supermarket, Park, Bus Stop, Metro Station, Temple, Police, School, Gym, Cinema.

Categories are displayed as horizontally scrollable chips with active state styling.

### 3.4 Search Suggestions
Autocomplete suggestions fetched from backend (Google Maps Autocomplete API or local data) with 300ms debounce. Displayed in a glassmorphism dropdown below the search input.

---

## 4. ROUTE PLANNING — PUBLIC TRANSIT

### 4.1 Multi-Hop Transit Engine
The most complex feature — plans journeys using Bangalore's public transit network.

**Sub-features:**
- **A\* Graph Routing** — Primary routing uses an A\* graph algorithm built from real GTFS (General Transit Feed Specification) data. The graph contains ~2900 nodes (bus stops + metro stations) and ~54,000 edges (bus routes, metro lines, walk connections).
- **Route Types Generated:**
  - **Direct Bus** — Single bus route connecting nearby source stop to nearby destination stop (common routes).
  - **Metro** — Namma Metro route from source station to destination station on same line.
  - **Metro Interchange** — Metro route requiring line change at an interchange station (e.g., Purple→Green Line at Majestic).
  - **KIA Bus** — KIA Vayu Vajra airport bus routes.
  - **Bus→Metro** — Walk/bus to metro station, metro ride, then walk from destination station.
  - **Metro→Bus** — Walk to metro, metro ride, then bus from destination station.
  - **Multi-Modal** — Complex combinations of bus + metro + bus with interchange.
  - **A\* Enriched** — The primary generator, combining any number of bus/metro/walk hops optimized by A\*.
  - **Walk-Only** — When distance ≤2km, a free walk option is provided.
- **GTFS Data Integration** — Real Bangalore BMTC GTFS data: 5077 stops, 7271 shapes, 429,882 time entries. Loaded lazily (not at server startup). Cached via pickle for fast subsequent startups (0.65s cache load).
- **Bus Stop Name Resolution** — Fuzzy matching to resolve user-entered stop names against GTFS stop names. Uses trigram pre-filtering + `get_close_matches` for performance. Pre-resolves at load time with caching (1696/2972 names resolved).
- **Direction Filtering** — Routes are filtered to ensure they go towards the destination using cosine angle between route direction and destination vector. Threshold relaxed to 0.3 for better coverage.
- **Time-Based Filtering** — Only future departures are shown (after current time). Falls back to all departures if filtering returns empty.
- **Route Number Cleaning** — GTFS route numbers are cleaned of terminal suffixes (e.g., "MF-28 JKLO-ISROQ-LGRNB" → "MF-28").

### 4.2 Interactive Segment Planner (SegmentFlowView)
A modal-based step-by-step transit planner.

**Sub-features:**
- **Breadcrumb Trail** — Shows the entire planned journey as a chain: Source → [Bus/Metro] → Stop Name → ... → Destination. Each confirmed step is color-coded with mode icons.
- **Step 1: Pick Destination Stop** — User selects which bus stop/metro station to go to next. Shows horizontal scrollable cards with:
  - Stop name and type icon
  - Distance from current location
  - Walk option (distance, duration, "Free" label)
  - Ride option (cab/auto) with fare
  - Number of transit options available from that stop
- **Step 2: Pick Transit Option** — After selecting a stop, shows available transit options from that stop. Each option card shows:
  - Mode icon (bus/metro/train/walk)
  - Route number with color coding (metro: purple/green line colors)
  - Fare and duration
  - From→To stop names
  - Departure/arrival times
  - Time status badge (running/not running with green/red indicators)
  - Next departure times (up to 6) for buses
  - Alternative suggestions when bus is not running (late night fallback)
  - Next transit chain (e.g., bus→metro continuation)
  - Final drop-off options (walk/cab/auto from transit stop to actual destination)
- **Time-of-Day Safety Advisories** — Based on current time, shows contextual warnings:
  - Late night (22:00-01:00): "It's late — cab/auto is safest"
  - Early morning (01:00-06:00): "Early morning — bus service may be limited"
- **Confirm & Continue** — Button to confirm each transit segment. Automatically attempts to find next segment via live extension API. Shows "Finding onward connections..." with spinner during extension.
- **Accumulated Path Display** — Each confirmed segment adds its path to the map, building up the full journey visualization.
- **Journey Complete Screen** — When all segments confirmed, shows: "You have reached [destination]" with total time, total fare, segment count, and list of all segments taken.
- **Reset Button** — Clears all selections and starts over.
- **Suggested Route Paths** — Pre-computed multi-hop route suggestions shown as horizontal cards with:
  - Route number and total fare header
  - Individual legs with mode icons and stop names
  - Running status (strikethrough if not running)
  - Total duration, distance, and transfer count

### 4.3 Scoring & Ranking (TOPSIS)
All routes are ranked using TOPSIS (Technique for Order Preference by Similarity to Ideal Solution) multi-criteria decision analysis.

**Scoring Factors:**
- **Total Fare** — Lower fare is better (inverse weight)
- **Total Duration** — Shorter time is better (inverse weight)
- **Total Walking Distance** — Less walking is better (inverse weight)
- **Number of Transfers** — Fewer transfers is better (inverse weight)
- **Weather Impact** — Dynamic adjustment: rain penalizes high-walk routes (+15 penalty if walk >1km), night penalizes bus/walk modes, group size ≥4 favors car/cab (+10 bonus). Rain slightly boosts car/cab (+5).
- **Time-of-Day Adjustments** — Night (before 6 AM or after 8 PM): -10 if walk >1.5km, -8 for ordinary bus, +8 for cab/car.
- **Final Score** — Normalized 0-99, sorted descending. Ties broken by lower fare.

### 4.4 Transit Data Sources
- **BMTC GTFS** — Bangalore Metropolitan Transport Corporation official GTFS data (stops, routes, trips, stop_times, shapes).
- **Namma Metro Network** — CSV-based metro station data with line information (Purple Line, Green Line).
- **KIA Bus Routes** — KIA Vayu Vajra airport bus routes.
- **Railway Stations** — Karnataka railway station codes (22 stations) with real-time train data from eRail.in API.
- **Transit Fares** — Static fare tables loaded from JSON.

### 4.5 Multi-Stop Waypoints
Route planning can accept intermediate waypoints. The route is split into segments, each planned independently using public transit, then recombined into a single multi-stop route with combined totals and scores.

---

## 5. RIDE HAILING

### 5.1 Ride Pricing Engine
Real-time ride fare estimation for Bangalore.

**Sub-features:**
- **Ride Types Covered:**
  - Uber Go / Ola Mini (₹12/km, 3 seats)
  - Ola Mini (₹12/km, 3 seats)
  - Uber Priority / Ola Prime Sedan (₹24/km, 3 seats)
  - Uber XL / Ola XL (₹30/km, 6 seats)
  - Auto Rickshaw (₹9/km, 3 seats)
  - Rapido Bike / Uber Moto (₹5/km, 1 seat)
  - Uber for Women (₹12/km, 3 seats)
  - Uber Pet / Premier (₹18/km, 3 seats)
- **Fare Calculation** — Base fare + per-km charge + per-minute charge, with minimum fare floor. Applies surge multiplier based on time of day.
- **Live Pricing Sources:**
  1. **SerpAPI Google Maps Directions** — Attempts to scrape real prices from Google Maps.
  2. **Formula Estimation** — Falls back to Karnataka govt-mandated rates with time-based surge (morning rush 1.4x, evening 1.5x, night 1.2x, late night 1.8x).
- **Per-Person Pricing** — Total is vehicle fare (not multiplied by passengers). Per-person = total / group size. Fixed a bug where fare was incorrectly multiplied by passenger count.
- **Surge Factor** — Based on time of day and weekday vs weekend. Morning peak (8-10AM): 1.4x, Evening (5-8PM): 1.5x, Late night (11PM-5AM): 1.8x.

### 5.2 Ride Price Display
- **Price Cards** — Each ride option shows: provider name, mode badge, price (₹), ETA in minutes, and optional distance note.
- **Source Label** — Shows whether price is "Live" or "Estimated" with distance context.
- **Selection** — Clicking a ride option highlights it and shows the driving route geometry on map.
- **Expand/Collapse** — Ride prices section can be shown/hidden with toggle button.
- **Integration with Route Planning** — Ride prices are fetched alongside transit routes and displayed in the "Direct Ride" sub-mode.

---

## 6. REAL-TIME & LIVE FEATURES

### 6.1 GPS Live Tracking
- **Start Journey** — Begins GPS tracking using browser's Geolocation API with high accuracy mode.
- **WatchPosition** — Continuous position updates via `watchPosition` (5s max age, 10s timeout).
- **Live Marker** — Blue pulsing dot updates position in real-time on map.
- **Active Journey Panel** — Shows live coordinates in Trip mode.
- **End Journey** — Stops tracking, clears watch, removes live marker.
- **Auto-location on Startup** — Attempts to get user location on page load, flies map to user position at zoom 14.

### 6.2 Weather Integration
- **Data Source** — Open-Meteo API (free, no key required).
- **Header Display** — Current temperature (°C) with weather condition icon (sunny/cloudy/rainy/foggy) in the top bar.
- **Route Scoring Impact** — Weather affects route scores:
  - Rain: walking routes penalized (-15 to -20), car/cab boosted (+5)
  - Rain + walk >1km: -15 score
  - Rain + walk/bike mode: -20 score
- **Auto-fetch** — Weather fetched automatically on app start for user's location.
- **Endpoint** — Available via `/api/search/weather` API.

### 6.3 Live Traffic Overlay
- **Traffic Data** — Based on time-of-day model (not real-time API): weekday peak speeds 10-12 km/h, off-peak 25-30 km/h, weekend/holiday 28-32 km/h.
- **Road Network** — Bangalore road GeoJSON loaded into memory. Roads classified into 9 types (motorway→unclassified) with color coding (red→green spectrum).
- **Congestion Levels:** — heavy (<15 km/h, red), moderate (15-30 km/h, yellow), light (>30 km/h, green).
- **Color Darkening** — During peak hours, major roads (motorway/trunk/primary/secondary) are darkened by 20 for visual emphasis.
- **Peak Detection** — 8-10 AM and 5-8 PM weekdays considered peak.
- **Random Variation** — Adds ±2 km/h random variation for realism.

### 6.4 Live News & Events
- **Data Sources** — Reddit API (r/bangalore) via Reddit client.
- **Notification Popup** — A floating glass panel on the map showing live updates. Has "LIVE" badge with pulsing green dot.
- **Categories:** — Traffic (red left border), Weather (blue), Events (yellow), General (gray).
- **Auto-Refresh** — Fetches every 2 minutes. Merges new items with existing (deduplication by title, max 15 items).
- **Dismiss** — User can dismiss the popup.
- **Geo-tagged News** — News items with coordinates appear as map markers with color-coded "!" icons.

### 6.5 Live Train Data
- **Data Source** — eRail.in Indian Railways API.
- **Station Coverage** — 22 Karnataka station codes mapped (SBC, YPR, BLR, etc.).
- **Route Fallbacks** — 7 city-pair fallbacks (e.g., Bengaluru→Mysuru, Bengaluru→Chennai) with hardcoded train options.
- **Integration** — Train options are offered alongside bus and metro in transit routing.

---

## 7. AI & LANGUAGE FEATURES

### 7.1 LangGraph Agent
A LangGraph-style reasoning agent with tool-calling capabilities.

**Sub-features:**
- **Intent Detection** — Analyzes query to determine which tools to call (search, ride, weather, news, hotels, reviews, geo, etc.).
- **Multi-Tool Parallel Execution** — Identifies independent tools and calls them concurrently.
- **LLM Integration** — Uses OpenRouter API (primary) with Gemini fallback. Models tried: primary OpenRouter model → fallback models → Gemini models.
- **Automatic Review Fetching** — After tool execution, auto-fetches reviews for any discovered place names.
- **Synthesis** — Combines all tool results into a structured response.
- **JSON Mode** — LLM responses are forced to JSON format for reliable parsing.
- **Timeout Handling** — 30s timeout per LLM call, fallback across models on failure.

### 7.2 AI Chat
- **Endpoint** — `/api/search/ai-chat` with user message and optional location context.
- **Use Cases** — General travel queries, place recommendations, transit information.
- **Context Awareness** — Can receive user's lat/lng for location-aware responses.

### 7.3 AI Review Summaries
- **Generation** — Real Google Reviews fetched via SerpAPI → proxy-scrape → fallback chain.
- **Summary** — AI-generated concise review summary shown in colored box.
- **Concerns Detection** — Negative review patterns extracted as "concerns" shown in red.
- **Review Display** — Individual reviews shown with username, star rating, date, and text.

### 7.4 AI Travel Recommendations
- **Context** — Route planning API returns AI-generated travel recommendations based on source, destination, group size, and budget.
- **Weather Impact** — Route response includes weather data and scoring adjustments.

### 7.5 AI Hotel Price Estimation
- **Source** — SerpAPI Google Hotels / Google Maps.
- **Display** — Price range (min-max), average, and brief summary shown in place cards and discovery panel.

---

## 8. DATA COLLECTION & SCRAPERS

### 8.1 Ride Scraper
- **SerpAPI Directions** — Attempts to scrape live ride prices from Google Maps Directions API via SerpAPI.
- **Formula Fallback** — Karnataka govt-mandated rates with time-based surge.
- **Distance Calculation** — Uses OSRM or Haversine for distance/duration estimation.

### 8.2 Google Reviews Scraper
- **Multi-Layer Fallback:**
  1. SerpAPI place search → place_id → place_details (reviews)
  2. Cache with versioning (`_CACHE_VERSION = 2`)
  3. TTL-based cache with 24-hour expiry
- **Review Fields** — username, description/rating, date. (Not user.name/snippet which are different SerpAPI keys).

### 8.3 News Scraper
- **Reddit API** — Fetches latest posts from r/bangalore and related subreddits.
- **DuckDuckGo Scraper** — Supplementary search for current events and traffic news.

### 8.4 JustDial Scraper
- **Note:** Currently not functional (site blocking scrapers).

### 8.5 Image Service
- Fetches place photos from Google Maps/SerpAPI for visual display in cards and discovery panel.

### 8.6 DuckDuckGo Scraper
- Supplemental search engine for news and general queries when primary sources fail.

---

## 9. DATA & DATABASE

### 9.1 Transit Database (Singleton)
In-memory database initialized at startup containing:
- **Metro Stations** — 50+ stations across Purple and Green lines with coordinates, lines, and interchange info.
- **Bus Stops** — ~3000+ BMTC bus stops with names, coordinates, and route lists.
- **KIA Routes** — Airport bus routes with stops and schedules.
- **Transit Fares** — Static fare tables for bus and metro.
- **Railway Stations** — Karnataka railway stations.
- **Spatial Indexes** — R-tree style spatial indexes for fast nearby-stop lookups (bus, metro, rail).

### 9.2 GTFS Cache
- **Data** — 7271 shapes, 5077 stops, 429882 time entries from BMTC GTFS.
- **Caching** — Pickle serialization for fast startup (~0.65s load vs ~40s first load).
- **Name Map** — Pre-resolved stop name mapping (1696/2972 names) cached in pickle.

### 9.3 Search Cache
- **TTL** — 24-hour cache for place search results.
- **Key Format** — Query + rounded coordinates (2 decimal places).
- **Use Case** — Reduces Google Maps API calls for repeated searches.

---

## 10. UI/UX & DESIGN SYSTEM

### 10.1 Glassmorphism Design
- **Glass Class** — `backdrop-filter: blur(24px) saturate(1.4)` with semi-transparent backgrounds.
- **Glass-Strong** — Higher opacity (0.92) with shadow for emphasis.
- **Consistent Border** — `rgba(198,197,212,0.3)` border on all glass elements.

### 10.2 Dark Mode
- **System Default** — Follows `prefers-color-scheme` media query.
- **Toggle** — Manual toggle button in header bar with sun/moon icon.
- **Full Theme** — Complete dark color palette: dark surfaces (#121212), adjusted shadows, inverted primary colors, lighter text on dark backgrounds.
- **CSS Variable Approach** — Theme applied via `.dark` class on `<html>`, overriding CSS custom properties.

### 10.3 Responsive Design
- **Mobile Breakpoint** (768px):
  - Sidebar collapses to 100% width, 40vh max height, positioned absolutely.
  - Bottom nav tabs hide text labels (icons only).
  - Header location text hidden.
  - News popup shrinks.
- **Sidebar** — Fixed 420px width on desktop.

### 10.4 Animations
- **Slide Up** — Elements entering view (cards, items).
- **Fade In** — Panels and popups.
- **Scale In** — Modal content and interactive elements.
- **Pulse Ring** — User location marker, destination marker, highlighted markers.
- **Pulse Dot** — Live indicator, tracking button.
- **Shimmer/Skeleton** — Loading placeholders with gradient animation.
- **Spin** — Loading spinner for async operations.
- **Hover Scale** — Map markers scale up to 1.15× on hover.

### 10.5 Bottom Pill Navigation
- Fixed at bottom center, glassmorphism background, rounded pill shape.
- Three tabs: Search, A→B, Trip.
- Active tab gets primary background with shadow.
- Transitions between modes clear route geometry.

### 10.6 Header Bar
- Clock with 12-hour format, updating every second.
- Weather widget with condition icon and temperature.
- Location name (reverse geocoded from Nominatim API).
- Dark mode toggle button.
- All in a glassmorphism bar with subtle bottom border.

### 10.7 Typography & Icons
- **Font** — Inter (Google Fonts) for body text.
- **Icons** — Material Symbols (variable font) with `wght` and `FILL` axes for dynamic styling. Fill mode for active/selected states.
- **Material Symbol Mapping** — Each place type and transport mode mapped to specific Material Symbol icons.

### 10.8 Color System
- **Primary** — Deep indigo (#000666 / #bac1ff in dark mode).
- **Secondary** — Green (#006e1c / #6cd97c in dark mode).
- **Error** — Red (#ba1a1a / #ffb4ab in dark mode).
- **Score Colors** — Green (≥80), Yellow (≥60), Orange (≥40), Red (<40).
- **Mode Colors** — Transit (primary), Walk (secondary), Ride (various).

---

## 11. BACKEND API

### 11.1 Route Planning Endpoints
- **POST /api/routes/plan** — Main route planning. Accepts source, destination, mode (public/personal/walking), group size, budget, and optional waypoints. Returns sorted routes with scores, legs, weather, and recommendations.
- **GET /api/routes/all-segments** — Multi-hop segment generation with OSRM paths and live pricing.
- **GET /api/routes/segment-step** — Single step segment options for the interactive planner.
- **GET /api/routes/extend-segment** — Live extension of multi-hop journey to next segment.

### 11.2 Search & Discovery Endpoints
- **GET /api/search/places** — Search places with query and optional location.
- **GET /api/search/nearby** — Category-based nearby search with radius.
- **GET /api/search/suggestions** — Autocomplete suggestions.
- **GET /api/search/verify-place** — Verify place existence and get rating.
- **GET /api/search/reviews** — Get real Google reviews for a place.
- **POST /api/search/enrich-place** — Enrich place with reviews, photos, hotel prices.
- **GET /api/search/ride-prices** — Live ride price estimation.
- **GET /api/search/current-events** — Current events and news for location.
- **GET /api/search/weather** — Current weather conditions.
- **GET /api/search/ai-chat** — AI chat with location context.

### 11.3 LangGraph Endpoint
- **POST /api/langgraph/ask** — Full LangGraph reasoning loop. Accepts query and optional context. Returns synthesized tool results.

### 11.4 Transit Data Endpoints
- **GET /api/routes/metro-stations** — Metro station list with line filter.
- **GET /api/routes/bus-stops** — Bus stops with optional proximity search.
- **GET /api/routes/kia-routes** — KIA airport bus routes.
- **GET /api/routes/transit-fares** — Static transit fare tables.
- **GET /api/routes/live-prices** — Live ride prices between named locations.

### 11.5 Traffic & News Endpoints
- **GET /api/routes/traffic-overlay** — Traffic congestion GeoJSON for map overlay.
- **GET /api/routes/news** — Travel news relevant to route.

### 11.6 Health & Status
- **GET /** — App status with station counts.
- **GET /health** — Health check with DB initialization status.

---

## 12. BACKEND ARCHITECTURE

### 12.1 Service Layer
- **TransitService** (~579 lines) — Composes all transit modules. Orchestrates route generation, scoring, path enrichment, and ride pricing.
- **TripSegmentBuilder** (~1283 lines) — Multi-hop transit segment routing with GTFS, bus→metro→walk chaining. Handles 17 methods including direction checking, stop resolution, and segment step options.
- **TransitGraph** — TransitAstarGraph class for A\* graph building with Haversine distance and distance caching.
- **TransitScoring** — TOPSIS multi-criteria scoring for route ranking.
- **TransitPaths** — OSRM path fetching and path interpolation.
- **TransitConfig** — Constants (ride types, train data, hubs) and pure functions (geo math, GTFS helpers, direction filters).
- **FareEngine** — Centralized fare calculation with surge multiplier.
- **GeocodingService** — Place search, nearby search, suggestions, verification, enrichment.
- **GTFSService** — GTFS data loader with fuzzy name matching and caching.
- **ImageService** — Place photo fetching.
- **TrainService** — Real-time train data from eRail.in API.

### 12.2 External Clients
- **GoogleMapsClient** — Places API, Geocoding API.
- **SerpAPIClient** — Google Search, Places, Hotels via SerpAPI.
- **WeatherClient** — Open-Meteo API.
- **RedditClient** — Reddit API for news and events.

### 12.3 OSRM Integration
- **OSRM Car** (port 5000) — Real road-following driving routes via Docker.
- **OSRM Foot** (port 5001) — Walking routes (currently OOM during build).
- **Fallback** — When OSRM unavailable, paths are interpolated (straight-line with intermediate points).

### 12.4 Performance Optimizations
- **Lazy GTFS Loading** — GTFS loads on first route request, not at server startup (avoids ~40s block).
- **Haversine Distance** — Used instead of `geodesic` for A\* graph building with distance caching (11.6s → 2.2s).
- **Fuzzy Match Optimization** — Trigram pre-filter + `get_close_matches` instead of SequenceMatcher loop (79s → 7.7s).
- **Pickle Cache** — GTFS data and name maps cached as pickle files for sub-second reloads.
- **A\* Graph Pre-building** — Graph built at `TransitService.__init__` so first request is instant.
- **Concurrent Path Fetching** — OSRM paths and live prices fetched concurrently with semaphore limits (8 concurrent).
- **Timeouts** — All external calls have strict timeouts (1.5s for OSRM health, 3s for path fetch, 5-30s for route generation).

---

## 13. FRONTEND ARCHITECTURE

### 13.1 State Management (AppContext)
- React Context-based global state with 30+ state variables.
- Manages: mode, location, markers, routing state, journey tracking, dark mode, weather, discovery panel, prices.
- Provides: `startJourney`, `stopJourney`, `openDiscovery`, `closeDiscovery` callbacks.

### 13.2 API Layer
- Axios-based client with 120s timeout.
- All endpoints typed with TypeScript interfaces.
- AbortController support for cancelable requests.

### 13.3 Google Fonts
- Inter (typeface) + Material Symbols (icons) loaded via Google Fonts.

---

## 14. KNOWN LIMITATIONS & EDGE CASES

### 14.1 Data Gaps
- 14/2972 bus stop names have no GTFS match (acronyms like "hnrj", "ggmc").
- Yelahanka metro station missing from metro network data (Green Line extension).
- JustDial scraper non-functional.

### 14.2 Performance
- Bus stop name pre-resolve takes ~7.7s on first run (cached thereafter).
- OSRM foot (walking) OOM-killed during Docker build; walking uses interpolated paths.
- Multi-hop transit timeout set to 30s for route generation, 10s for OSRM batch.

### 14.3 External Dependencies
- SerpAPI requires API key for real reviews/prices.
- OpenRouter/Gemini API key required for AI features.
- Google Maps API key for place search.
- All real data sources have fallback chains to prevent empty responses.

### 14.4 Behavioral Edge Cases
- When metro stations are not near source, all metro stations are searched for optimal bus→metro transfer.
- When future-departure GTFS filtering returns empty, falls back to all departures.
- 800m visited-stop radius to prevent circular routing.
- Routes with same score sorted by lower fare first.
