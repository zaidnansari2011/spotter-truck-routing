import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type GeoJSONSource,
  type MapLayerMouseEvent,
} from 'maplibre-gl'
// MapLibre looks for its worker next to its own module, which does not exist once bundled.
// Importing it with ?url makes Vite emit the file and gives us its final URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import Box from '@mui/material/Box'
import type { Plan } from '../api/types.ts'
import { formatDuration, formatMiles } from '../lib/format.ts'
import {
  checkpointPoints,
  chipAnchors,
  planBounds,
  riskSegments,
  routeLines,
} from '../lib/mapData.ts'
import { colorExpression, opacityExpression, radiusExpression } from '../lib/heatmap.ts'
import { checkpointPopupHtml } from '../lib/popup.ts'
import { worstLevel } from '../lib/risk.ts'
import { fontFamily, tokens } from '../theme.ts'

setWorkerUrl(workerUrl)

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const US_VIEW = { center: [-96, 38.5] as [number, number], zoom: 3.6 }
const EMPTY = { type: 'FeatureCollection' as const, features: [] }

interface Props {
  plan?: Plan
  selectedId?: string
  recommendedId?: string
  onSelectRoute: (id: string) => void
  onMapReady?: (map: MapLibreMap) => void
  children?: ReactNode
}

export default function MapView({
  plan,
  selectedId,
  recommendedId,
  onSelectRoute,
  onMapReady,
  children,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  // Map event handlers are bound once; they read the latest props through this ref.
  const latest = useRef({ plan, selectedId, onSelectRoute })
  const readyCallback = useRef(onMapReady)
  useLayoutEffect(() => {
    latest.current = { plan, selectedId, onSelectRoute }
    readyCallback.current = onMapReady
  })

  useEffect(() => {
    const instance = new MapLibreMap({
      container: containerRef.current!,
      style: STYLE_URL,
      ...US_VIEW,
      attributionControl: {
        compact: true,
        customAttribution: [
          'Routing &copy; TomTom',
          'Weather: <a href="https://open-meteo.com">Open-Meteo</a> (CC BY 4.0)',
        ],
      },
    })
    instance.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    instance.on('load', () => {
      // Compact attribution starts expanded; start collapsed so it does not cover small maps.
      instance
        .getContainer()
        .querySelector('.maplibregl-ctrl-attrib')
        ?.classList.remove('maplibregl-compact-show')
      addRouteLayers(instance)
      bindInteractions(instance, latest)
      setMap(instance)
      readyCallback.current?.(instance)
      // Development only: lets browser checks find features on the map. Removed from builds.
      if (import.meta.env.DEV) Object.assign(window, { __map: instance })
    })
    return () => instance.remove()
  }, [])

  // Route lines, risk-colored selected route, checkpoints.
  useEffect(() => {
    if (!map) return
    const selected = plan?.routes.find((r) => r.id === selectedId)
    source(map, 'routes').setData(plan && selectedId ? routeLines(plan, selectedId) : EMPTY)
    source(map, 'risk').setData(selected ? riskSegments(selected) : EMPTY)
    source(map, 'checkpoints').setData(selected ? checkpointPoints(selected) : EMPTY)
  }, [map, plan, selectedId])

  // Frame all routes when a new plan arrives. On phones the timeline sits under the map,
  // so the map needs no room for it.
  useEffect(() => {
    if (!map || !plan) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const compact = map.getContainer().clientWidth < 600
    map.fitBounds(planBounds(plan), {
      padding: compact
        ? { top: 40, bottom: 40, left: 24, right: 24 }
        : { top: 70, bottom: 150, left: 60, right: 60 },
      duration: reduceMotion ? 0 : 900,
    })
  }, [map, plan])

  // Route chips: route letter and travel time, clickable.
  useEffect(() => {
    if (!map || !plan) return
    const anchors = chipAnchors(plan)
    const markers = plan.routes.map((route) => {
      const chip = document.createElement('button')
      chip.type = 'button'
      chip.className = 'route-chip'
      chip.dataset.selected = String(route.id === selectedId)
      chip.dataset.recommended = String(route.id === recommendedId)
      const worst = worstLevel(route.summary)
      const summary = `${formatDuration(route.duration_s)}, ${formatMiles(route.distance_mi)}`
      chip.setAttribute('aria-label', `Route ${route.id}: ${summary}, worst weather ${worst.label}`)
      chip.title = `Worst weather on this route: ${worst.label}`
      chip.innerHTML =
        `<span class="route-chip-id">${route.id}</span>` +
        `<span class="route-chip-risk" style="background:${worst.color}"></span><span class="route-chip-text">${summary}</span>`
      chip.addEventListener('click', (event) => {
        event.stopPropagation()
        latest.current.onSelectRoute(route.id)
      })
      return new Marker({ element: chip }).setLngLat(anchors[route.id]).addTo(map)
    })
    blockChipSpace(map, markers)
    return () => {
      markers.forEach((m) => m.remove())
      source(map, 'chip-blockers').setData(EMPTY)
    }
  }, [map, plan, selectedId, recommendedId])

  return (
    <Box sx={{ position: 'absolute', inset: 0, ...mapStyles }}>
      <Box ref={containerRef} sx={{ position: 'absolute', inset: 0 }} />
      {children}
    </Box>
  )
}

function source(map: MapLibreMap, id: string): GeoJSONSource {
  return map.getSource(id) as GeoJSONSource
}

/** Reserves each chip's on-screen box in the map's label placement with a transparent icon. */
function blockChipSpace(map: MapLibreMap, markers: Marker[]) {
  const features = markers.map((marker, i) => {
    const chip = marker.getElement()
    const image = `chip-block-${i}`
    const width = Math.ceil(chip.offsetWidth)
    const height = Math.ceil(chip.offsetHeight)
    if (map.hasImage(image)) map.removeImage(image)
    map.addImage(image, { width, height, data: new Uint8Array(width * height * 4) })
    const { lng, lat } = marker.getLngLat()
    return {
      type: 'Feature' as const,
      properties: { image },
      geometry: { type: 'Point' as const, coordinates: [lng, lat] },
    }
  })
  source(map, 'chip-blockers').setData({ type: 'FeatureCollection', features })
}
function addRouteLayers(map: MapLibreMap) {
  for (const id of ['heat', 'routes', 'risk', 'checkpoints', 'chip-blockers', 'trucks']) {
    map.addSource(id, { type: 'geojson', data: EMPTY })
  }

  // The weather overlay sits under the basemap's labels so place names stay readable.
  const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id
  map.addLayer(
    {
      id: 'heat',
      type: 'circle',
      source: 'heat',
      paint: {
        'circle-blur': 1,
        'circle-pitch-alignment': 'map',
        'circle-radius': radiusExpression(0.25),
        'circle-color': colorExpression('risk', 0),
        'circle-opacity': opacityExpression('risk', 0),
      },
    },
    firstLabel,
  )

  map.addLayer({
    id: 'routes-other',
    type: 'line',
    source: 'routes',
    filter: ['==', ['get', 'selected'], false],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': tokens.routeInk, 'line-width': 4, 'line-opacity': 0.55 },
  })
  map.addLayer({
    id: 'routes-selected-casing',
    type: 'line',
    source: 'routes',
    filter: ['==', ['get', 'selected'], true],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': tokens.laneWhite, 'line-width': 11 },
  })
  map.addLayer({
    id: 'risk-line',
    type: 'line',
    source: 'risk',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-width': 6 },
  })
  map.addLayer({
    id: 'checkpoint-dots',
    type: 'circle',
    source: 'checkpoints',
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3.5, 8, 7],
      'circle-stroke-color': tokens.laneWhite,
      'circle-stroke-width': 1.5,
    },
  })
  map.addLayer({
    id: 'checkpoint-eta',
    type: 'symbol',
    source: 'checkpoints',
    // Label collision keeps as many ETAs as fit at each zoom; start and destination go first.
    minzoom: 3.5,
    layout: {
      'text-field': ['get', 'eta'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11,
      'text-offset': [0, -1.3],
      'text-anchor': 'bottom',
      'symbol-sort-key': ['case', ['get', 'endpoint'], 0, 1],
    },
    paint: {
      'text-color': tokens.asphalt,
      'text-halo-color': tokens.laneWhite,
      'text-halo-width': 1.5,
    },
  })

  // Invisible boxes where the route chips sit. Symbols are placed top layer first, so arrival
  // times and place names below give way to the chips instead of hiding under them.
  map.addLayer({
    id: 'chip-blockers',
    type: 'symbol',
    source: 'chip-blockers',
    layout: {
      'icon-image': ['get', 'image'],
      'icon-allow-overlap': true,
      'icon-ignore-placement': false,
      'icon-padding': 4,
    },
  })

  // Trucks follow the timeline slider; drawn last so they sit on top of everything.
  map.addLayer({
    id: 'truck-dots',
    type: 'circle',
    source: 'trucks',
    paint: {
      'circle-radius': 10,
      'circle-color': ['case', ['get', 'recommended'], tokens.signGreen, tokens.asphalt],
      'circle-stroke-color': tokens.centerLine,
      'circle-stroke-width': 2.5,
      'circle-opacity': ['case', ['==', ['get', 'state'], 'driving'], 1, 0.55],
      'circle-stroke-opacity': ['case', ['==', ['get', 'state'], 'driving'], 1, 0.55],
    },
  })
  map.addLayer({
    id: 'truck-labels',
    type: 'symbol',
    source: 'trucks',
    layout: {
      'text-field': ['get', 'id'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11,
      'text-allow-overlap': true,
      'text-ignore-placement': true,
    },
    paint: { 'text-color': tokens.laneWhite },
  })
}

function bindInteractions(
  map: MapLibreMap,
  latest: {
    current: {
      plan?: Plan
      selectedId?: string
      onSelectRoute: (id: string) => void
    }
  },
) {
  for (const layer of ['routes-other', 'checkpoint-dots']) {
    map.on('mouseenter', layer, () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', layer, () => (map.getCanvas().style.cursor = ''))
  }
  map.on('click', 'routes-other', (event: MapLayerMouseEvent) => {
    const id = event.features?.[0]?.properties?.id
    if (id) latest.current.onSelectRoute(id)
  })
  map.on('click', 'checkpoint-dots', (event: MapLayerMouseEvent) => {
    const { plan, selectedId } = latest.current
    const route = plan?.routes.find((r) => r.id === selectedId)
    const index = event.features?.[0]?.properties?.index
    const checkpoint = route?.checkpoints[index]
    if (!route || !checkpoint) return
    new Popup({ closeButton: true, maxWidth: '260px', offset: 10 })
      .setLngLat([checkpoint.lon, checkpoint.lat])
      .setHTML(checkpointPopupHtml(checkpoint, route.id))
      .addTo(map)
  })
}

// Styles for DOM elements MapLibre creates (chips, popups), scoped to the map container.
const mapStyles = {
  '& .route-chip': {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '3px 9px 3px 3px',
    border: `2px solid ${tokens.laneWhite}`,
    borderRadius: '999px',
    background: tokens.asphalt,
    color: tokens.laneWhite,
    font: `700 12px/1 ${fontFamily}`,
    boxShadow: '0 1px 4px rgba(43, 47, 51, 0.35)',
    cursor: 'pointer',
  },
  // On phones the routes sit close together; chips show only the letter and worst risk there.
  '@media (max-width: 599px)': {
    '& .route-chip': { padding: '3px' },
    '& .route-chip-text': { display: 'none' },
  },
  '& .route-chip[data-recommended="true"]': { background: tokens.signGreen },
  '& .route-chip[data-selected="true"]': { outline: `3px solid ${tokens.centerLine}` },
  '& .route-chip-risk': {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    border: `1.5px solid ${tokens.laneWhite}`,
  },
  '& .route-chip-id': {
    display: 'grid',
    placeItems: 'center',
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    background: tokens.laneWhite,
    color: tokens.asphalt,
  },
  '& .maplibregl-popup-content': {
    font: `14px/1.4 ${fontFamily}`,
    color: tokens.asphalt,
    padding: '12px 14px',
    borderRadius: '6px',
  },
  '& .cp-popup p': { margin: 0 },
  '& .cp-title': { fontWeight: 800 },
  '& .cp-eta': { color: tokens.asphaltSoft, marginBottom: '6px !important' },
  '& .cp-level': { display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 },
  '& .cp-swatch': { width: '10px', height: '10px', borderRadius: '50%', flexShrink: 0 },
  '& .cp-popup dl': {
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    gap: '2px 10px',
    margin: '8px 0 0',
    fontVariantNumeric: 'tabular-nums',
  },
  '& .cp-popup dt': { color: tokens.asphaltSoft },
  '& .cp-popup dd': { margin: 0 },
  '& .cp-note': { marginTop: '8px !important', fontSize: '13px', color: tokens.asphaltSoft },
}
