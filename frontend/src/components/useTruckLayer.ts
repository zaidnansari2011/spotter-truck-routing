import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Marker, type Map as MapLibreMap } from 'maplibre-gl'
import type { Plan } from '../api/types.ts'
import { buildTracks, truckAt, type Track } from '../lib/trucks.ts'

/**
 * Returns `setTime(ts)`, which moves each route's truck to where it would be at that moment.
 *
 * Trucks are DOM markers rather than a GeoJSON layer: moving a marker only sets a CSS transform,
 * while `setData` on a source makes the map re-tile it and redo label placement every frame.
 */
export function useTruckLayer(map: MapLibreMap | null, plan: Plan | undefined) {
  const tracks = useMemo(() => (plan ? buildTracks(plan) : []), [plan])
  const markers = useRef<Marker[]>([])
  const lastTs = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!map) return
    markers.current = tracks.map((track) => {
      const element = document.createElement('div')
      element.className = 'truck-marker'
      element.dataset.recommended = String(track.recommended)
      element.textContent = track.id
      element.setAttribute('aria-hidden', 'true')
      return new Marker({ element }).setLngLat(track.line[0]).addTo(map)
    })
    // The timeline may have moved before these markers existed (a new plan at the same time).
    place(tracks, markers.current, lastTs.current ?? -Infinity)
    return () => {
      markers.current.forEach((m) => m.remove())
      markers.current = []
    }
  }, [map, tracks])

  return useCallback(
    (ts: number | undefined) => {
      if (ts === undefined) return
      lastTs.current = ts
      place(tracks, markers.current, ts)
    },
    [tracks],
  )
}

function place(tracks: Track[], markers: Marker[], ts: number) {
  tracks.forEach((track, i) => {
    const marker = markers[i]
    if (!marker) return
    const { coordinates, state } = truckAt(track, ts)
    marker.setLngLat(coordinates)
    // A truck that has arrived leaves the map; the timeline says when it arrived.
    const element = marker.getElement()
    if (element.dataset.state !== state) element.dataset.state = state
  })
}
