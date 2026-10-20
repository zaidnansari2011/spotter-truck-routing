import type { ExpressionSpecification } from 'maplibre-gl'
import type { FeatureCollection, Point } from 'geojson'
import type { CorridorFrames, HeatLayer } from '../api/types.ts'
import { LEVELS } from './risk.ts'

export const HEAT_LAYERS: { id: HeatLayer; label: string; unit: string }[] = [
  { id: 'risk', label: 'Weather risk', unit: '' },
  { id: 'risk_load', label: 'Risk for this load', unit: '' },
  { id: 'wind', label: 'Wind', unit: 'mph' },
  { id: 'rain', label: 'Rain', unit: 'in/hr' },
  { id: 'snow', label: 'Snow', unit: 'in/hr' },
]

/**
 * Where each layer's values cross into Moderate, High, Severe and No Travel, in the units the
 * API sends: risk x100, wind mph, rain and snow in hundredths of an inch per hour.
 * Rain and snow No Travel is "more than" 1.00 and 3.0 in/hr, hence 101 and 301.
 */
export const THRESHOLDS: Record<HeatLayer, [number, number, number, number]> = {
  risk: [100, 200, 300, 400],
  risk_load: [100, 200, 300, 400],
  wind: [25, 35, 45, 55],
  rain: [10, 25, 50, 101],
  snow: [50, 100, 200, 301],
}

export const FRAME_COUNT = 49
const RADIUS_FACTOR = 1.8

/** One point per grid cell with its 49 hourly values as v0..v48 (missing hours become 0). */
export function corridorFeatures(
  points: [number, number][],
  frames: CorridorFrames,
  layer: HeatLayer,
): FeatureCollection<Point> {
  const rows = frames[layer]
  return {
    type: 'FeatureCollection',
    features: points.map((coordinates, i) => ({
      type: 'Feature',
      properties: Object.fromEntries(rows[i].map((v, hour) => [`v${hour}`, v ?? 0])),
      geometry: { type: 'Point', coordinates },
    })),
  }
}

/** Value at fractional hour t, blended between the two neighbouring hourly frames on the GPU. */
export function valueAt(t: number): ExpressionSpecification {
  const clamped = Math.min(Math.max(t, 0), FRAME_COUNT - 1)
  const hour = Math.floor(clamped)
  const fraction = clamped - hour
  if (fraction === 0 || hour === FRAME_COUNT - 1) return ['get', `v${hour}`]
  return ['+', ['*', ['get', `v${hour}`], 1 - fraction], ['*', ['get', `v${hour + 1}`], fraction]]
}

/**
 * Each band holds its level's color and blends toward the next only over the last 10% before a
 * threshold, so colors match the legend everywhere except right at band edges, and the overlay
 * still animates smoothly. Below Moderate the layer fades out so calm weather stays clear.
 */
export function colorExpression(layer: HeatLayer, t: number): ExpressionSpecification {
  const edges = THRESHOLDS[layer]
  const stops: (number | string)[] = []
  edges.forEach((edge, i) => {
    if (i > 0) stops.push(edge - (edge - edges[i - 1]) * 0.1, LEVELS[i].color)
    stops.push(edge, LEVELS[i + 1].color)
  })
  return ['interpolate', ['linear'], valueAt(t), ...stops] as ExpressionSpecification
}

export function opacityExpression(layer: HeatLayer, t: number): ExpressionSpecification {
  const [moderate, , , noTravel] = THRESHOLDS[layer]
  return ['interpolate', ['linear'], valueAt(t), moderate * 0.6, 0, moderate, 0.42, noTravel, 0.62]
}

/** Disc radius in pixels at each zoom: wide enough that neighbouring grid points blend smoothly. */
export function radiusExpression(spacingDeg: number): ExpressionSpecification {
  // MapLibre's world is 512 px wide at zoom 0. With full blur a disc is only solid near its
  // centre, so 1.8x the spacing is needed for neighbours to merge without visible blocks.
  const atZoom0 = (spacingDeg / 360) * 512 * RADIUS_FACTOR
  return ['interpolate', ['exponential', 2], ['zoom'], 0, atZoom0, 12, atZoom0 * 2 ** 12]
}
