import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type { Plan, RouteOption } from '../api/types.ts'
import { formatClock } from './format.ts'
import { levelColor } from './risk.ts'

type LonLat = [number, number]

const EARTH_RADIUS_MI = 3958.7613

export function haversineMi([lon1, lat1]: LonLat, [lon2, lat2]: LonLat): number {
  const rad = Math.PI / 180
  const h =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.sqrt(h))
}

/** Distance from the start to each vertex, in miles. */
export function cumulativeMi(coords: LonLat[]): number[] {
  const totals = [0]
  for (let i = 1; i < coords.length; i++)
    totals.push(totals[i - 1] + haversineMi(coords[i - 1], coords[i]))
  return totals
}

function pointAt(coords: LonLat[], cum: number[], mi: number): LonLat {
  if (mi <= 0) return coords[0]
  const last = coords.length - 1
  if (mi >= cum[last]) return coords[last]
  let i = 1
  while (cum[i] < mi) i++
  const span = cum[i] - cum[i - 1]
  const t = span > 0 ? (mi - cum[i - 1]) / span : 0
  return [
    coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t,
    coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t,
  ]
}

/** The part of a polyline between two distances (miles along the line). */
export function sliceLine(
  coords: LonLat[],
  cum: number[],
  startMi: number,
  endMi: number,
): LonLat[] {
  const inside = coords.filter((_, i) => cum[i] > startMi && cum[i] < endMi)
  return [pointAt(coords, cum, startMi), ...inside, pointAt(coords, cum, endMi)]
}

/** Point a share of the way along a line, e.g. 0.5 for the middle. */
export function pointAlong(coords: LonLat[], fraction: number): LonLat {
  const cum = cumulativeMi(coords)
  return pointAt(coords, cum, cum[cum.length - 1] * fraction)
}

/**
 * The selected route split into stretches colored by the checkpoint that covers them.
 * Checkpoint miles come from the routing API; they are scaled onto the simplified map line,
 * whose length differs slightly.
 */
export function riskSegments(route: RouteOption): FeatureCollection<LineString> {
  const cum = cumulativeMi(route.geometry)
  const scale = cum[cum.length - 1] / route.distance_mi
  const checkpoints = route.checkpoints
  const features = checkpoints.map((cp, i): Feature<LineString> => {
    const start = i === 0 ? 0 : (checkpoints[i - 1].mile + cp.mile) / 2
    const end =
      i === checkpoints.length - 1 ? route.distance_mi : (cp.mile + checkpoints[i + 1].mile) / 2
    return {
      type: 'Feature',
      properties: { color: levelColor(cp.level) },
      geometry: {
        type: 'LineString',
        coordinates: sliceLine(route.geometry, cum, start * scale, end * scale),
      },
    }
  })
  return { type: 'FeatureCollection', features }
}

export function routeLines(plan: Plan, selectedId: string): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: plan.routes.map((route) => ({
      type: 'Feature',
      id: route.id.charCodeAt(0),
      properties: { id: route.id, selected: route.id === selectedId },
      geometry: { type: 'LineString', coordinates: route.geometry },
    })),
  }
}

export function checkpointPoints(route: RouteOption): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: route.checkpoints.map((cp) => ({
      type: 'Feature',
      properties: {
        index: cp.index,
        color: levelColor(cp.level),
        eta: formatClock(cp.eta),
        // Last checkpoint is the destination; label it even when it sits close to the previous one.
        endpoint: cp.index === 0 || cp.index === route.checkpoints.length - 1,
      },
      geometry: { type: 'Point', coordinates: [cp.lon, cp.lat] },
    })),
  }
}

export function planBounds(plan: Plan): [LonLat, LonLat] {
  const all = plan.routes.flatMap((r) => r.geometry)
  const lons = all.map((p) => p[0])
  const lats = all.map((p) => p[1])
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ]
}
