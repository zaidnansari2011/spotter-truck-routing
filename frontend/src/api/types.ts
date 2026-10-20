// Mirrors the Django API responses (backend/planner/services/trip.py and corridor.py).

export type LevelLabel = 'Low' | 'Moderate' | 'High' | 'Severe' | 'No Travel'
export type IntervalKey = '10' | '25' | '50'
export const INTERVALS: IntervalKey[] = ['10', '25', '50']

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface Checkpoint {
  index: number
  mile: number
  lat: number
  lon: number
  eta: string
  covered_miles: number
  forecast: boolean
  level: LevelLabel | null
  level_score?: number
  weather_level?: LevelLabel
  factors?: string[]
  load_rule?: string | null
  wind_mph?: number
  gust_mph?: number | null
  rain_in_hr?: number
  snow_in_hr?: number
}

export interface RouteSummary {
  miles_by_level: Record<LevelLabel, number>
  unknown_miles: number
  avg_risk: number | null
  do_not_travel: boolean
}

export interface RouteOption {
  id: string
  source: 'tomtom' | 'via-waypoint'
  distance_mi: number
  duration_s: number
  traffic_delay_s: number
  arrival: string
  geometry: [number, number][] // [lon, lat]
  intervals: Record<IntervalKey, { checkpoints: Checkpoint[]; summary: RouteSummary }>
}

export interface Comparison {
  other_id: string
  decided_by: string
  reason: string
}

export interface Ranking {
  order: string[]
  recommended_id: string
  comparisons: Comparison[]
  tradeoff: { faster_id: string; saving_s: number; note: string } | null
  all_no_travel: boolean
}

export interface DepartureOption {
  offset_h: number
  departure: string
  route_id: string
  worst_level: LevelLabel | null
  no_travel_miles: number
  severe_miles: number
  high_miles: number
  avg_risk: number | null
  arrival: string
}

export interface DepartureAdvice {
  options: DepartureOption[]
  suggestion: DepartureOption | null
}

export interface Plan {
  departure: string
  load_lb: number
  generated_at: string
  routes: RouteOption[]
  rankings: Record<IntervalKey, Ranking>
  departure_options: Record<IntervalKey, DepartureAdvice>
  notices: string[]
  corridor: { points: [number, number][]; spacing_deg: number }
  assumptions: Record<string, unknown>
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string
  load_lb: number
}

export type HeatLayer = 'risk' | 'risk_load' | 'wind' | 'rain' | 'snow'

export interface CorridorFrames extends Record<HeatLayer, (number | null)[][]> {
  hours: number[] // unix seconds, hour 0 to 48
}
