import { describe, expect, it } from 'vitest'
import type { Checkpoint, Plan, RouteOption } from '../api/types.ts'
import { haversineMi } from './mapData.ts'
import { buildTracks, truckAt, truckFeatures } from './trucks.ts'

const DEG_MI = haversineMi([0, 0], [1, 0])
const DEPART = Date.parse('2026-10-22T12:00:00Z') / 1000

function checkpoint(index: number, mile: number, hoursAfter: number): Checkpoint {
  return {
    index,
    mile,
    lat: 0,
    lon: mile / DEG_MI,
    eta: new Date((DEPART + hoursAfter * 3600) * 1000).toISOString(),
    covered_miles: 0,
    forecast: true,
    level: 'Low',
  }
}

// 2 degrees east along the equator; the first half is driven in 1 h, the second half in 3 h.
const ROUTE: RouteOption = {
  id: 'A',
  source: 'tomtom',
  distance_mi: 2 * DEG_MI,
  duration_s: 4 * 3600,
  driving_s: 4 * 3600,
  rest_s: 0,
  traffic_delay_s: 0,
  arrival: '2026-10-22T16:00:00Z',
  geometry: [
    [0, 0],
    [1, 0],
    [2, 0],
  ],
  checkpoints: [checkpoint(0, 0, 0), checkpoint(1, DEG_MI, 1), checkpoint(2, 2 * DEG_MI, 4)],
  summary: {} as never,
}

const PLAN = { routes: [ROUTE], ranking: { recommended_id: 'A' } } as unknown as Plan
const [track] = buildTracks(PLAN)

describe('truckAt', () => {
  it('waits at the origin before departure', () => {
    expect(truckAt(track, DEPART - 600)).toEqual({ coordinates: [0, 0], state: 'waiting' })
  })

  it('follows the arrival times, not an average speed', () => {
    // 30 minutes in: halfway through the fast first hour, so a quarter of the trip
    expect(truckAt(track, DEPART + 1800).coordinates[0]).toBeCloseTo(0.5, 6)
    // 2.5 hours in: halfway through the slow second part
    expect(truckAt(track, DEPART + 2.5 * 3600).coordinates[0]).toBeCloseTo(1.5, 6)
  })

  it('parks at the destination after arrival', () => {
    expect(truckAt(track, DEPART + 5 * 3600)).toEqual({ coordinates: [2, 0], state: 'arrived' })
  })
})

describe('truckFeatures', () => {
  it('has one point per route with its state and recommendation', () => {
    const fc = truckFeatures([track], DEPART + 3600)
    expect(fc.features[0].properties).toEqual({ id: 'A', recommended: true, state: 'driving' })
  })
})
