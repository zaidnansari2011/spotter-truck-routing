# Decision log

Every significant choice in this project, with the options considered, what was tested, the measured results, and why the final option won. Newest entries at the bottom. Measurements were taken from a development machine unless noted, so absolute latencies are indicative. Test counts in each entry are as of that entry; the current totals are in the README.

**Where to start.** For the scoring logic: [DR-006](#dr-006-interpreting-the-risk-table-boundaries) (risk table edges), [DR-007](#dr-007-no-travel-in-the-ranking) (No Travel and miles), [DR-003](#dr-003-checkpoint-etas-from-tomtom-progress-data) and [DR-005](#dr-005-which-weather-fields-and-how-to-align-them-with-etas) (weather at the arrival time), [DR-014](#dr-014-routes-without-a-forecast-rank-last) (missing forecasts). For performance: [DR-020](#dr-020-heatmap-rendering-and-the-timeline-slider) and [DR-023](#dr-023-staying-inside-the-free-weather-quota). For the final review: [DR-029](#dr-029-review-against-a-scoring-checklist) and [DR-031](#dr-031-pre-submission-audit).

| # | Decision | Status |
|---|---|---|
| [DR-001](#dr-001-routing-provider-tomtom-truck-routing) | Routing provider: TomTom truck routing | Accepted |
| [DR-002](#dr-002-request-2-alternatives-not-5) | Request 2 alternatives (3 routes), not 5 | Accepted |
| [DR-003](#dr-003-checkpoint-etas-from-tomtom-progress-data) | Checkpoint ETAs from TomTom `progress` data | Accepted |
| [DR-004](#dr-004-weather-provider-open-meteo) | Weather provider: Open-Meteo | Accepted |
| [DR-005](#dr-005-which-weather-fields-and-how-to-align-them-with-etas) | Weather fields and ETA alignment | Accepted |
| [DR-006](#dr-006-interpreting-the-risk-table-boundaries) | Risk table boundaries | Accepted |
| [DR-007](#dr-007-no-travel-in-the-ranking) | No Travel in the ranking | Accepted |
| [DR-008](#dr-008-ranking-precision-for-average-risk) | Ranking precision for average risk | Accepted |
| [DR-009](#dr-009-forecast-slider-start-time) | Forecast slider start time | Accepted, revised by DR-019 |
| [DR-010](#dr-010-map-rendering-maplibre-gl) | Map rendering: MapLibre GL | Accepted |
| [DR-011](#dr-011-hosting-azure-container-apps) | Hosting: Azure Container Apps | Accepted, revised by DR-030 |
| [DR-012](#dr-012-stateless-backend-no-database) | Stateless backend, no database | Accepted |
| [DR-013](#dr-013-continuous-risk-index-for-the-heatmap) | Continuous risk index for the heatmap | Accepted |
| [DR-014](#dr-014-routes-without-a-forecast-rank-last) | Routes without a forecast rank last | Accepted |
| [DR-015](#dr-015-guaranteeing-distinct-route-options) | Guaranteeing distinct route options | Accepted |
| [DR-016](#dr-016-keep-the-api-key-out-of-logs) | Keep the API key out of logs | Accepted |
| [DR-017](#dr-017-forecast-batching-and-caching) | Forecast batching and caching | Accepted |
| [DR-018](#dr-018-plan-api-design) | Plan API design | Accepted, revised by DR-023 |
| [DR-019](#dr-019-corridor-heatmap-data) | Corridor heatmap data | Accepted, revised by DR-023 and DR-029 |
| [DR-020](#dr-020-heatmap-rendering-and-the-timeline-slider) | Heatmap rendering and the timeline slider | Accepted |
| [DR-021](#dr-021-browser-qa-and-the-production-map-worker) | Browser QA and the production map worker | Accepted |
| [DR-022](#dr-022-departure-time-advisor) | Departure-time advisor | Accepted |
| [DR-023](#dr-023-staying-inside-the-free-weather-quota) | Staying inside the free weather quota | Accepted (revises DR-018) |
| [DR-024](#dr-024-trucks-on-the-timeline) | Trucks on the timeline | Accepted |
| [DR-025](#dr-025-hours-of-service-rest-breaks) | Hours-of-service rest breaks | Accepted |
| [DR-026](#dr-026-simulated-storm-demo-mode) | Simulated storm demo mode | Accepted |
| [DR-027](#dr-027-shareable-trip-links) | Shareable trip links | Accepted |
| [DR-028](#dr-028-layout-and-map-label-review) | Layout and map label review | Accepted |
| [DR-029](#dr-029-review-against-a-scoring-checklist) | Review against a scoring checklist | Accepted |
| [DR-030](#dr-030-hosting-as-deployed) | Hosting as deployed | Accepted, revised by DR-031 |
| [DR-031](#dr-031-pre-submission-audit) | Pre-submission audit | Accepted |

---

## DR-001: Routing provider: TomTom truck routing

**Context.** The brief needs 3 route options for a truck, and ETAs at points along each route. Load weight is an input.

**Options considered.**

| Provider | Truck mode | Alternatives | Per-point travel time | Verdict |
|---|---|---|---|---|
| TomTom Routing API | Yes (`travelMode=truck`, `vehicleWeight`, `vehicleCommercial`) | Up to 5 | Yes (`extendedRouteRepresentation=travelTime`) | Chosen |
| Mapbox Directions | No (only `max_weight` road restriction) | Up to 2 | Yes (annotations) | Car routing for a truck app |
| OpenRouteService | Yes (`driving-hgv`) | Only for short routes | No | Fails on long-haul trips |
| OSRM public demo | No | Yes | Yes | Car only, no SLA |
| Google Routes | No | Up to 3 | No | No truck mode |

**Tested.** Geocoding and truck routing with a live key on 2026-10-21.

| Test | Result |
|---|---|
| Geocode "Chicago, IL", "Denver, CO", "Dallas, TX", "Atlanta, GA" | Correct city centers, 0.51 to 0.59 s each |
| Truck route Chicago to Denver, 30,000 kg, up to 5 alternatives | 6 distinct routes: 1,007 / 1,185 / 1,344 / 1,019 / 1,301 / 1,244 mi |
| Truck route Dallas to Atlanta, same settings | 6 distinct routes: 789 to 1,213 mi |
| `progress` array present on every route | Yes |

**Decision.** TomTom. Truck routing respects weight and commercial-vehicle restrictions, so routes and travel times are realistic for the user's load.

---

## DR-002: Request 2 alternatives, not 5

**Context.** First tests took 18.8 s for one Chicago to Denver request. Too slow for a responsive UI.

**Tested.** Same Chicago to Denver truck request, one variable changed at a time.

| Variant | Latency | Routes returned |
|---|---|---|
| 5 alternatives + `computeTravelTimeFor=all` | 12.4 s | 6 |
| 5 alternatives | 11.2 s | 6 |
| 3 alternatives | 6.7 s | 4 |
| **2 alternatives** | **4.7 s** | **3** |
| 2 alternatives, car mode (reference) | 4.5 s | 3 |

**Findings.** Latency grows with the number of alternatives. Truck mode costs almost nothing over car mode (4.7 s vs 4.5 s). `computeTravelTimeFor=all` adds about 1 s and is not needed.

**Decision.** `maxAlternatives=2`, which returns exactly the 3 routes the brief asks for at the lowest latency. Responses are cached by request, so repeat lookups are instant. If TomTom ever returns fewer than 3 distinct routes, a fallback requests a route through a waypoint offset from the midpoint, and the UI labels that route as generated this way.

---

## DR-003: Checkpoint ETAs from TomTom `progress` data

**Context.** The brief requires weather at the truck's estimated arrival time at each checkpoint. Assuming constant speed would be wrong: a truck moves slower in cities and on grades than on interstates.

**Tested.** The Chicago to Denver fastest route has 10,712 geometry points but only 122 `progress` entries. Each entry gives cumulative distance and travel time at a point index, e.g. `{pointIndex: 4, distanceInMeters: 246, travelTimeInSeconds: 94}`.

**Decision.** Use the `progress` entries as timing anchors. Between two anchors, interpolate time in proportion to distance along the geometry. ETAs then follow TomTom's traffic-aware speed profile, and constant speed is only assumed inside each short anchor span.

**Also decided.** Routes carry 10,000 to 16,000 points. Checkpoints are computed on the full geometry on the server, and a simplified line is sent to the browser to keep payloads small.

**Implementation details.**
- Mileage uses TomTom's reported distances, not the polyline's own length. On Chicago to Denver the polyline measures 1,004.71 mi while TomTom reports 1,006.68 mi. Using TomTom's figure keeps checkpoint miles consistent with the route length shown to the user.
- Checkpoints sit at mile 0, every N miles, and the destination. A destination that falls exactly on a multiple of N is not duplicated.
- Each checkpoint covers half the gap to each neighbor, clipped at the ends, so the miles per risk level always add up to the route length.

**Results on the real Chicago to Denver truck route** (10,712 points, 122 anchors):

| Interval | Checkpoints | Last checkpoint ETA | Covered miles sum |
|---|---|---|---|
| 10 mi | 102 | +14.594 h | 1,006.68 |
| 25 mi | 42 | +14.594 h | 1,006.68 |
| 50 mi | 22 | +14.594 h | 1,006.68 |

The final ETA equals TomTom's own trip time (14.594 h) and covered miles equal the route length. Building the profile and all three checkpoint sets takes 15 ms.

**Why constant speed would be wrong, measured.** The truck averages 33 mph over the first 50 miles (leaving Chicago) against 69 mph for the whole trip.

| Mile | ETA from `progress` | ETA at constant 69 mph | Error |
|---|---|---|---|
| 50 | +1.50 h | +0.72 h | 46 min early |
| 100 | +2.19 h | +1.45 h | 44 min early |

A constant-speed model would read weather for the wrong hour at most checkpoints near cities.

**Tests.** 24 unit tests on spacing, coverage, interpolation between anchors at different speeds, API length differing from polyline length, zero-length segments, and clamping at the route end. 100% branch coverage.

---

## DR-004: Weather provider: Open-Meteo

**Context.** We need hourly wind, rain and snow forecasts for hundreds of points (checkpoints plus the heatmap corridor), 0 to 48+ hours ahead.

**Tested.** Live requests on 2026-10-21.

| Test | Result |
|---|---|
| Units with `wind_speed_unit=mph&precipitation_unit=inch` | wind `mp/h`, rain `inch`, showers `inch`, snowfall `inch`. Matches the brief's units with no conversion |
| 300 locations x 49 hourly steps in one GET | 2.09 s, URL 4,098 characters, all 300 returned |

**Other facts.** No API key. Multi-location requests are comma-separated. In North America the default model blend includes NOAA HRRR (3 km). Forecasts go 16 days ahead. The free tier is for non-commercial use (600 calls/min, 10,000/day), which suits an assessment. A production deployment would use their commercial plan. Data is CC BY 4.0, credited in the app.

**Decision.** Open-Meteo, batched up to 300 points per request and cached per location and hour.

---

## DR-005: Which weather fields, and how to align them with ETAs

**Fields.**
- Wind: `wind_speed_10m`, sustained speed. The brief says "wind", not gusts. Gusts are shown in tooltips for context but not classified.
- Rain: `rain + showers`. Not `precipitation`, which also includes melted snow and would count snow twice.
- Snow: `snowfall`, in inches per hour of snow (not water equivalent), matching the brief's snow thresholds.

**Time alignment.** Open-Meteo documents rain, showers and snowfall as "sum of the preceding hour", while wind speed is an instant value. So a truck reaching a checkpoint at 14:20 is rated with:
- precipitation from the 15:00 value (which covers 14:00 to 15:00),
- wind linearly interpolated between 14:00 and 15:00.

A checkpoint whose ETA falls beyond the forecast horizon is marked "no forecast", never silently rated Low.

**Edge cases handled.**
- ETA exactly on the hour (15:00) uses the 15:00 bucket. One second later moves to the 16:00 bucket.
- Missing wind, rain, showers or snow value: the sample is "no forecast". A missing gust value does not hide the sample, since gusts are display-only.
- Rain plus showers is rounded back to Open-Meteo's 3-decimal precision. Without this, `0.01 + 0.09` evaluates to `0.09999999999999999` in floating point and would be rated Low instead of Moderate.

**Verified live (2026-10-21).** A 72-hour request returned 72 timestamps, all exactly on the hour, contiguous, with no null values in any field. This is the shape `HourlySeries` assumes.

**Tests.** 11 unit tests covering bucket selection, wind interpolation, the exact-hour boundary, float rounding, horizon limits, and missing values. 100% branch coverage.

---

## DR-006: Interpreting the risk table boundaries

**Context.** The table's ranges touch or overlap: rain 0.25 appears in both Moderate and High, and wind has a gap between 34 and 35 mph for decimal values.

**Decision.** Each band includes its lower bound and excludes its upper bound. The exceptions follow the table's own symbols: wind No Travel is `>= 55`, so 55 mph is No Travel; rain and snow No Travel are `> 1.00` and `> 3.0`, so exactly 1.00 in/hr rain and 3.0 in/hr snow are Severe.

| Value | Level |
|---|---|
| Wind 24.9 / 25 / 34.9 / 35 / 45 / 55 mph | Low / Moderate / Moderate / High / Severe / No Travel |
| Rain 0.10 / 0.25 / 0.50 / 1.00 / 1.01 in/hr | Moderate / High / Severe / Severe / No Travel |
| Snow 0.5 / 1.0 / 2.0 / 3.0 / 3.01 in/hr | Moderate / High / Severe / Severe / No Travel |

A checkpoint takes the worst of its wind, rain and snow levels. Load rules are then applied and can only raise the level. Weight thresholds are strict (`> 30,000 lb`, `> 40,000 lb`), so exactly 30,000 lb does not trigger a rule. Every row above is a unit test.

---

## DR-007: No Travel in the ranking

**Context.** The brief ranks routes by Severe miles, High miles, average risk, then travel time. No Travel is not in the list.

**Problem.** Taken literally, a route with 10 No Travel miles and 0 Severe miles would beat a route with 0 No Travel miles and 20 Severe miles.

**Decision.** No Travel miles are compared first, then the brief's four criteria in its order. Any route with No Travel miles is badged "Do not travel". If all three routes have No Travel segments, the app says there is no safe route at that departure time.

**Tested.** Route A (10 No Travel miles, 0 Severe, faster) vs Route B (0 No Travel, 50 Severe): B is recommended, with the reason "Fewest No Travel miles: 0 mi vs 10 mi on Route A". The `all_no_travel` flag is tested both ways.

---

## DR-008: Ranking precision for average risk

**Context.** Severe and High miles are often tied (commonly both 0), so average risk usually decides. It is a decimal and almost never exactly equal, so travel time rarely gets a say.

**Example.**

| | Route A | Route B |
|---|---|---|
| Severe / High miles | 0 / 0 | 0 / 0 |
| Moderate miles | 25 of 400 | 25 of 410 |
| Average risk (exact) | 0.0625 | 0.0610 |
| Average risk (shown) | 0.06 | 0.06 |
| Travel time | 6 h 10 m | 7 h 25 m |

Comparing exact values picks B, which drives through the same 25 rainy miles but is 1 h 15 m slower, while the screen shows both at 0.06. To the user that looks like a bug, and it ignores the brief's "balancing weather risk and travel time".

**Options.**
1. Compare exact values. Literal, but produces the case above.
2. **Compare at the 2 decimals shown in the UI.** Same order as the brief, only removes differences nobody can see.
3. Treat routes within a wide band (e.g. 0.1) as equal. Real balancing, but an invented constant.

**Decision.** Option 2. Every recommendation can be explained from the numbers on screen. A "Why this route" panel names the deciding criterion. When the runner-up is 30+ minutes faster, a note shows that trade-off without changing the recommendation.

**Same rule for miles.** Severe, High and No Travel miles are compared at 1 decimal, the precision shown in the UI. Checkpoint coverage produces values like 25.04 vs 25.0 from floating-point sums, and without rounding those would decide a ranking the screen shows as tied.

**Output.** The ranking returns the full order, the recommended route, one comparison per other route naming the criterion that decided it (e.g. "Shortest travel time: 6 h 10 min vs 7 h 25 min on Route B"), and the optional trade-off note (e.g. "Route B is 2 h faster but has 30 Severe miles, average risk 0.23 (vs 20 High miles, average risk 0.10 on Route A).").

**Tested.** 26 unit tests: each criterion deciding only when every earlier one ties, the exact table above (A wins on time), a visible 0.21 vs 0.20 difference beating a 3 h faster route, mile differences below 0.1 tying, full ties keeping the routing API's order, the 29 vs 30 minute trade-off threshold, and duration formatting. 100% branch coverage.

**Real-data check (2026-10-21).** The 3 real Chicago to Denver truck routes, scored with live forecasts at each checkpoint's ETA (25 mi interval, 38,000 lb):

| Route | Miles | Time | Checkpoints | Average risk | Max wind |
|---|---|---|---|---|---|
| A | 1,006.7 | 14 h 36 min | 42 | 0.00 | 13.1 mph |
| B | 1,185.1 | 17 h 23 min | 49 | 0.00 | 11.3 mph |
| C | 1,343.6 | 20 h 5 min | 55 | 0.00 | 12.3 mph |

All risk criteria tie, so travel time decides and A is recommended, as intended. 146 checkpoints mapped to 139 forecast locations, fetched in one 1.08 s request. All domain logic for the three routes ran in 73 ms.

---

## DR-009: Forecast slider start time

**Context.** "0 to 48 hour forecast slider" can mean hours from now or hours from departure. They differ only when the departure is in the future.

**Example.** It is Tuesday 21:00. The truck leaves Thursday 06:00 (in 33 h) and the trip takes 20 h.

| | Slider starts now | Slider starts at departure |
|---|---|---|
| Covers | Tue 21:00 to Thu 21:00 | Thu 06:00 to Sat 06:00 |
| Trip visible | First 15 h of 20 h | All of it |

**Decision.** Hour 0 is the departure time, which is "now" by default. A Departure / Now toggle switches to hours from the current time. Every slider position shows the clock time and the forecast lead, e.g. "Thu 06:00, forecast +33 h".

**Revised during implementation (DR-019).** The first plan fetched both windows up front so the toggle would be instant. For a departure days ahead that doubles the heatmap payload, and in the common case (leave now) the two windows are identical anyway. The toggle now makes one extra request, which is served from the forecast cache in about 0.2 s.

---

## DR-010: Map rendering: MapLibre GL

**Context.** UI, map and heatmap smoothness is 40% of the evaluation. The slider must update the heatmap while dragging.

**Decision.** MapLibre GL JS (WebGL) with OpenFreeMap vector tiles, so there is no map token in the browser. The heatmap is one data source holding all 49 hourly frames. The slider changes only the layer's paint expression, so dragging triggers no network requests and no data re-upload, just GPU work. Measured results are in [DR-020](#dr-020-heatmap-rendering-and-the-timeline-slider).

---

## DR-011: Hosting: Azure Container Apps

**Decision.** One Docker image (Django serving the built React app) on Azure Container Apps with at least 1 replica always running, so reviewers never hit a cold start. Redis on Azure Managed Redis, with an in-memory fallback so a cache outage cannot break the app.

**Update.** The deployed app uses the in-memory cache, not Redis; see [DR-030](#dr-030-hosting-as-deployed). Secrets live in Container Apps secrets, never in the image or the repo.

---

## DR-012: Stateless backend, no database

**Context.** Every plan is computed from the request (places, departure, load) plus live routing and forecast data. Nothing has to be stored per user.

**Decision.** No database and no auth. Django runs with `DATABASES = {}`, and Redis caches the slow upstream calls (routes per request, forecasts per location and hour). If Redis is unreachable, cache errors are treated as misses, so the app keeps working, only slower. Without `REDIS_URL` the same code uses Django's in-memory cache, which is what the hosted app does ([DR-030](#dr-030-hosting-as-deployed)).

**Result.** Simpler deployment (one container plus a cache), nothing to migrate, and the app scales horizontally without coordination. Verified locally: one Django process serves the built React app at `/`, the API at `/api/health/`, and OpenAPI docs at `/api/docs/`.

---

## DR-013: Continuous risk index for the heatmap

**Context.** Five discrete levels make a blocky heatmap with hard color jumps. A smooth gradient reads better and animates more smoothly with the slider. But the heatmap must never contradict the checkpoint markers: a point the markers call High cannot be painted Severe.

**Decision.** Each condition maps to a 0 to 4 index by linear interpolation inside its band, so band edges land on whole numbers (wind 25 mph = 1.0, 35 mph = 2.0, and so on). The combined index is the maximum of wind, rain and snow. Two details keep `floor(index)` equal to the discrete level:
- The Severe band for rain and snow includes its top edge (1.00 in/hr, 3.0 in/hr), so its index is capped at 3.999 there. Only values above the edge reach 4.
- The load-adjusted index (heatmap option "Risk for this load") is raised to the level a load rule forces.

**Also decided.** A checkpoint reports every condition at its final level (e.g. "High: wind, rain"). A load rule is reported only when it actually raised the level. If snow is already Severe, a heavy-load wind rule that would also give Severe is not shown as the reason.

**Tested.** 47 unit tests, 100% branch coverage of `risk.py`:
- every band edge from DR-006 for wind, rain and snow,
- all three load rules at and just past their weight thresholds,
- `floor(index) == level` for 2,001 evenly spaced values per condition plus every edge,
- the index never decreases as the value rises,
- combined and load-adjusted indices agree with the assessed levels.

---

## DR-014: Routes without a forecast rank last

**Found by a failing test.** A route whose checkpoints had no forecast at all has 0 known Severe and High miles. Under the plain ranking it beat a route with 100 real High miles, so missing data counted as safe.

**Decision.** A "forecast available" check runs before every other criterion: a route with no forecast at any checkpoint ranks after every route that has one, with the reason "Forecast available: yes vs no". A route with only some checkpoints missing (e.g. a long trip running past the forecast horizon) is still ranked on its known miles, and the unknown miles are reported separately so the UI can flag them.

**Why not penalize partial gaps too.** Ranking by "fewest unknown miles" first would let a route with 5 unforecast miles at the very end lose to a route with 50 known Severe miles. Showing the gap is more honest than guessing what it contains.

**Tested.** Both cases are unit tests: the fully blind route ranks last, and a route with 30 unknown miles and 20 High miles still beats one with 10 Severe miles.

---

## DR-015: Guaranteeing distinct route options

**Context.** The brief asks for 3 route options. Two lines on the map that follow the same road are not real options, so "3 routes" must mean 3 distinct routes.

**Measuring overlap.** For two routes, the share of one route's points that lie within roughly 300 to 600 m of the other (grid-cell lookup, every 5th point). Calibrated on real TomTom output:

| Pair | Overlap |
|---|---|
| Chicago to Denver, TomTom's 2 alternatives vs the fastest route | 0.03 to 0.13 |
| Dallas to Atlanta, any two of 6 routes | at most 0.40 |
| Chicago to Denver, routes of 1,007 and 1,019 mi (visually the same) | 0.75 / 0.81 |

**Decision.** Two routes are duplicates if either shares 70% or more of its length with the other. Every genuine alternative measured stayed at or below 0.44, so the threshold has a wide margin.

**Fallback when fewer than 3 distinct routes come back.** Request a route through a waypoint offset sideways from the fastest route's midpoint: 15% then 30% of the straight-line distance (clamped to 15 to 120 mi), left then right, at most 4 attempts. A candidate is kept only if it is distinct from every route so far and takes at most 1.6x the fastest route's time. Kept routes are labeled "via waypoint" in the UI. If no candidate qualifies, the app shows fewer routes and says why, instead of inventing fake options.

**Load weight in routing.** The brief's load weight is cargo; TomTom's `vehicleWeight` is gross weight. We send cargo plus an assumed 35,000 lb tractor-trailer tare, capped at the 80,000 lb US federal limit, in kg. Weight-restricted roads are then avoided for heavy loads.

**Live results (2026-10-21).**

| Trip | Routes | Time | Notes |
|---|---|---|---|
| Chicago to Denver | 3 from TomTom | 3.2 s | max overlap 0.13 |
| Dallas to Fort Worth | 3 from TomTom | 0.7 s | max overlap 0.38 |
| Key West to Miami | 1 | 2.5 s | Only one road (US-1). One waypoint route rejoined US-1 and was rejected as a duplicate, three waypoints were unroutable (in the sea). Correctly returns 1 route |

**Browser payload.** Routes are simplified with Douglas-Peucker at 25 m before being sent to the map: Chicago to Denver goes from 10,712 / 13,645 / 15,820 points to 816 / 1,004 / 1,305, in about 0.1 s per route. Checkpoints still use the full geometry.

**Tests.** 18 client tests with mocked HTTP (no live calls in CI): request parameters, label formatting, URL encoding, multi-leg joining, duplicate replacement, unroutable and too-slow waypoints, the 1-route outcome, and error mapping (no route vs upstream failure vs timeout). 14 geometry tests for overlap, offsets and simplification.

---

## DR-016: Keep the API key out of logs

**Found during the live test.** `httpx` logs every request at INFO as `HTTP Request: GET <full url>`, and TomTom takes its key as a query parameter. With Django's root logger at INFO, the key would be written to the container logs on every request.

**Decision.** The `httpx` and `httpcore` loggers are set to WARNING. A test asserts they cannot log at INFO, and a live call afterwards produced 0 log lines containing the key.

---

## DR-017: Forecast batching and caching

**Context.** One plan needs forecasts for every checkpoint of 3 routes at 3 sampling intervals, plus the heatmap grid. Switching the interval in the UI, or two users planning similar trips, should not refetch the same weather.

**Decisions.**
- **Snap to a 0.05 degree grid** (about 5.5 km). That is finer than GFS (13 km) and close to HRRR (3 km), so it does not blur the forecast, and it merges checkpoints that fall in the same cell.
- **One cache entry per grid cell**, holding every hour fetched so far. A request only fetches cells that are missing any hour of its window, and the new hours are merged into the entry. Entries expire after 30 minutes, since the models update hourly.
- **Batches of up to 300 locations**, run in parallel when there is more than one.
- **16-day horizon.** The request window is clipped to Open-Meteo's limit, so hours past it come back as unknown instead of the whole request failing.
- **Errors** (HTTP errors, timeouts, a location-count mismatch) raise one `WeatherError` with Open-Meteo's reason, which the API maps to a clear 502.

**Bug found by measuring.** The first live run made an HTTP request even when everything should have been cached. Django's in-memory cache keeps only 300 entries by default and silently evicts the rest, and this one trip needed 414 cells. Redis has no such limit, and the in-memory cache, which the hosted app uses ([DR-030](#dr-030-hosting-as-deployed)), is now set to 10,000 entries (roughly 50 MB at most).

**Live results (Chicago to Denver, 2026-10-21).**

| Measure | Value |
|---|---|
| Checkpoints, 3 routes x intervals 10/25/50 | 578 |
| Distinct forecast cells after snapping | 414 (28% fewer) |
| First fetch | 0.84 s, 2 parallel requests |
| Repeat fetch (e.g. switching interval) | 0.01 s, 0 requests |
| Checkpoints with a forecast at their ETA | 578 / 578 |

**Tests.** 19 tests with mocked HTTP and an isolated cache per test: request parameters and units, whole-hour window rounding, single-location responses (an object, not a list), batches of 300/300/50, de-duplication, cache hits, merging when the window grows, the 16-day horizon, and error mapping. 100% branch coverage.

---

## DR-018: Plan API design

**One request returns all three sampling intervals.** `POST /api/plan` returns checkpoints, per-route summaries and a ranking for 10, 25 and 50 mile intervals together. Switching the interval in the UI is then instant, with no network request. The cost is a larger response, measured below. *Revised by DR-023: a plan now covers one interval, because each forecast location counts against the free weather quota.*

**Request validation** (each rule is a test):
- Origin and destination: label plus lat/lon in range, at least 1 km apart.
- Departure: ISO 8601 with an explicit UTC offset, from 15 minutes ago (a form filled in a moment ago still means "now") to 7 days ahead (forecast skill drops sharply after a week).
- Load: 0 to 80,000 lb. Zero is allowed for an empty truck. 80,000 lb is the US federal gross limit, so no legal cargo load is above it.

**Errors share one shape**, `{"code", "message", "fields"?}`, with no internal details:

| Situation | Status | Code |
|---|---|---|
| Invalid input | 400 | `invalid_input`, plus per-field messages |
| No road route between the places | 422 | `no_route` |
| Too many requests from one IP | 429 | `rate_limited` |
| TomTom or Open-Meteo failing | 502 | `routing_unavailable` / `weather_unavailable` |
| Unexpected bug | 500 | `internal_error` (traceback logged, never returned) |

**Rate limits.** 60 plans and 600 place searches per hour per IP. Generous for real use, but a refresh loop cannot burn through TomTom's daily quota.

**Caching.** Routes and their simplified map geometry are cached for 10 minutes per (origin, destination, departure, gross weight). Place suggestions are cached for 24 hours per normalized query. Forecasts are cached per grid cell (DR-017).

**Rate limits per address.** Plans 60 an hour, place search 600 an hour, heatmap frames 120 an hour; above that the API answers 429 with the wait time.

**Fewer than 3 routes.** The response carries a plain-language notice (e.g. "There are only 1 distinct road route between these places") rather than failing or padding the list.

**Live results, Chicago to Denver, 38,000 lb (2026-10-21).**

| Measure | Value |
|---|---|
| First request (routing + forecasts + scoring) | 4.6 to 4.9 s |
| Repeat request | 0.34 s, then **0.10 s** after also caching the simplified geometry |
| Response size | 224 KB, **38 KB gzipped** |
| Map geometry | 816 / 1,002 / 1,305 points (from 10,712 / 13,645 / 15,820) |
| Checkpoints per route at 10 / 25 / 50 mi | 102-135 / 42-55 / 22-28 |
| API key occurrences in server logs | 0 |

**Tests.** 30 API tests with fake routing and weather clients: calm weather (fastest route wins), a planted storm on the fastest route (recommendation moves, trade-off note appears), the same storm with a 35,000 lb load (load rule turns it into No Travel), the 40,000 vs 40,001 lb threshold through the full API, missing forecasts, 1 and 2 route results, route caching, every validation rule, every error mapping, and the rate limit. The whole backend is at 100% branch coverage.

---

## DR-019: Corridor heatmap data

**Revised later.** The grid cap below (600 points) became 300 in [DR-023](#dr-023-staying-inside-the-free-weather-quota) to stay inside the free weather quota, and the default layer became "Risk for this load" in [DR-029](#dr-029-review-against-a-scoring-checklist). The text below is the original decision.

**Grid.** Every point within 30 miles of any of the 3 routes, on a regular grid. Spacing is the finest multiple of 0.05 degrees that keeps the grid at or under 600 points, so grid points line up exactly with the forecast cache cells (DR-017) and fit in two Open-Meteo batches. Short trips get a fine grid (Dallas to Fort Worth), long trips a coarser one (Chicago to Denver: 425 points at 0.35 degrees, about 35 km).

**How "within 30 miles" is computed.** Routes are densified to a sample every 5 km and bucketed in a spatial hash whose cells are at least 30 miles wide, so each grid point only checks its 9 neighboring buckets. Worst-case error is 2.5 km at the buffer edge. 140 ms for the 3 real Chicago to Denver routes.

**Two requests instead of one.** The plan response carries the grid points (about 10 KB). The hourly frames come from a separate stateless `POST /api/corridor` (points, hour-0 time, load). Routes appear on the map as soon as the plan returns while the heatmap loads in parallel, and the Departure / Now slider toggle (DR-009) is just a second corridor request.

**Payload format.** One row per grid point and one value per hour, for hours 0 to 48 (49 frames; 50 since DR-031), as small integers:
- `risk`: weather-only risk index x100 (0 to 400), the default "weather heatmap" layer
- `risk_load`: the same with load rules applied, for the "Risk for this load" layer
- `wind` in whole mph, `rain` and `snow` in hundredths of an inch per hour (now tenths of a mph and thousandths of an inch, DR-031)

Values are floored, not rounded, so `floor(risk / 100)` always equals the discrete level shown at checkpoints (DR-013). Hours without a forecast are `null`, never 0.

**Live results (Chicago to Denver, 38,000 lb, 2026-10-21).**

| Measure | Value |
|---|---|
| Grid | 425 points, 0.35 degree spacing |
| Values per response | 20,825 per layer (425 x 49), 0 nulls |
| First request | 0.56 s |
| Repeat request | 0.18 s |
| Size | 252 KB, **48 KB gzipped** |
| Weather on the day | Calm: max wind 21 mph, max rain 0.09 in/hr, no snow (max risk index 0.86, Low) |

**Testing safeguard added.** The corridor service first imported the forecast client factory by name, so tests that swapped in a fake client still reached the live API without failing. Services now look the factory up through its module, and an autouse fixture makes every API test fail loudly if it touches a live client without installing fakes.

**Tests.** 7 grid tests (buffer containment, full coverage along the route, spacing on the 0.05 degree lattice, the point cap, multiple routes) and 13 endpoint tests (frame count and timing, units, the load-adjusted layer differing exactly at 30,000 vs 30,001 lb, nulls, validation, rate limit). Backend total: 216 tests, 100% branch coverage.

---

## DR-020: Heatmap rendering and the timeline slider

**Options considered.**
1. MapLibre's built-in `heatmap` layer. Smooth, but it colors by point *density* (the sum of nearby weighted kernels), so the color at a spot depends on grid spacing and zoom, not only on the forecast. The legend could not be trusted.
2. Square grid cells (fill polygons). Exact, but reads as a coarse mosaic at 35 km spacing.
3. **One blurred disc per grid point, colored directly from its value.** Exact colors, smooth look, and still a GPU layer.

**Decision.** Option 3:
- Colors use the same 5 risk colors as the checkpoints and legend. Each band holds its level's color and only blends into the next over the last 10% before a threshold, so the map matches the legend everywhere except right at band edges.
- Below Moderate the layer is fully transparent (a `step` expression, so blended in-between-hour values like 99.5 cannot leak color either). Calm weather leaves the map clean and storms stand out.
- Disc radius follows the grid spacing at every zoom (exponential zoom expression). A first try at 1.1x the spacing looked blocky in the QA screenshots, so the final value is 1.8x with peak opacity 0.62, which blends neighbors into a continuous field.
- The layer sits under the basemap's place labels and under the routes.

**Slider performance.** The 49 hourly values live on each map feature (`v0` to `v48`). Moving the slider only swaps two paint expressions (color and opacity), which read and blend the two neighboring hours on the GPU for 15-minute steps. The slider's position is local state inside the timeline bar, so dragging never re-renders the sidebar or the 100-row checkpoint table.

**Slider start.** Hour 0 is the exact departure time (or the moment "From now" was chosen), not the top of the hour. Forecast frames start on the hour, so the slider maps into them with a fractional offset; the clock label and the "N h after departure" text always agree.

**Measured in headless Edge (GPU, 1440x900, Chicago to Denver, 425 grid points).**

| Measure | Value |
|---|---|
| Heatmap ready after routes appear | 1.9 s |
| Playback frame rate | 127 fps (no vsync cap in headless), worst frame 16 ms |
| API requests while dragging the slider or playing | 0 |
| "From now" toggle | 1 corridor request (served from the forecast cache) |
| Console or page errors | 0 |

Real weather on the test day was calm everywhere (nothing reached Moderate), so the rendering was also checked with a synthetic storm injected into the corridor response by the test browser only. The app code has no test hooks.

**Fixed during the requirements check.** The first version faded color in from 60% of the Moderate threshold. A Key West to Miami run showed a wide yellow haze over the Keys while every checkpoint on the road was Low: values that were still Low were drawn in Moderate's yellow, contradicting the markers (DR-013). Opacity is now exactly 0 below Moderate; the same run then showed only two real Moderate cells over open water.

---

## DR-021: Browser QA and the production map worker

**Setup.** UI checks run a real browser: the installed Microsoft Edge in headless mode, driven by `playwright-core` (no browser download). Scripts load the production build served by Django, fill the example trip, find routes, switch intervals and layers, play the timeline, and record screenshots, console errors, failed requests and frame timing.

**Bug found.** The first run showed a blank map in the production build. MapLibre GL v6 loads its web worker from a file next to its own module (`maplibre-gl-worker.mjs`). After bundling, that file did not exist, the request returned 404, and the map never finished loading. Development mode hid this because Vite serves `node_modules` directly.

**Fix.** The worker is imported with Vite's `?url` suffix, so it is emitted as a hashed asset, and its URL is passed to MapLibre's `setWorkerUrl`. Verified: the worker is served with `text/javascript`, the map renders, and runs report 0 console errors.

**Other fixes from the screenshots.**
- ETA labels only appeared from zoom 5.5, so the starting view showed none. They now start at zoom 3.5, and MapLibre's label collision keeps as many as fit, with origin and destination first.
- On phones the map attribution opened expanded and covered a third of the map. It now starts collapsed behind its (i) button.
- The checkpoint table was wider than the sidebar (the Snow column was cut off). Units moved to the caption and cell padding was tightened; it now fits exactly.
- Place-search cache keys contained spaces and commas, which Django warns are unsafe for memcached. Keys are now hashed.

---

## DR-022: Departure-time advisor

**Problem it solves.** When every route crosses bad weather, "which route" is the wrong question; "when should I leave" is the right one.

**How it works.** The same 3 routes are re-scored as if the truck left 0 to 24 hours later, in 1 hour steps. Route geometry and driving times are reused and only the time each checkpoint is reached moves, so its forecast changes. For each departure the normal ranking picks the best route. The forecast window extends by 24 hours for the same locations, so this adds no forecast locations.

**What is suggested.** The safest departure in the window (the earliest one if several tie), and only when it is strictly safer than leaving as planned. "Safer" compares everything the ranking compares except travel time. The first version suggested the *earliest* departure that was safer at all. A test showed why that is wrong: with a storm clearing over 4 hours it suggested waiting 1 hour to trim 25 of 100 Severe miles, when waiting 4 hours avoids the storm entirely.

**Assumption, stated in the UI.** Driving times for later departures are the ones TomTom gave for the planned departure. Traffic at other times of day is not re-queried, which would cost 24 more routing calls per plan.

**UI.** A 25-cell strip (planned departure, then +1 h to +24 h), each cell colored by the worst level on that departure's best route, a sentence such as "Leaving at Wed 9:00 AM (6 h later) avoids 42 mi of Severe", and a button to plan that departure. Any cell can be selected to re-plan; the form updates to the new time.

**Tests.** 7 domain tests (offsets, shifted arrival times, the best route changing with departure time, no suggestion when the planned time is already safest or when later is only faster) and 2 API tests (24 hour coverage, waiting out a storm that covers every route).

**Cost.** The first version took 270 ms per plan for 14,400 forecast lookups. Remembering lookups by (cell, time) and caching each route's timing profile with the route brought a repeated plan back to about 0.1 s.

---

## DR-023: Staying inside the free weather quota

**Found while testing.** Open-Meteo returned `429 Minutely API request limit exceeded`. Controlled tests showed the free tier counts **each location** in a multi-location request as one call, whatever the number of variables: 3 requests of 250 locations went through (the limit is checked before a request is counted), and the next was refused. Limits are 600 per minute, 5,000 per hour and 10,000 per day.

**Measured cost before the fix (Chicago to Denver).** 414 checkpoint locations (all three intervals) plus 425 heatmap points: about 840 calls per new trip. That allowed only about 12 new long trips per day, and a second one within a minute failed.

**Options measured.**

| Change | Locations |
|---|---|
| Coarser snapping for checkpoints (0.05 to 0.10 or 0.15 degrees) | 414 to 404 or 350, little gain |
| Only the selected interval (25 mi) | 139 |
| Heatmap grid capped at 300 points instead of 600 | 260 (0.45 degree spacing) instead of 423 |

**Decision.**
- A plan request covers one sampling interval (default 25 mi). Switching interval is a new request: about 0.7 s when routes are cached, and switching back is instant from the browser cache. The previous results stay on screen, dimmed, while the new ones load.
- The heatmap grid is capped at 300 points. The blurred rendering (DR-020) hides the coarser spacing well.
- On a per-minute 429 the client waits for the next minute and retries once (the window resets on the minute). Hourly or daily limits, or a second 429, return `503 weather_busy` with a plain message instead of a generic error.
- Gunicorn's timeout is 120 s, so a request that waits out the minute is not cut off.

**Result.** A new Chicago to Denver trip now costs about 400 calls instead of 840: roughly 25 new long trips per day, with repeated or similar trips served from the 30-minute forecast cache. Measured in the browser: first plan 5.7 s, switch to 10 mi 0.7 s, back to 25 mi 0.1 s with no request, and the heatmap fetched once. A paid Open-Meteo plan would remove the limits for production use.

**Tests.** The per-minute retry (waits until the next minute plus 1 s, then succeeds), a second 429 giving up, hourly and daily limits failing fast without waiting, the 503 mapping, single-interval responses for 10, 25 and 50 miles, and an unknown interval being rejected.

---

## DR-024: Trucks on the timeline

**Why.** The heatmap shows where the weather is; the checkpoints show when the truck gets there. A marker per route that moves with the slider puts both in one picture: you can watch a truck drive into, or around, a storm.

**How.** Each truck's distance at a moment comes from the checkpoint arrival times (linear between two checkpoints), so it follows the same traffic-aware timing as the ETAs, not an average speed. The distance is then placed along the drawn road line, scaled because the simplified line is slightly shorter than the routing API's distance. Before departure the truck waits at the origin and after arrival it stays at the destination, both drawn faded. Positions only exist for the departure-anchored timeline; with "From now" a truck that has not left yet waits at the origin.

**Performance.** Updating three points per slider step is a tiny GeoJSON update. Playback measured 91 to 95 fps in headless Edge with trucks and heatmap animating together (127 fps with the heatmap alone).

**Tests.** 4 unit tests: waiting before departure, following uneven arrival times (a quarter of the way after 30 minutes when the first half takes 1 hour), parking at the destination, and feature properties.

**QA note.** An automated check first reported that slider keys were ignored right after loading. The cause was the test's text selector: "At departure" matched "plan th*at departure*" in the advisor text, so the test acted while the heatmap was still loading and the slider was correctly disabled. Scoped to the timeline, the slider responds as expected.

---

## DR-025: Hours-of-service rest breaks

**Why.** A truck cannot drive Chicago to Denver in one 15 hour stretch. Federal hours-of-service rules for property-carrying drivers require a 30 minute break after 8 hours of driving and limit driving to 11 hours before 10 consecutive hours off duty. Rests move when the truck reaches each checkpoint, which changes the forecast it meets.

**Model.** A driving day is 8 h driving, a 30 min break and 3 h driving (11.5 h on duty, inside the 14 hour window), followed by 10 h off if more driving remains. A rest is only added before more driving, so a trip of exactly 8 h or 11 h gets none. The 60/70 hour weekly limits are not modelled; one trip here does not approach them, and the driver's recent hours are unknown.

**Where it applies.** It is a switch on the trip form, off by default so the core results match the brief. When on, checkpoint arrival times, the route's arrival, the travel time used for ranking and the departure advisor all use elapsed time including rests. Routes report driving time and rest time separately.

**Effect on ranking, stated precisely.** Elapsed time always grows with driving time, so rests never change which route is faster. They change how much faster it is, and therefore the trade-off note: for 11.2 h vs 10.9 h of driving the gap grows from 18 minutes to over 10 hours, because only the longer route crosses the 11 hour limit. They also change which hour each checkpoint is reached, which can change the risk ranking itself.

**Measured.** Chicago to Denver, 14.9 h of driving: "25 h 22 min including 10 h 30 min of rest, arrives Thu 4:52 AM" (one 30 minute break and one 10 hour rest).

**Tests.** 13 rule tests (break and rest boundaries, multi-day trips, never decreasing), a checkpoint test (driving time unchanged, ETA uses the clock), an advisor test (later departures keep the rests), and 3 API tests (off by default, a 20 h drive arriving 31 h after departure with the rest between two checkpoints, and the widened time gap in the ranking reason).

---

## DR-026: Simulated storm demo mode

**Problem.** During development the real forecast was calm along every test corridor: every checkpoint Low, nothing on the heatmap, no load rule ever applying. That hides most of what the app does, including in a walkthrough recorded on a calm day.

**Decision.** A demo mode, switched on only by opening the page with `?demo=storm`, lays a synthetic winter storm over the real forecast:
- centred 40% of the way along the fastest route, strongest when that route's truck would arrive there, building up over 2 hours and fading to nothing over 14 hours;
- 62 mph winds and 2.6 in/hr of snow at the centre, falling to zero at 180 km, so the ring around the core passes through every wind band the load rules use;
- the worse of real and simulated values wins at each point, and missing real data stays missing.

The storm is applied after the real forecast is fetched and cached, so cached data is never altered. The plan response reports it (`simulation`), the heatmap request sends it back so the map shows the same storm, and requests without the flag are never touched (tested).

**Labelling.** Every view in demo mode shows a warning banner in the sidebar ("Simulated storm. The weather on this page is made up...") and a filled banner on the map, so a screenshot can never pass as a real forecast.

**What it shows (Chicago to Denver, measured).** Route A: 75 No Travel miles and 50 High miles, badged "Do not travel". Route B is recommended. The heatmap shows the storm on Route A between Lincoln and Des Moines and fading over the timeline.

**Wording fix found with it.** The guide sign's headline said "Fastest, with the same weather risk as the others" whenever travel time decided against the runner-up. With the storm, B and C tied on risk but A did not, so the sentence was false. It now reads "Fastest of the routes with the least weather risk", which is true in both cases.

**Tests.** 10 tests for the storm (full strength at the centre is No Travel, falloff with distance, nothing outside the radius, build-up and dissipation, the ring exercising the load rules, overlay rules) and 5 API tests (no simulation without the flag, the storm hitting the fastest route and moving the recommendation, an unknown demo rejected, the corridor showing the same storm, a bad simulation block rejected).

---

## DR-027: Shareable trip links

**Why.** A dispatcher shares a plan with a driver; a reviewer shares a scenario with a colleague. Both need the trip in the address.

**How.** After each plan the address holds the trip: origin and destination (coordinates and label), departure, load, spacing and the rest-break setting, plus `demo=storm` if demo mode is on. Opening such a link fills the form and plans the trip straight away. A departure that has already passed moves to the next quarter hour, so an old link still plans the same trip. A malformed link is ignored. "Copy link to this trip" copies the address.

**Precision.** Coordinates first used 5 decimals. Reopening a link then missed the server's route cache (the cache key uses the exact coordinates), TomTom recalculated with live traffic, and the result differed by 2 minutes from the original. Links now keep 6 decimals, the precision place search returns, and a reopened link reproduces the original plan exactly (checked in the browser).

**Tests.** 9 unit tests (round trip including labels with commas, demo mode kept, past departures moved, five malformed links ignored, unknown spacing falling back to 25 miles) and a browser check (address updates on interval change, the clipboard holds the address, a fresh page opens on the same trip, form and spacing restored).

---

## DR-028: Layout and map label review

**Why.** A screenshot review of the finished app, desktop and phone, found five things a reviewer would notice in the first minute. None broke a requirement; all made the main screen harder to read.

| Found | Change | Result |
|---|---|---|
| After planning, the full form stayed on top and the recommendation started halfway down the panel | The form folds into a two-line trip summary with "Edit trip"; editing shows the form again with "Keep the current trip" | The guide sign is the second thing in the panel on desktop |
| Route chips were pinned at fixed shares of each route (42%, 55%, 68%), so they stacked where routes shared a highway and covered arrival times | Each chip goes on the point of its route farthest from the other routes and chips (15% to 85% of the way, middle preferred among near-equal points). A transparent box of the chip's size is placed in the map's own label placement, so arrival times and place names under a chip give way | No chip overlaps another or a label in the Chicago to Denver and storm checks; 3 unit tests |
| On phones the timeline covered about half the map, and the map collapsed to its 320 px minimum | The timeline is a strip under the map on phones; the map is 58% of the screen height and frames the routes without room for an overlay; chips show only the letter and worst risk | Map 390 x 490 px, all of the trip in view, no horizontal scroll |
| Playback ran 6 forecast hours a second (48 h in 8 s), chosen for the heatmap before trucks were added; a truck crossed about 330 miles of map a second | Default 2 hours a second (48 h in 24 s), with a speed button for 1, 2 or 6 | In 2 s of play the recommended truck moves about 4 hours of driving, easy to follow |
| In "Best time to leave", one click on a bar re-planned the trip without saying what the bar was | Pointing at or selecting a bar shows it ("Leave Wed 5:45 PM (in 5 h): Route A, worst weather Low"); a separate "Plan this departure" button re-plans. The description says what a bar is | No accidental re-plans; the readout is announced to screen readers |

The rest-break note under the switch is now one line.

**Follow-up: trip end on the timeline.** The slider covers the 48 hour forecast, but trips end sooner (14 to 20 hours for Chicago to Denver). Past the last arrival the trucks sat stacked on the destination while the slider kept moving, which read as the two being out of step. Now each route's arrival is a lettered flag above the track (arrivals under 1.5 h apart share one flag), the status line says which trucks have arrived ("All trucks have arrived; the map shows only the forecast"), and an arrived truck leaves the map. 6 unit tests; checked in the browser at 16 h (A arrived, B and C driving) and 48 h.

**Checks.** Type check, lint, format and 61 unit tests pass. A browser tour (desktop 1440 x 900 and phone 390 x 844) covers the summary, route list, advisor hover and select, checkpoint popup, playback, layers, edit trip and storm mode, with no page or console errors.

---

## DR-029: Review against a scoring checklist

**Why.** Before submitting, the app was checked point by point against a reviewer-style checklist: exact thresholds, miles rather than checkpoint counts, No Travel handling, arrival-time weather, heatmap consistency and real-world latency.

| Check | Finding | Action |
|---|---|---|
| Every threshold tested below, at and above | Already tested at each edge, including 55 mph exactly, 30,000 and 40,000 lb exactly, rain 1.00 and snow 3.0 exactly. Missing: just-below values for rain (0.499, 0.999) and snow (0.99, 1.99, 2.99), wind 54 and 44 with loads, and a test that a load rule can never lower a level | Added those cases and a test where snow is No Travel and the 35 to 44 mph rule (Severe) must not win |
| Rank by miles, not checkpoint counts | Each checkpoint covers half the gap to each neighbor (DR-007), so miles per level add up to the route length at every spacing | None |
| No Travel cannot win quietly | Compared first (DR-007). When every route crosses No Travel the sign turns yellow, reads "Least risky: Route X" and says every route crosses No Travel conditions | None |
| Weather at arrival time, horizon | Arrival times from TomTom progress data (DR-003); times are compared as UTC timestamps; hours past the 16 day forecast are "No forecast" and a route without forecasts ranks last (DR-014) | None |
| Heatmap agrees with the checkpoints | **Did not.** The default heatmap layer was weather risk without the load rules, while the dots include them. At 35,000 lb in 50 mph wind a dot was No Travel over a Severe-colored area | Default layer is now "Risk for this load"; the other is labelled "Weather only (no load rules)". The legend says the dots show weather when the truck gets there and the shading shows the time on the slider |
| Real latency, not only call counts | Measured on the hosted app: new trip 5.2 s, repeat 0.6 s, heatmap 1.1 s, three concurrent new trips all done in 5.0 s without errors. Provider failures, timeouts and each kind of rate limit are covered by tests (502, 503 with a retry on the per-minute limit) | Numbers added to the README |
| Cache policy and what changes with accounts | Expiry per cache is explicit (10 min, 30 min, 24 h); a cache outage is treated as a miss | README now says what a database would look like if saved trips or accounts were added |

---

## DR-030: Hosting as deployed

**Plan (DR-011).** Azure Container Apps in East US, built with `az containerapp up`, Redis for the cache.

**What changed and why.**

| Step | Found | Done |
|---|---|---|
| Region | The Azure for Students subscription only allows Central India, Korea Central, Malaysia West, India South Central and UAE North | Central India. The server calls TomTom and Open-Meteo itself and map tiles come from a CDN, so the region adds little to what a reviewer waits for |
| Image build | Local Docker was not available | Built in the cloud with `az acr build` (Azure Container Registry, Basic). `.dockerignore` keeps `.env` out of the upload |
| Environment | The CLI created an "express" Container Apps environment, which does not support custom domains, and the subscription allows only one standard environment, already used by another project | The app runs in that existing standard environment as a separate app in its own resource group, so it can be removed without touching anything else |
| Cache | Redis would be a second paid service for a stateless app with light traffic | In-memory cache per worker (2 gunicorn workers, 1 replica, up to 2). A cold worker only means one slower first request. *Revised by DR-031: one worker with 8 threads* |
| Domain | | `truck-routing.zaidansari.tech`: a CNAME and an `asuid` TXT record, with an Azure managed certificate (HTTPS) |

**Settings.** 0.5 vCPU and 1 GiB, minimum 1 replica so there is never a cold start, maximum 2. The TomTom key and Django secret are Container Apps secrets referenced by environment variables. `DJANGO_DEBUG=false`, allowed hosts limited to the two host names.

**Cost.** About INR 350 a week (one mostly idle replica plus the registry), at most about INR 900 a week if the app were busy around the clock.

**Result.** Health check, home page and API docs return 200 on the custom domain. The browser tour (desktop and phone) runs with no page or console errors. Latency is in [DR-029](#dr-029-review-against-a-scoring-checklist): a new trip 5.2 s, a repeat 0.6 s, three concurrent trips all done in 5.0 s. `deploy/azure-container-apps.sh` reproduces the build and update steps.

**Flaky test found while checking the setup steps.** On a clean clone one storm test failed: the storm is sampled hourly and wind is interpolated to the arrival time, so its peak reaches the truck at 53 to 62 mph depending on the minute the test runs, and the test expected No Travel from wind alone. It now uses a 35,000 lb load (45 to 54 mph is No Travel above 30,000 lb) and runs at four fixed departures, on the hour and at 15, 30 and 45 minutes past. The app's behaviour was correct; only the test depended on the clock.

**Follow-up: demo mode was hard to find.** It was only reachable through `?demo=storm` in the address, so a reviewer on a calm day would see every route Low and never see the rules at work. Now the start screen offers "try it with a simulated storm", "How it works" opens with a link to it, and the demo banner has a "Show real forecasts" link back. Checked in the browser: each link switches mode and the banners follow. The start screen hint goes away once a trip is planned, so the results also offer "Try it in a simulated storm", which reopens the same trip with the storm on.

---

## DR-031: Pre-submission audit

**Why.** A last pass over the four things the work is judged on: the routing, weather and risk logic, the map and timeline performance, code quality, and the docs. Each finding below was reproduced before it was fixed, and each fix has a test or a measurement.

**Logic.**

| Found | Fixed |
|---|---|
| A value could look like it sat in a different band: wind 34.96 mph showed as "35" next to Moderate, rain 0.248 in/hr as "0.25" next to Moderate | Wind is rounded to 0.1 mph before it is classified, and every view shows wind to 0.1 mph and rain and snow to up to 0.001 in/hr. All 145 checkpoints of the storm demo were checked against the brief's table from the values on screen |
| The wind, rain and snow heatmap layers used whole mph and hundredths of an inch, so a layer could change color at a different value than a checkpoint changes level | The corridor sends wind in tenths of a mph and rain and snow in thousandths of an inch, the same precision checkpoints are classified at |
| A route just over a multiple of the spacing (100.06 mi at 25 mi) left the destination checkpoint covering 0.03 mi. No Travel there rounded to 0.0 miles in the ranking while the route was still badged "Do not travel" | A regular checkpoint within a mile of the destination is left out, so the destination covers a real stretch of road |
| Gusts are the hour's peak while wind is interpolated toward the next hour, so a gust could read lower than the wind | Gusts are shown as at least the sustained wind |
| Travel times were compared to the second but shown to the minute ("Shortest travel time: 1 h vs 1 h") | Compared in whole minutes, like the other criteria (DR-008) |
| A cached forecast hour merged into a newer entry kept being served past its 30 minutes | Each cached hour keeps its own fetch time |

**Performance.** Measured on the production build in Chrome, Chicago to Denver, playback at 2 forecast hours a second, normal CPU and 4x CPU slowdown (a slower laptop).

| Found | Fixed | Before | After |
|---|---|---|---|
| The slider's thumb and fill lagged behind playback and stuck after a reset: MUI eases them over 150 ms, and playback sets the value every frame, which restarted the easing each time | Easing turned off on the thumb and track | After 12 s of play the value was 24.75 h and the thumb was drawn at 0.96 h | Within 0.12 h at every sample, and Play after the end starts at 0 h |
| Trucks were a GeoJSON source updated with `setData` every frame, which makes the map re-tile the source and redo label placement | Trucks are three DOM markers moved with `setLngLat` | 4x: 34 to 38 fps | 4x: about 40 to 65 fps across repeated runs (CPU slowdown emulation varies run to run), no long tasks |
| A new heatmap paint expression makes MapLibre rebuild the layer's tiles, and playback set one every frame | The shading moves in quarter-hour steps (the slider's step), and an unchanged step is skipped | about 4 tile rebuilds per frame | 8 a second at 2 h/s |
| The timeline's toggle, layer menu and arrival flags re-rendered every frame | Memoized | about 130 component renders per frame | the slider and readout only |
| The panel grew from 127 to 160 px when "Route A has arrived" wrapped the controls, so the slider jumped during playback | Controls share a row with the clock, and the description has two lines reserved | 2 heights | 153 px throughout |
| The 1.95 MB script was served uncompressed with a 60 s cache | Compressed at build time (561 KB gzipped) and split into app, MUI, MapLibre and vendor files; hashed files are cached for a year | | |

At normal CPU playback holds the display's 165 fps in both cases.

**Behavior.** A checkpoint popup now closes when the route or plan changes. Changing the spacing keeps the driver's zoom (the map only re-frames when the roads change). Playback stops while the timeline reloads, and a new trip starts its timeline at hour 0. Phones get a one-line risk legend, and checkpoint dots have a dark ring so yellow stays visible on the light basemap.

**Follow-up: three smaller fixes.**

| Found | Fixed |
|---|---|
| Frames start on the hour before the departure, so with a 2:40 departure slider hour 48 is 48.67 h into the frames, past the last one: the shading held still for the final 40 minutes | The corridor returns 50 frames (hours 0 to 49); the slider still runs 0 to 48 h |
| Selecting a route rebuilt all three route chips and their label space (one 164 ms task at 4x CPU slowdown) | Chips are built once per plan; selecting only flips their selected and recommended attributes |
| Opening a shared link searched for the two pre-filled place names, two wasted TomTom requests | Place search runs only on what the user types, not on the label the field fills in itself |

**Security and hosting.**

| Found | Fixed |
|---|---|
| The per-address rate limit keyed on the whole `X-Forwarded-For` header, so a client could add any address to it and get a fresh limit | `NUM_PROXIES = 1` (the Container Apps ingress is the only proxy), with a test that two spoofed headers share one limit |
| `/api/corridor/` accepted 1,000 points while a plan's grid never has more than 300, and every point costs one forecast request | Capped at the grid's 300 |
| Two gunicorn workers each had their own cache and rate-limit counts | One worker with 8 threads; the work is mostly waiting on TomTom and Open-Meteo |
| `check --deploy` warnings | Added the clickjacking middleware and HSTS |
| The API docs page listed a `rankings` field the API does not return | The schema lists the real top-level fields |

**Hosted, after the deploy.** A repeat plan dropped from 0.14 to 0.6 s to 0.08 s, since every request on the replica now shares one cache. Three new trips at once all finished in 4.1 s without errors, so one worker with threads loses nothing to two workers here.

**Checks.** 288 backend tests at 100% line and branch coverage, 68 frontend tests, ruff, oxlint, Prettier and the TypeScript build pass.
