import { useCallback, useEffect, useRef } from 'react'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { FeatureCollection, Point } from 'geojson'
import type { HeatLayer } from '../api/types.ts'
import { colorExpression, opacityExpression, radiusExpression } from '../lib/heatmap.ts'

const EMPTY: FeatureCollection<Point> = { type: 'FeatureCollection', features: [] }
const STEPS_PER_HOUR = 4

/**
 * Keeps the map's heat layer in sync with the corridor data and returns `setTime(hours)`.
 * Moving the slider only swaps two paint expressions: no network request and no React render.
 */
export function useHeatLayer(
  map: MapLibreMap | null,
  features: FeatureCollection<Point> | undefined,
  spacingDeg: number | undefined,
  layer: HeatLayer,
) {
  useEffect(() => {
    if (!map) return
    ;(map.getSource('heat') as GeoJSONSource).setData(features ?? EMPTY)
    if (spacingDeg) map.setPaintProperty('heat', 'circle-radius', radiusExpression(spacingDeg))
  }, [map, features, spacingDeg])

  // A new data-driven expression makes MapLibre rebuild the layer's tiles, so during playback the
  // shading moves in quarter-hour steps (the slider's own step) instead of on every frame.
  const painted = useRef<string>('')
  return useCallback(
    (hours: number) => {
      if (!map) return
      const step = Math.round(hours * STEPS_PER_HOUR) / STEPS_PER_HOUR
      const key = `${layer}@${step}`
      if (painted.current === key) return
      painted.current = key
      map.setPaintProperty('heat', 'circle-color', colorExpression(layer, step))
      map.setPaintProperty('heat', 'circle-opacity', opacityExpression(layer, step))
    },
    [map, layer],
  )
}
