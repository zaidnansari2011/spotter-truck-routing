import { describe, expect, it } from 'vitest'
import { formatAvgRisk, formatDuration, formatMiles } from './format.ts'
import { describeLevel, levelColor, LEVELS, NO_FORECAST } from './risk.ts'

describe('formatDuration', () => {
  it.each([
    [0, '0 min'],
    [45 * 60, '45 min'],
    [2 * 3600, '2 h'],
    [3600 + 15 * 60, '1 h 15 min'],
    [3599.7, '1 h'],
  ])('%s seconds -> %s', (seconds, text) => {
    expect(formatDuration(seconds)).toBe(text)
  })

  it('matches the backend wording used in ranking reasons', () => {
    expect(formatDuration(14 * 3600 + 48 * 60)).toBe('14 h 48 min')
  })
})

describe('formatMiles', () => {
  it('drops decimals on long distances and keeps one on short ones', () => {
    expect(formatMiles(1006.7)).toBe('1,007 mi')
    expect(formatMiles(32.44)).toBe('32.4 mi')
  })
})

describe('formatAvgRisk', () => {
  it('shows two decimals, the precision the ranking compares', () => {
    expect(formatAvgRisk(0.0625)).toBe('0.06')
    expect(formatAvgRisk(null)).toBe('n/a')
  })
})

describe('risk styles', () => {
  it('orders levels from Low to No Travel', () => {
    expect(LEVELS.map((l) => l.label)).toEqual(['Low', 'Moderate', 'High', 'Severe', 'No Travel'])
  })

  it('uses a neutral color when there is no forecast', () => {
    expect(levelColor(null)).toBe(NO_FORECAST.color)
  })

  it.each([
    ['High', ['wind', 'rain'], 'High from wind and rain'],
    ['Severe', ['snow'], 'Severe from snow'],
    ['Moderate', ['wind', 'rain', 'snow'], 'Moderate from wind, rain and snow'],
    ['Low', [], 'Low'],
    [null, [], 'No forecast for this time'],
  ] as const)('describes %s with %j', (label, factors, text) => {
    expect(describeLevel(label, [...factors])).toBe(text)
  })
})
