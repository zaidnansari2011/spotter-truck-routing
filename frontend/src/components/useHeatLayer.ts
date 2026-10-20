import { useCallback, useEffect } from 'react'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { FeatureCollection, Point } from 'geojson'
import type { HeatLayer } from '../api/types.ts'
import { colorExpression, opacityExpression, radiusExpression } from '../lib/heatmap.ts'

const EMPTY: FeatureCollection<Point> = { type: 'FeatureCollection', features: [] }

/**
 * Keeps the map's heat layer in sync with the corridor data and returns `setTime(hours)`.
 * Moving the slider only swaps two paint expressions: no data upload and no React render.
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

  return useCallback(
    (hours: number) => {
      if (!map) return
      map.setPaintProperty('heat', 'circle-color', colorExpression(layer, hours))
      map.setPaintProperty('heat', 'circle-opacity', opacityExpression(layer, hours))
    },
    [map, layer],
  )
}
