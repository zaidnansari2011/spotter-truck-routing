import { describe, expect, it } from 'vitest'
import type { Checkpoint, Plan, RouteOption } from '../api/types.ts'
import { haversineMi } from './mapData.ts'
import { arrivalNote, buildTracks, groupArrivals, truckAt, truckFeatures } from './trucks.ts'

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

describe('arrivalNote', () => {
  const list = [
    { id: 'A', ts: 100, recommended: true },
    { id: 'B', ts: 200, recommended: false },
    { id: 'C', ts: 300, recommended: false },
  ]

  it('says nothing while every truck is still on the road', () => {
    expect(arrivalNote(list, 99)).toBeUndefined()
  })

  it('names the trucks that have arrived', () => {
    expect(arrivalNote(list, 100)).toBe('Route A has arrived')
    expect(arrivalNote(list, 250)).toBe('Routes A and B have arrived')
  })

  it('says when the map shows only the forecast', () => {
    expect(arrivalNote(list, 300)).toBe('All trucks have arrived; the map shows only the forecast')
    expect(arrivalNote(list.slice(0, 1), 100)).toBe(
      'The truck has arrived; the map shows only the forecast',
    )
  })
})

describe('groupArrivals', () => {
  const at = (id: string, hours: number) => ({ id, ts: hours * 3600, recommended: false })

  it('places arrivals in hours from the slider start, earliest first', () => {
    const groups = groupArrivals([at('B', 20), at('A', 14)], 0)
    expect(groups.map((g) => [g.hour, g.items.map((a) => a.id)])).toEqual([
      [14, ['A']],
      [20, ['B']],
    ])
  })

  it('shares a flag between arrivals close together', () => {
    const groups = groupArrivals([at('A', 14), at('B', 16.5), at('C', 16.75)], 0)
    expect(groups.map((g) => g.items.map((a) => a.id))).toEqual([['A'], ['B', 'C']])
  })

  it('leaves out arrivals outside the window', () => {
    expect(groupArrivals([at('A', 2), at('B', 60)], 3 * 3600)).toEqual([])
  })
})
