import type { Plan, RouteOption } from '../api/types.ts'
import { cumulativeMi } from './mapData.ts'

export type TruckState = 'waiting' | 'driving' | 'arrived'

export interface Track {
  id: string
  recommended: boolean
  etaTs: number[] // checkpoint arrival times, seconds
  mile: number[] // checkpoint miles (routing API distances)
  line: [number, number][] // simplified road line, [lon, lat]
  lineMi: number[] // distance along the line at each vertex
  scale: number // line miles per API mile (the simplified line is slightly shorter)
}

/** Precompute what is needed to place each route's truck quickly while the slider moves. */
export function buildTracks(plan: Plan): Track[] {
  return plan.routes.map((route: RouteOption) => {
    const lineMi = cumulativeMi(route.geometry)
    return {
      id: route.id,
      recommended: route.id === plan.ranking.recommended_id,
      etaTs: route.checkpoints.map((c) => Date.parse(c.eta) / 1000),
      mile: route.checkpoints.map((c) => c.mile),
      line: route.geometry,
      lineMi,
      scale: lineMi[lineMi.length - 1] / route.distance_mi,
    }
  })
}

/** Where a truck is at `ts`: miles driven come from the checkpoint arrival times. */
export function truckAt(
  track: Track,
  ts: number,
): { coordinates: [number, number]; state: TruckState } {
  const { etaTs, mile } = track
  if (ts <= etaTs[0]) return { coordinates: track.line[0], state: 'waiting' }
  if (ts >= etaTs[etaTs.length - 1])
    return { coordinates: track.line[track.line.length - 1], state: 'arrived' }
  let i = 1
  while (etaTs[i] < ts) i++
  const t = (ts - etaTs[i - 1]) / (etaTs[i] - etaTs[i - 1])
  const driven = mile[i - 1] + (mile[i] - mile[i - 1]) * t
  return { coordinates: alongLine(track, driven * track.scale), state: 'driving' }
}

function alongLine(track: Track, mi: number): [number, number] {
  const { line, lineMi } = track
  let i = 1
  while (i < lineMi.length - 1 && lineMi[i] < mi) i++
  const span = lineMi[i] - lineMi[i - 1]
  const t = span > 0 ? Math.min(Math.max((mi - lineMi[i - 1]) / span, 0), 1) : 0
  return [
    line[i - 1][0] + (line[i][0] - line[i - 1][0]) * t,
    line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t,
  ]
}

export interface Arrival {
  id: string
  ts: number // arrival, unix seconds
  recommended: boolean
}

export function arrivals(plan: Plan): Arrival[] {
  return plan.routes.map((route) => ({
    id: route.id,
    ts: Date.parse(route.arrival) / 1000,
    recommended: route.id === plan.ranking.recommended_id,
  }))
}

/** Which trucks have finished their trip at `ts`, in words, or undefined if none has. */
export function arrivalNote(list: Arrival[], ts: number): string | undefined {
  const arrived = list.filter((a) => a.ts <= ts).map((a) => a.id)
  if (!arrived.length) return undefined
  if (arrived.length === list.length) {
    return list.length === 1
      ? 'The truck has arrived; the map shows only the forecast'
      : 'All trucks have arrived; the map shows only the forecast'
  }
  if (arrived.length === 1) return `Route ${arrived[0]} has arrived`
  return `Routes ${arrived.slice(0, -1).join(', ')} and ${arrived.at(-1)} have arrived`
}

/**
 * Arrivals inside the 0 to 48 h window, as slider positions in hours from `startTs`. Arrivals
 * closer than `minGapH` share one flag so their letters do not overlap.
 */
export function groupArrivals(
  list: Arrival[],
  startTs: number,
  lastHour = 48,
  minGapH = 1.5,
): { hour: number; items: Arrival[] }[] {
  const groups: { hour: number; items: Arrival[] }[] = []
  const inWindow = list
    .map((a) => ({ arrival: a, hour: (a.ts - startTs) / 3600 }))
    .filter((a) => a.hour >= 0 && a.hour <= lastHour)
    .sort((a, b) => a.hour - b.hour)
  for (const { arrival, hour } of inWindow) {
    const last = groups.at(-1)
    if (last && hour - last.hour < minGapH) last.items.push(arrival)
    else groups.push({ hour, items: [arrival] })
  }
  return groups
}
