import { describe, expect, it } from 'vitest'
import type { Checkpoint } from '../api/types.ts'
import { checkpointPopupHtml, escapeHtml } from './popup.ts'

const BASE: Checkpoint = {
  index: 3,
  mile: 75.04,
  lat: 41,
  lon: -90,
  eta: '2026-10-22T14:20:00Z',
  covered_miles: 25,
  forecast: true,
  level: 'Severe',
  weather_level: 'High',
  factors: ['wind'],
  load_rule: '35-44 mph wind with a load over 40,000 lb',
  wind_mph: 38.2,
  gust_mph: 51,
  rain_in_hr: 0,
  snow_in_hr: 0.05,
}

describe('checkpointPopupHtml', () => {
  it('shows mile, level, conditions and the load rule', () => {
    const html = checkpointPopupHtml(BASE, 'B')

    expect(html).toContain('Route B, mile 75')
    expect(html).toContain('Severe from wind')
    expect(html).toContain('38.2 mph, gusts 51')
    expect(html).toContain('0.05 in/hr')
    expect(html).toContain(
      'Raised from High by the load rule: 35-44 mph wind with a load over 40,000 lb.',
    )
  })

  it('says when there is no forecast instead of showing zeros', () => {
    const html = checkpointPopupHtml(
      { ...BASE, forecast: false, level: null, load_rule: null },
      'A',
    )

    expect(html).toContain('No forecast for this time')
    expect(html).not.toContain('<dl>')
  })

  it('escapes text', () => {
    expect(escapeHtml('<b>"x" & \'y\'</b>')).toBe(
      '&lt;b&gt;&quot;x&quot; &amp; &#39;y&#39;&lt;/b&gt;',
    )
  })
})
