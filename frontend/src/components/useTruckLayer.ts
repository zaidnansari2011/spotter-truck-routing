import { useCallback, useEffect, useMemo } from 'react'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { Plan } from '../api/types.ts'
import { buildTracks, truckFeatures } from '../lib/trucks.ts'

/** Returns `setTime(ts)`, which moves each route's truck to where it would be at that moment. */
export function useTruckLayer(map: MapLibreMap | null, plan: Plan | undefined) {
  const tracks = useMemo(() => (plan ? buildTracks(plan) : []), [plan])

  useEffect(() => {
    if (map && !plan) {
      ;(map.getSource('trucks') as GeoJSONSource).setData({
        type: 'FeatureCollection',
        features: [],
      })
    }
  }, [map, plan])

  return useCallback(
    (ts: number | undefined) => {
      if (!map || ts === undefined || !tracks.length) return
      ;(map.getSource('trucks') as GeoJSONSource).setData(truckFeatures(tracks, ts))
    },
    [map, tracks],
  )
}
