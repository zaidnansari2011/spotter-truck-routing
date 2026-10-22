import { describe, expect, it } from 'vitest'
import type { PlanRequest } from '../api/types.ts'
import { decodeTrip, encodeTrip } from './shareUrl.ts'

const NOW = Date.parse('2026-10-22T10:00:00Z')
const REQUEST: PlanRequest = {
  origin: { label: 'Chicago, IL', lat: 41.883229, lon: -87.632398 },
  destination: { label: 'Denver, CO', lat: 39.738453, lon: -104.984853 },
  departure: '2026-10-22T20:00:00+05:30', // 14:30 UTC, after NOW
  load_lb: 38000,
  hos: true,
}

describe('share links', () => {
  it('round-trips a trip, including labels with commas', () => {
    const search = encodeTrip(REQUEST, '10', new URLSearchParams())

    const decoded = decodeTrip(search, 'unused', NOW)

    expect(decoded?.interval).toBe('10')
    expect(decoded?.request).toEqual(REQUEST) // coordinates keep all 6 decimals
  })

  it('keeps demo mode in the link', () => {
    expect(encodeTrip(REQUEST, '25', new URLSearchParams('demo=storm'))).toMatch(/^demo=storm&/)
  })

  it('keeps a re-planned demo trip on the same storm', () => {
    const simulation = { center: [-87.1, 41.2] as [number, number], start: '2026-10-22T16:00:00Z' }
    const search = encodeTrip({ ...REQUEST, simulation }, '25', new URLSearchParams('demo=storm'))

    expect(decodeTrip(search, 'unused', NOW)?.request.simulation).toEqual(simulation)
  })

  it.each(['abc,41,2026-10-22T16:00:00Z', '-87,95,2026-10-22T16:00:00Z', '-87,41,later', '-87'])(
    'drops a malformed storm and keeps the trip: %s',
    (storm) => {
      const search = `${encodeTrip(REQUEST, '25', new URLSearchParams())}&storm=${storm}`

      const decoded = decodeTrip(search, 'unused', NOW)

      expect(decoded?.request).toEqual(REQUEST)
    },
  )

  it('moves a departure that has passed to the fallback time', () => {
    const search = encodeTrip(
      { ...REQUEST, departure: '2026-10-20T08:00:00Z' },
      '25',
      new URLSearchParams(),
    )

    expect(decodeTrip(search, '2026-10-22T10:15:00Z', NOW)?.request.departure).toBe(
      '2026-10-22T10:15:00Z',
    )
  })

  it.each([
    [''],
    ['from=41,-87,Chicago'],
    ['from=abc,-87,Chicago&to=39.7,-104.9,Denver&depart=2026-10-22T14:00:00Z&load=1000'],
    ['from=41,-87,Chicago&to=39.7,-104.9,&depart=2026-10-22T14:00:00Z&load=1000'],
    ['from=41,-87,Chicago&to=39.7,-104.9,Denver&depart=tomorrow&load=1000'],
  ])('ignores a missing or malformed trip: %s', (search) => {
    expect(decodeTrip(search, 'x', NOW)).toBeNull()
  })

  it('falls back to 25 miles for an unknown spacing', () => {
    const search = encodeTrip(REQUEST, '25', new URLSearchParams()).replace('mi=25', 'mi=15')

    expect(decodeTrip(search, 'x', NOW)?.interval).toBe('25')
  })
})
