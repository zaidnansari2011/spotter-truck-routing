import { describe, expect, it } from 'vitest'
import type { Checkpoint, Plan, RouteOption } from '../api/types.ts'
import {
  cumulativeMi,
  haversineMi,
  planBounds,
  pointAlong,
  riskSegments,
  routeLines,
  sliceLine,
} from './mapData.ts'
import { LEVELS } from './risk.ts'

// A straight east-west line along the equator: one degree of longitude is about 69.1 miles.
const LINE: [number, number][] = [
  [0, 0],
  [1, 0],
  [2, 0],
  [3, 0],
]
const DEG_MI = haversineMi([0, 0], [1, 0])

function checkpoint(mile: number, level: Checkpoint['level']): Checkpoint {
  return {
    index: 0,
    mile,
    lat: 0,
    lon: mile / DEG_MI,
    eta: '2026-10-22T12:00:00Z',
    covered_miles: 0,
    forecast: !!level,
    level,
  }
}

function route(checkpoints: Checkpoint[], distance = 3 * DEG_MI): RouteOption {
  const interval = {
    checkpoints: checkpoints.map((c, i) => ({ ...c, index: i })),
    summary: {} as never,
  }
  return {
    id: 'A',
    source: 'tomtom',
    distance_mi: distance,
    duration_s: 3600,
    traffic_delay_s: 0,
    arrival: '2026-10-22T13:00:00Z',
    geometry: LINE,
    intervals: { '10': interval, '25': interval, '50': interval },
  }
}

describe('distances', () => {
  it('one degree of longitude at the equator is about 69.1 miles', () => {
    expect(DEG_MI).toBeCloseTo(69.1, 1)
  })

  it('accumulates along the line', () => {
    const cum = cumulativeMi(LINE)
    expect(cum[0]).toBe(0)
    expect(cum[3]).toBeCloseTo(3 * DEG_MI, 6)
  })
})

describe('sliceLine', () => {
  const cum = cumulativeMi(LINE)

  it('cuts inside segments and keeps the vertices between the cuts', () => {
    const part = sliceLine(LINE, cum, 0.5 * DEG_MI, 2.5 * DEG_MI)
    expect(part[0][0]).toBeCloseTo(0.5, 6)
    expect(part.slice(1, -1)).toEqual([
      [1, 0],
      [2, 0],
    ])
    expect(part.at(-1)![0]).toBeCloseTo(2.5, 6)
  })

  it('clamps to the ends of the line', () => {
    const part = sliceLine(LINE, cum, -5, 99_999)
    expect(part[0]).toEqual([0, 0])
    expect(part.at(-1)).toEqual([3, 0])
  })
})

describe('pointAlong', () => {
  it('finds the middle of the line', () => {
    expect(pointAlong(LINE, 0.5)[0]).toBeCloseTo(1.5, 6)
  })
})

describe('riskSegments', () => {
  it('splits the route halfway between checkpoints and colors each stretch', () => {
    const r = route([
      checkpoint(0, 'Low'),
      checkpoint(DEG_MI, 'Severe'),
      checkpoint(3 * DEG_MI, 'Moderate'),
    ])

    const segments = riskSegments(r, '25').features

    expect(segments).toHaveLength(3)
    expect(segments.map((s) => s.properties!.color)).toEqual([
      LEVELS[0].color,
      LEVELS[3].color,
      LEVELS[1].color,
    ])
    const ends = segments.map((s) => s.geometry.coordinates.at(-1)![0])
    expect(ends[0]).toBeCloseTo(0.5, 4) // halfway between mile 0 and the second checkpoint
    expect(ends[1]).toBeCloseTo(2, 4) // halfway between the second and the last
    expect(ends[2]).toBeCloseTo(3, 4)
  })

  it('stretches checkpoint miles onto a map line of a different length', () => {
    // The API reports twice the drawn length, so the stretch boundary at API mile 3 x DEG_MI
    // lands at 1.5 degrees on the map line.
    const r = route([checkpoint(0, 'Low'), checkpoint(6 * DEG_MI, 'High')], 6 * DEG_MI)

    const segments = riskSegments(r, '10').features

    expect(segments[0].geometry.coordinates.at(-1)![0]).toBeCloseTo(1.5, 4)
  })
})

describe('routeLines and bounds', () => {
  const plan = {
    routes: [
      { ...route([]), id: 'A', geometry: LINE },
      {
        ...route([]),
        id: 'B',
        geometry: [
          [0, -1],
          [3, 2],
        ] as [number, number][],
      },
    ],
  } as Plan

  it('marks the selected route', () => {
    const lines = routeLines(plan, 'B').features
    expect(lines.map((f) => f.properties!.selected)).toEqual([false, true])
  })

  it('covers every route', () => {
    expect(planBounds(plan)).toEqual([
      [0, -1],
      [3, 2],
    ])
  })
})
