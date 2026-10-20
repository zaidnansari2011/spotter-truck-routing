import { describe, expect, it } from 'vitest'
import type { DepartureOption, Ranking } from '../api/types.ts'
import { advisorGain, recommendationHeadline } from './explain.ts'

function ranking(overrides: Partial<Ranking> = {}): Ranking {
  return {
    order: ['A', 'B'],
    recommended_id: 'A',
    comparisons: [{ other_id: 'B', decided_by: 'duration', reason: '' }],
    tradeoff: null,
    all_no_travel: false,
    ...overrides,
  }
}

describe('recommendationHeadline', () => {
  it('explains a time-based pick as equal risk, faster', () => {
    expect(recommendationHeadline(ranking())).toBe(
      'Fastest of the routes with the least weather risk',
    )
  })

  it('uses the criterion that beat the runner-up', () => {
    const r = ranking({ comparisons: [{ other_id: 'B', decided_by: 'severe_miles', reason: '' }] })
    expect(recommendationHeadline(r)).toBe('Fewest miles in Severe weather')
  })

  it('warns when every route has No Travel conditions', () => {
    expect(recommendationHeadline(ranking({ all_no_travel: true }))).toMatch(
      /Every route crosses No Travel/,
    )
  })

  it('handles a single route', () => {
    expect(recommendationHeadline(ranking({ comparisons: [] }))).toBe('The only route available')
  })
})

describe('advisorGain', () => {
  const option = (overrides: Partial<DepartureOption>): DepartureOption => ({
    offset_h: 0,
    departure: '2026-10-22T08:00:00Z',
    route_id: 'A',
    worst_level: 'Low',
    no_travel_miles: 0,
    severe_miles: 0,
    high_miles: 0,
    avg_risk: 0,
    arrival: '2026-10-22T20:00:00Z',
    ...overrides,
  })

  it('lists the risky miles that waiting avoids', () => {
    const planned = option({ severe_miles: 42, high_miles: 10 })
    expect(advisorGain(planned, option({}))).toBe('avoids 42 mi of Severe and 10 mi of High')
  })

  it('falls back to average risk when only that improves', () => {
    const planned = option({ avg_risk: 0.8 })
    expect(advisorGain(planned, option({ avg_risk: 0.45 }))).toBe(
      'lowers the average risk from 0.80 to 0.45',
    )
  })
})
