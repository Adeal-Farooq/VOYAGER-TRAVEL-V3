# TRIP PLANNER MODULE ~~—~~ FULL BUILD SPECIFICATION 

#### CONTEXT 

This app already has two working modules: 

1. Search ~~—~~ general search/discovery 

2. A ~~-t~~ o ~~-~~ B Route Builder ~~—~~ a segment ~~-~~ based transport engine that, between any two points, recommends transport options (Bus / Cab ~~-A~~ uto ~~-B~~ ike / Walk) as clearly separated top ~~-l~~ evel choices, with buses showing nearest boarding stop + bus number + timing + fare, and cabs/bikes showing direct point ~~-~~ to ~~-~~ point routes with optional custom stops. 

We are now building the third module: Trip Planner ~~—~~ a full destination ~~-~~ and ~~-i~~ tinerary planning system. This is NOT just point ~~-~~ to ~~-~~ point routing. It answers: where shouldI go, in what order, at what time, and within what budg ~~et—~~ while reusing the existing A ~~-t~~ o ~~-~~ B segment engine for every movement between places. 

Do not rebuild transport logic from scratch. Every "place A to place B" hop inside an itinerary must call the same segment/route engine already built. This module sits on top of it. 

###### 1. INPUT COLLECTION FLOW 

When the user opens the "Trip" tab, run a guided multi ~~-~~ step form (not one giant form ~~—~~ step by step, each step showing a summary of previous answers at the top so user can go back and edit). 

### Step 1 ~~—~~ Destination 

- e Text input with autocomplete/search (city, region, or specific landmark). 

- e Toggle: "I know where I want to go" vs "Suggest destinations for me" (if the second is chosen, ask 2 ~~-~~ 3 quick questions ~~—~~ preferred climate, max travel distance/time from current location, trip theme ~~—~~ and generate 3 ~~-~~ 5 destination suggestions with a one ~~-~~ line reason each before proceeding). 

### Step 2 ~~—~~ Trip Duration 

- e Date picker: start date and end date. 

- e Ifuser doesn't want to commit to exact dates, allow "just number of days" mode (e.g., "3 days") and treat it as flexible/no fixed calendar dates ~~—~~ in this case skip anything that depends on real calendar (like weekday ~~-o~~ nly closures) unless the user later fixes dates. 

### Step 3 ~~—~~ Group Details 

- e Group size (number). 

- e Group type: Solo / Couple / Friends / Family with kids / Family without kids / Senior citizens included. 

- ¢ This must directly influence downstream filtering ~~—~~ e.g., family with kids should down ~~-r~~ ank nightlife/ba ~~r-~~ heavy spots and up ~~-~~ rank parks, easy ~~-~~ walk attractions; senior citizens should down ~~-r~~ ank heavy trekking/adventure spots unless explicitly selected as an interest. 

### Step 4 ~~—~~ Budget 

- ¢ Total trip budget in = (numeric input). 

- e Toggle: "This is total for the whole group" vs "This is per person" ~~—~~ normalize internally to a tota ~~l~~ -grou ~~p-~~ budget number regardless of which one user picks. 

- e Optional: let user manually split budget across categories (Stay / Food / Transport / Attractions / Misc) ~~—~~ if they skip this, auto ~~-a~~ llocate using a default ratio (suggested default: Stay 35%, Food 25%, Transport 15%, Attractions 20%, Misc 5%) and show this breakdown so user can adjust with sliders before continuing. 

## Step 5 ~~—~~ Interests / Preferences (multi ~~-s~~ elect, no hard limit but recommend picking 3 ~~-~~ 5) 

- e Nature & Scenery 

- e History & Heritage 

- e Food & Local Cuisine 

- e Adventure & Outdoor Activities 

- e Shopping 

- e Nightlife 

- e Relaxation / Wellness 

- e Offbeat / Hidden Gems 

- e Religious / Spiritual 

- e Museums & Art 

- e Photography Spots 

### Step 6 ~~—~~ Pace Preference 

- e Relaxed (2 ~~-~~ 3 places/day, more buffer/rest time) 

- e Balanced (3 ~~-~~ 4 places/day) 

- e Packed (5+ places/day, minimal buffer) 

### Step 7 ~~—~~ Summary Screen 

- e Show all collected inputs in an editable card format. 

- e Asingle "Generate My Trip" button that triggers the planning engine. 

e Donotlet the engine run until this step is confirmed ~~—~~ no silent auto ~~-~~ generation from partial data. 

###### 2. DESTINATION & PLACES DISCOVERY ENGINE 

Once inputs are locked, build a candidate pool of places for the destination. 

###### 2.1 Data needed per place (this must exist for every place in the pool): 

- e Name, category (attraction/food/nature/shopping/nightlife/religious/etc.), short description 

- e Average visit duration (in minutes) 

- e Entry fee (% per person, 0 if free) 

- e Average rating (out of 5) and rough number of reviews (for confidence weighting) e Best time of day to visit: Early Morning / Morning / Afternoon / Evening / Night (can have more than one valid window) 

- e Crowd level by time slot (Low/Medium/High) ~~—~~ if this data isn't available from any source, mark as "Unknown" and do not fabricate it; treat unknown as neutral/medium in scoring, never as a confident data point. 

- e Opening hours and any weekly closures 

- e Latitude/longitude (mandatory ~~—~~ needed for clustering and route calls) 

- e Tags matching the interest categories from Step 5 

- e Suitability flags: family ~~-f~~ riendly (yes/no), accessibility notes if available, physically demanding (yes/no) 

###### 2.2 Where this data comes from 

- e The AlI/dev must decide based on existing app stack (API, database, scraped source, or LLM- ~~g~~ enerated with disclaimers). If using an LLM to generate place data instead ofa live API, explicitly flag in the UI that details like fees/timings are approximate and should be verified ~~—~~ do not silently present LLM ~~-g~~ uessed numbers as verified facts. 

###### 2.3 Ranking / Scoring formula For each candidate place, compute a relevance score: 



###### Where: 

- ° = fraction of user ~~-~~ selected interest tags this place matches (0 to 1) 

- ° = place rating /5 

- ° = 1.0 if fully suitable for group type, 0.5 if partially, 0 if unsuitable (e.g., a bar for a family ~~-~~ with ~~-~~ kids trip) 

- ° = higher score if the place's low ~~-~~ crowd time slot aligns with when it would likely be scheduled 

- ° = extra weight for offbeat/hidde ~~n-~~ gem tagged places if user selected that interest, to avoid an itinerary that's just "top 10 tourist trap" list 

Every recommended place should showa short "why recommended" line to the user (e.g., "Matches your interest in Heritage + highly rated + good fit for families") ~~—~~ never show a bare ranked list with no reasoning. 

2.4 Diversity rule Do not let the top ~~-~~ ranked pool be dominated by a single category. Cap any single category at roughly 40% of the places actually included in the final itinerary, unless the user's interests are extremely narrow (e.g., only "Food" selected) ~~—~~ in that case diversity rule is relaxed but still avoid pure repetition (e.g., don't put 5 similar cafes back to back). 

###### 3. ITINERARY BUILDER (DAY-WISE) 

###### 3.1 Place ~~-~~ t ~~o-~~ day allocation 

- e Total available places = pace ~~_p~~ reference x number ~~_o~~ f ~~_d~~ ays (e.g., Balanced x 3 days = 9 ~~-~~ 12 places total). 

- e Group nearby places using geographic clustering (simple approach: ~~k-~~ means or greedy neares ~~t-~~ neighbor clustering on lat/long, where k = number of days) so each day's cluster is geographically coherent ~~—~~ do not distribute purely by rank/preference order, since that causes cross ~~-c~~ ity zig ~~-~~ zagging. 

##### 3.2 Within ~~-~~ day ordering (mini route optimization) 

- e Within each day's cluster, order the places to minimize backtracking ~~—~~ treat itasa small travelin ~~g-~~ salesman ~~-s~~ tyle problem (neares ~~t-~~ neighbor heuristic is enough, doesn't need to be perfectly optimal, just reasonable ~~—~~ no crossing paths back and forth). 

- e Layer time ~~-~~ of ~~-~~ day constraints on top of pure distance optimization: e Sunrise/scenic viewpoints > schedule early morning if tagged as such 

   - e Indoor museums/malls > schedule during peak heat/afternoon if outdoor alternatives exist for morning/evening 

   - e Sunset points/rooftop spots > schedule evening 

   - e Nightlife > only if user selected it and only in evening/night slot 

- e Ifatime ~~-o~~ f ~~-~~ day constraint conflicts with the shortes ~~t-~~ path order, time ~~-~~ of ~~-~~ day constraint wins for that specific place, but keep the rest ofthe day's order distance ~~-~~ optimized around it. 

3.3 Transport integration (reuse existing engine) 

- e For every consecutive pair of places in a day's plan, call the existing A ~~-t~~ o ~~-~~ B segment engine to get: recommended transport mode (bus/cab/walk), time taken, and fare. 

- e Donot build aseparate/simplified distance ~~-~~ only estimate for this ~~—~~ it must be the same real logic already validated for the A ~~-t~~ o ~~-~~ B module (same bus ~~-s~~ top ~~-a~~ s ~~-i~~ nherent ~~-~~ step logic, same direc ~~t-~~ cab ~~-~~ route logic). 

- e Insert this transport segment visually between each place block in the itinerary. 

###### 3.4 Daily running totals Each day view must show, updated live: 

- e Number of places visited 

- e Total time spent at places (sightseeing/activity time) 

- e Total transport time 

- ¢ Total free/buffer time remaining in the day 

- e Running cost for that day (see Budget Engine below) 

###### 4. BUDGET ENGINE 

###### 4.1 Per ~~-~~ place cost estimation For every place in the itinerary, calculate: 

- e Entry/activity fee x group size 

- e Average food cost nearby (assume 1 meal if the place spans a mealtime, based on average per ~~-~~ person cost in that price tier x group size) 

- e Transport cost to reach it from the previous stop (pulled directly from the segment engine's fare output) 

###### 4.2 Running budget tracker 

- e Maintaina live total: vs(Total Budget), broken into the same categories as Step 4 allocation (Stay / Food / Transport / Attractions / Misc). 

- e Show this asa visible bar or breakdown widget that updates in real time as the itinerary is generated and as the user edits it. 

4.3 Overspend handling If projected total spend exceeds the user's stated budget at any point: 

- e Donotjust show a warning and stop ~~—~~ proactively suggest at least one concrete fix per overspend instance: 

   - e Swapa paid attraction for a free/cheaper alternative nearby with similar theme 

   - e Suggest a cheaper transport mode for a specific segment (e.g., bus instead of cab) if it doesn't blow the time budget too badly 

   - e Suggest a lower ~~-~~ cost food option nearby e Ifnone of the above close the gap, suggest trimming the lowes ~~t-~~ ranked (lowest score) place from the day 

- e Always present the cheaper alternative side ~~-~~ by ~~-~~ side with the original option (with the cost difference clearly shown), so the user picks rather than the system silently downgrading their plan. 

4.4 Surplus handling If there's meaningful budget surplus remaining: 

- e« Suggest optional upgrades: a better ~~-~~ rated restaurant nearby, a premium/guided experience at one of the attractions, or an additional offbeat place that didn't make the initial cut. 

- e These must be clearly optional add ~~-~~ ons the user can accept or ignore ~~—~~ never auto ~~-~~ added to the plan. 

###### 5. STAY / ACCOMMODATION (multi-day trips outside user's current city only) 

- e Recommend a stay location that minimizes average daily travel distance to that day's cluster of places ~~—~~ not simply the cheapest or highest ~~-~~ rated option in isolation. 

- e Ifthe itinerary spans multiple geographically distant zones across days, it is acceptable to recommend more than one stay (e.g., switch hotels/areas mid- ~~t~~ rip) ~~—~~ but flag this clearly to the user since it adds packing/checkout friction, and prefer single ~~-~~ stay solutions when the cost/time tradeoff is small. 

- e Showstay cost per night and reflect it in the overall budget tracker under the "Stay" category. 

- e Ifthe destination is close enough that no overnight stay is needed (day trip), skip this section entirely and reallocate that budget percentage to other categories with a note to the user explaining why. 

##### 6. USER CONTROL & CUSTOMIZATION (must work at every stage, not just at 

##### the end) 

- e Swapa place: user can replace any recommended place with an alternative from the same category/cluster; on swap, immediately recalculate that day's route order, transport segments, and budget ~~—~~ do not require a full itinerary regeneration. 

- e Addacustom place: user can manually type/search a place not in the original recommended pool; it gets inserted into the most geographically sensible day/slot, and the system recalculates around it the same way. 

- e Removea place: immediately frees up time and budget for that day; system should proactively suggest filling the gap with another place from the ranked pool (not just leave a hole), but only apply it if the user accepts the suggestion. 

- e Reorder within a day (drag/manual reorder): allowed, but if the new order meaningfully increases total travel time or cost versus the optimized order, show a clear inline warning with the delta (e.g., "This order adds ~25 min more travel ~~—~~ keep anyway?") without blocking the user from proceeding. 

- e Allofthe above must propagate downstream ~~—~~ e.g., swapping a place on Day 1 should not silently leave Day 2's budget totals stale; recalculation must be end ~~-~~ to ~~-~~ end whenever anything changes upstream. 

### 7. OUTPUT / FINAL VIEW 

##### 7.1 Day ~~-~~ by ~~-~~ day timeline 

- e Same visual timeline style already used for the A ~~-t~~ o ~~-~~ B segment builder: place block > time spent > transport segment to next > next place block, repeating through each day, with a clear day divider between days. 

- e Each block should show timing (e.g., "9:00 AM <u>-</u> 10:30 AM") not just duration, so the user can follow it like an actual schedule. 

###### 7.2 Map view 

- e Show all places for the currently selected day highlighted on the map, with the connecting route drawn (reusing the same route ~~-~~ highlighting already built for A ~~-t~~ o ~~-~~ B). 

- e Allow toggling between days to see that day's specific map view, and an optional "full trip" view showing all days together (different color per day). 

###### 7.3 Final trip summary 

- e Total budget breakdown by category (Stay/Food/Transport/Attractions/Misc) vs total budget set by user. 

- e Total places covered vs total time spent sightseeing vs total time spent in transit (asa simple ratio/visual, e.g., a small bar or donut breakdown). 

- e One clear top banner recommendation, e.g., "Best overall plan for your =X budget and interests," summarizing the plan's fit in a sentence ~~—~~ not just raw numbers with no takeaway. 

###### 8. EDGE CASES TO HANDLE EXPLICITLY 

- e Destination has very few places matching the selected interests > relax the interest filter automatically (widen to adjacent categories) rather than returning an empty/thin itinerary, and tell the user this happened. 

- e Trip duration is longer than there are quality places to fill it > don't force- ~~f~~ ill with low ~~-~~ score filler; instead suggest fewer places per day (more relaxed pace) or suggest adding a nearby secondary destination, and let the user choose. 

- e Budget is unrealistically low for the destination/duration > tell the user clearly this budget is tight for this trip, give an estimated realistic minimum, and let them either adjust budget or accept a bare ~~-~~ bones plan ~~—~~ never silently produce a broken/incomplete plan without explanation. 

- e User picks contradictory inputs (e.g., "Nightlife" interest + "Family with kids" group) > don't silently drop one; ask a quick clarifying toggle (e.g., "Include nightlife spots for the adults in the group?") before finalizing. 

- e Notransport data available between two places (segment engine returns nothing) > show this gap honestly in the itinerary rather than guessing a fake time/cost, and prompt the user to manually specify or skip. 

- e Real ~~-~~ time factors (weather, holidays/closures) unknown to the system > do not fabricate confident claims about them; if this data isn't available, state assumptions plainly (e.g., "Assuming this attraction is open ~~—~~ please verify before your trip") rather than presenting guesses as verified facts. 

###### 9. INTEGRATION RULE (do not violate) 

This entire module must treat the existing A ~~-t~~ o ~~-~~ B segment engine as the single source of truth for anything transport ~~-~~ related (mode, time, cost, bus numbers/timings, direct cab routing). The Trip Planner's only new intelligence is: what to see, in what order, at what time of day, and within what budget ~~—~~ never re ~~-~~ derive transport logic independently 

inside this module. 

##### 10. BUILD ORDER (recommended, so the AI doesn't try to do everything at 

#### once) 

1. Input collection flow (Steps 1 ~~-~~ 7) with a working summary screen. 

2. Places discovery + ranking engine (static data first is fine, real API/live data can come later). 

3. Day ~~-w~~ ise clustering + within ~~-~~ day ordering (without transport integration yet ~~—~~ just place order). 

4. Plugin the existing segment engine between places. 

5. Budget engine (estimation + overspend/surplus handling). 

6. Stay recommendation logic. 

7. Customization/recalculation (swap/add/remove/reorder). 

8. Final timeline + map view + trip summary. 

Build and test each phase before moving to the next ~~—~~ do not attempt all 10 sections in one 

pass. 

