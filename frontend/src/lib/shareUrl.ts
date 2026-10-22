import type { IntervalKey, Place, PlanRequest } from '../api/types.ts'
import { INTERVALS } from '../api/types.ts'

/** Trip inputs in the page address, so a planned trip can be shared or reloaded. */
export function encodeTrip(
  request: PlanRequest,
  interval: IntervalKey,
  keep: URLSearchParams,
): string {
  const params = new URLSearchParams()
  if (keep.get('demo')) params.set('demo', keep.get('demo')!)
  params.set('from', encodePlace(request.origin))
  params.set('to', encodePlace(request.destination))
  params.set('depart', request.departure)
  params.set('load', String(request.load_lb))
  params.set('mi', interval)
  if (request.hos) params.set('hos', '1')
  return params.toString()
}

/**
 * The trip in a shared link, or null if the link has none or it is malformed. A departure that has
 * already passed is moved to `fallbackDeparture`, so an old link still plans the same trip.
 */
export function decodeTrip(
  search: string,
  fallbackDeparture: string,
  now: number = Date.now(),
): { request: PlanRequest; interval: IntervalKey } | null {
  const params = new URLSearchParams(search)
  const origin = decodePlace(params.get('from'))
  const destination = decodePlace(params.get('to'))
  const load = Number(params.get('load'))
  const departure = params.get('depart') ?? ''
  if (!origin || !destination || !Number.isFinite(load) || Number.isNaN(Date.parse(departure))) {
    return null
  }
  const mi = INTERVALS.find((key) => key === params.get('mi'))
  return {
    request: {
      origin,
      destination,
      departure: Date.parse(departure) < now ? fallbackDeparture : departure,
      load_lb: load,
      hos: params.get('hos') === '1',
    },
    interval: mi ?? '25',
  }
}

function encodePlace(place: Place): string {
  // 6 decimals, the precision place search returns, so a reopened link reuses cached routes.
  return `${place.lat.toFixed(6)},${place.lon.toFixed(6)},${place.label}`
}

function decodePlace(text: string | null): Place | null {
  if (!text) return null
  const [lat, lon, ...label] = text.split(',')
  const place = { lat: Number(lat), lon: Number(lon), label: label.join(',').trim() }
  const valid =
    Number.isFinite(place.lat) &&
    Number.isFinite(place.lon) &&
    Math.abs(place.lat) <= 90 &&
    Math.abs(place.lon) <= 180 &&
    place.label.length > 0
  return valid ? place : null
}
