import { useEffect, useRef } from 'react'
import { Map as MapLibreMap, NavigationControl } from 'maplibre-gl'
import Box from '@mui/material/Box'

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const US_CENTER: [number, number] = [-96, 38.5]

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const map = new MapLibreMap({
      container: containerRef.current,
      style: STYLE_URL,
      center: US_CENTER,
      zoom: 3.6,
      attributionControl: { compact: true },
    })
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    return () => map.remove()
  }, [])

  return <Box ref={containerRef} sx={{ position: 'absolute', inset: 0 }} />
}
