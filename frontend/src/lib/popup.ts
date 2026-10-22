import type { Checkpoint } from '../api/types.ts'
import { formatClock, formatPrecip, formatWind, timeZoneName } from './format.ts'
import { describeLevel, levelColor } from './risk.ts'

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ESCAPES[c])
}

/** Popup body for a checkpoint marker. Values come from our API but are escaped anyway. */
export function checkpointPopupHtml(cp: Checkpoint, routeId: string): string {
  const title = `Route ${routeId}, mile ${Math.round(cp.mile).toLocaleString('en-US')}`
  const eta = `Arrives ${formatClock(cp.eta)} ${timeZoneName(cp.eta)}`
  const level = describeLevel(cp.level, cp.factors)
  const rows = cp.forecast
    ? [
        [
          'Wind',
          `${formatWind(cp.wind_mph!)} mph${cp.gust_mph != null ? `, gusts ${formatWind(cp.gust_mph)}` : ''}`,
        ],
        ['Rain', `${formatPrecip(cp.rain_in_hr!)} in/hr`],
        ['Snow', `${formatPrecip(cp.snow_in_hr!)} in/hr`],
      ]
    : []
  const loadRule = cp.load_rule
    ? `<p class="cp-note">Raised from ${escapeHtml(cp.weather_level ?? '')} by the load rule: ${escapeHtml(cp.load_rule)}.</p>`
    : ''
  return [
    `<div class="cp-popup">`,
    `<p class="cp-title">${escapeHtml(title)}</p>`,
    `<p class="cp-eta">${escapeHtml(eta)}</p>`,
    `<p class="cp-level"><span class="cp-swatch" style="background:${levelColor(cp.level)}"></span>${escapeHtml(level)}</p>`,
    rows.length
      ? `<dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`).join('')}</dl>`
      : '',
    loadRule,
    `</div>`,
  ].join('')
}
