import { useCallback, useMemo, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import LinearProgress from '@mui/material/LinearProgress'
import Typography from '@mui/material/Typography'
import { useCorridor, usePlan } from './api/hooks.ts'
import type { HeatLayer, IntervalKey, PlanRequest } from './api/types.ts'
import DemoBanner from './components/DemoBanner.tsx'
import Legend from './components/Legend.tsx'
import MapView from './components/MapView.tsx'
import Results, { ResultsSkeleton } from './components/Results.tsx'
import TimelineBar, { type Anchor } from './components/TimelineBar.tsx'
import TripForm from './components/TripForm.tsx'
import { useHeatLayer } from './components/useHeatLayer.ts'
import { useTruckLayer } from './components/useTruckLayer.ts'
import { corridorFeatures } from './lib/heatmap.ts'
import { tokens } from './theme.ts'

// Demo mode lays a simulated storm over the real forecast; every page using it says so.
const DEMO_STORM = new URLSearchParams(window.location.search).get('demo') === 'storm'

export default function App() {
  const [request, setRequest] = useState<PlanRequest>()
  const [interval, setSamplingInterval] = useState<IntervalKey>('25')
  const plan = usePlan(request, interval)
  const [chosenId, setChosenId] = useState<string>()
  const [formVersion, setFormVersion] = useState(0)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [anchor, setAnchor] = useState<Anchor>('departure')
  const [nowStart, setNowStart] = useState<string>()
  const [heatLayer, setHeatLayer] = useState<HeatLayer>('risk')

  const data = plan.data
  // The driver's pick if it exists in these results, otherwise the recommended route.
  const selectedId = data?.routes.some((r) => r.id === chosenId)
    ? chosenId
    : data?.ranking.recommended_id
  const updating = plan.isFetching && plan.isPlaceholderData

  const timelineStart = anchor === 'departure' ? data?.departure : nowStart
  const corridor = useCorridor(data, timelineStart)
  const heatFeatures = useMemo(
    () =>
      data && corridor.data
        ? corridorFeatures(data.corridor.points, corridor.data, heatLayer)
        : undefined,
    [data, corridor.data, heatLayer],
  )
  const setHeatTime = useHeatLayer(map, heatFeatures, data?.corridor.spacing_deg, heatLayer)
  const setTruckTime = useTruckLayer(map, data)
  const setTimelineTime = useCallback(
    (frameIndex: number, momentTs: number | undefined) => {
      setHeatTime(frameIndex)
      setTruckTime(momentTs)
    },
    [setHeatTime, setTruckTime],
  )

  function findRoutes(next: PlanRequest) {
    setRequest(DEMO_STORM ? { ...next, demo: 'storm' } : next)
    setChosenId(undefined) // a new trip starts on its recommended route
  }

  function replanAt(departure: string) {
    if (!request) return
    setFormVersion((v) => v + 1) // remount the form so it shows the new departure
    findRoutes({ ...request, departure })
  }

  function changeAnchor(next: Anchor) {
    if (next === 'now') setNowStart(new Date().toISOString())
    setAnchor(next)
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        height: { md: '100vh' },
        minHeight: '100vh',
      }}
    >
      <Box
        component="aside"
        sx={{
          order: { xs: 2, md: 1 },
          width: { md: 440 },
          flexShrink: 0,
          overflowY: { md: 'auto' },
          borderRight: { md: `1px solid ${tokens.rule}` },
          bgcolor: 'background.paper',
          px: 2.5,
          py: 3,
        }}
      >
        <Typography variant="h1" component="h1">
          Weather-Aware Truck Routing
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 3 }}>
          Compare three truck routes by forecast weather at your arrival time, load weight and
          travel time.
        </Typography>

        {DEMO_STORM && <DemoBanner />}

        <TripForm
          key={formVersion}
          initial={request}
          busy={plan.isFetching}
          onSubmit={findRoutes}
        />

        {plan.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {plan.error.message}
          </Alert>
        )}
        {plan.isFetching && !data && <ResultsSkeleton />}
        {data && request && (
          <Results
            plan={data}
            destination={request.destination.label}
            interval={interval}
            onIntervalChange={setSamplingInterval}
            selectedId={selectedId}
            onSelect={setChosenId}
            busy={plan.isFetching}
            updating={updating}
            onReplan={replanAt}
          />
        )}
      </Box>

      <Box
        component="main"
        sx={{
          order: { xs: 1, md: 2 },
          flex: 1,
          position: 'relative',
          height: { xs: '62vh', md: 'auto' },
          minHeight: 360,
        }}
      >
        <MapView
          plan={data}
          selectedId={selectedId}
          recommendedId={data?.ranking.recommended_id}
          onSelectRoute={setChosenId}
          onMapReady={setMap}
        >
          {plan.isFetching && (
            <LinearProgress
              aria-label="Finding routes"
              sx={{ position: 'absolute', top: 0, left: 0, right: 0 }}
            />
          )}
          <Legend />
          {DEMO_STORM && (
            <Box
              sx={{
                position: 'absolute',
                top: 12,
                left: '50%',
                transform: 'translateX(-50%)',
                maxWidth: 420,
              }}
            >
              <DemoBanner compact />
            </Box>
          )}
          <TimelineBar
            hours={corridor.data?.hours}
            startTs={timelineStart ? Date.parse(timelineStart) / 1000 : undefined}
            loading={corridor.isFetching}
            error={corridor.isError ? corridor.error.message : undefined}
            anchor={anchor}
            onAnchorChange={changeAnchor}
            layer={heatLayer}
            onLayerChange={setHeatLayer}
            onTimeChange={setTimelineTime}
          />
        </MapView>
      </Box>
    </Box>
  )
}
