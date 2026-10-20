import { describe, expect, it } from 'vitest'
import type { Ranking } from '../api/types.ts'
import { recommendationHeadline } from './explain.ts'

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
      'Fastest, with the same weather risk as the others',
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
