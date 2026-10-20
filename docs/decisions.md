# Decision log

Every significant choice in this project, with the options considered, what was tested, the measured results, and why the final option won. Newest entries at the bottom. Measurements were taken from a development machine unless noted, so absolute latencies are indicative.

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
| [DR-009](#dr-009-forecast-slider-start-time) | Forecast slider start time | Accepted |
| [DR-010](#dr-010-map-rendering-maplibre-gl) | Map rendering: MapLibre GL | Accepted |
| [DR-011](#dr-011-hosting-azure-container-apps) | Hosting: Azure Container Apps | Accepted |
| [DR-012](#dr-012-stateless-backend-no-database) | Stateless backend, no database | Accepted |
| [DR-013](#dr-013-continuous-risk-index-for-the-heatmap) | Continuous risk index for the heatmap | Accepted |
| [DR-014](#dr-014-routes-without-a-forecast-rank-last) | Routes without a forecast rank last | Accepted |

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

**Decision.** Hour 0 is the departure time, which is "now" by default. A Departure / Now toggle switches to hours from the current time. Every slider position shows the clock time and the forecast lead, e.g. "Thu 06:00, forecast +33 h". Both windows are fetched up front, so the toggle is instant.

---

## DR-010: Map rendering: MapLibre GL

**Context.** UI, map and heatmap smoothness is 40% of the evaluation. The slider must update the heatmap while dragging.

**Decision.** MapLibre GL JS (WebGL) with OpenFreeMap vector tiles, so there is no map token in the browser. The heatmap is one data source holding all 49 hourly frames. The slider changes only the layer's paint expression, so dragging triggers no network requests and no data re-upload, just GPU work. Results will be measured and added here.

---

## DR-011: Hosting: Azure Container Apps

**Decision.** One Docker image (Django serving the built React app) on Azure Container Apps with at least 1 replica always running, so reviewers never hit a cold start. Redis on Azure Managed Redis, with an in-memory fallback so a cache outage cannot break the app. Secrets live in Container Apps secrets, never in the image or the repo.

---

## DR-012: Stateless backend, no database

**Context.** Every plan is computed from the request (places, departure, load) plus live routing and forecast data. Nothing has to be stored per user.

**Decision.** No database and no auth. Django runs with `DATABASES = {}`, and Redis caches the slow upstream calls (routes per request, forecasts per location and hour). If Redis is unreachable, cache errors are treated as misses, so the app keeps working, only slower.

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
