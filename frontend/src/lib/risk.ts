import type { LevelLabel } from '../api/types.ts'

export interface LevelStyle {
  label: LevelLabel
  color: string
  text: string // readable text color on top of `color`
}

// Ordered Low -> No Travel; the index is the level score used by the backend.
export const LEVELS: LevelStyle[] = [
  { label: 'Low', color: '#3C8D5A', text: '#FFFFFF' },
  { label: 'Moderate', color: '#F2B705', text: '#2B2F33' },
  { label: 'High', color: '#E8741E', text: '#2B2F33' },
  { label: 'Severe', color: '#C62828', text: '#FFFFFF' },
  { label: 'No Travel', color: '#6A1B9A', text: '#FFFFFF' },
]

export const NO_FORECAST = { label: 'No forecast', color: '#9AA3A8', text: '#2B2F33' }

export function levelStyle(label: LevelLabel | null | undefined) {
  return LEVELS.find((l) => l.label === label) ?? NO_FORECAST
}

export function levelColor(label: LevelLabel | null | undefined): string {
  return levelStyle(label).color
}

const FACTOR_NAMES: Record<string, string> = { wind: 'wind', rain: 'rain', snow: 'snow' }

/** "High from wind and rain", "Low", or "No forecast for this time". */
export function describeLevel(label: LevelLabel | null, factors: string[] = []): string {
  if (!label) return 'No forecast for this time'
  if (label === 'Low' || factors.length === 0) return label
  const names = factors.map((f) => FACTOR_NAMES[f] ?? f)
  const joined =
    names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names.at(-1)}` : names[0]
  return `${label} from ${joined}`
}
