export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours && minutes) return `${hours} h ${minutes} min`
  return hours ? `${hours} h` : `${minutes} min`
}

export function formatMiles(miles: number): string {
  const digits = miles >= 100 ? 0 : 1
  return `${miles.toLocaleString('en-US', { maximumFractionDigits: digits })} mi`
}

const clock = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
})
const zone = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' })

/** "Thu 06:12" in the viewer's time zone. */
export function formatClock(time: string | number | Date): string {
  return clock.format(toDate(time))
}

/** Short name of the viewer's time zone at that moment, e.g. "CDT" or "GMT+5:30". */
export function timeZoneName(time: string | number | Date = Date.now()): string {
  return zone.formatToParts(toDate(time)).find((p) => p.type === 'timeZoneName')?.value ?? ''
}

/**
 * Weather values at the precision they are classified at (wind 1 decimal, rain and snow up to 3),
 * so a value never looks like it sits in a different band: 0.248 in/hr is Moderate, not "0.25".
 */
export function formatWind(mph: number): string {
  return mph.toFixed(1)
}

export function formatPrecip(inches: number): string {
  return inches.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
}

export function formatAvgRisk(avg: number | null): string {
  return avg === null ? 'n/a' : avg.toFixed(2)
}

function toDate(time: string | number | Date): Date {
  if (time instanceof Date) return time
  return typeof time === 'number' ? new Date(time * 1000) : new Date(time)
}
