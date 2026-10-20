import { useMemo, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import LinearProgress from '@mui/material/LinearProgress'
import Typography from '@mui/material/Typography'
import { useCorridor, usePlan } from './api/hooks.ts'
import type { HeatLayer, IntervalKey, PlanRequest } from './api/types.ts'
import Legend from './components/Legend.tsx'
import MapView from './components/MapView.tsx'
import Results, { ResultsSkeleton } from './components/Results.tsx'
import TimelineBar, { type Anchor } from './components/TimelineBar.tsx'
import TripForm from './components/TripForm.tsx'
import { useHeatLayer } from './components/useHeatLayer.ts'
import { corridorFeatures } from './lib/heatmap.ts'
import { tokens } from './theme.ts'

export default function App() {
  const plan = usePlan()
  const [request, setRequest] = useState<PlanRequest>()
  const [interval, setSamplingInterval] = useState<IntervalKey>('25')
  const [selectedId, setSelectedId] = useState<string>()
  const [formVersion, setFormVersion] = useState(0)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [anchor, setAnchor] = useState<Anchor>('departure')
  const [nowStart, setNowStart] = useState<string>()
  const [heatLayer, setHeatLayer] = useState<HeatLayer>('risk')

  const timelineStart = anchor === 'departure' ? plan.data?.departure : nowStart
  const corridor = useCorridor(plan.data, timelineStart)
  const heatFeatures = useMemo(
    () =>
      plan.data && corridor.data
        ? corridorFeatures(plan.data.corridor.points, corridor.data, heatLayer)
        : undefined,
    [plan.data, corridor.data, heatLayer],
  )
  const setHeatTime = useHeatLayer(map, heatFeatures, plan.data?.corridor.spacing_deg, heatLayer)

  function replanAt(departure: string) {
    if (!request) return
    setFormVersion((v) => v + 1) // remount the form so it shows the new departure
    findRoutes({ ...request, departure })
  }

  function changeAnchor(next: Anchor) {
    if (next === 'now') setNowStart(new Date().toISOString())
    setAnchor(next)
  }

  function findRoutes(next: PlanRequest) {
    setRequest(next)
    plan.mutate(next, {
      onSuccess: (result) => setSelectedId(result.rankings[interval].recommended_id),
    })
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

        <TripForm key={formVersion} initial={request} busy={plan.isPending} onSubmit={findRoutes} />

        {plan.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {plan.error.message}
          </Alert>
        )}
        {plan.isPending && <ResultsSkeleton />}
        {plan.data && request && (
          <Results
            plan={plan.data}
            destination={request.destination.label}
            interval={interval}
            onIntervalChange={setSamplingInterval}
            selectedId={selectedId}
            onSelect={setSelectedId}
            busy={plan.isPending}
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
          plan={plan.data}
          interval={interval}
          selectedId={selectedId}
          recommendedId={plan.data?.rankings[interval].recommended_id}
          onSelectRoute={setSelectedId}
          onMapReady={setMap}
        >
          {plan.isPending && (
            <LinearProgress
              aria-label="Finding routes"
              sx={{ position: 'absolute', top: 0, left: 0, right: 0 }}
            />
          )}
          <Legend />
          <TimelineBar
            hours={corridor.data?.hours}
            startTs={timelineStart ? Date.parse(timelineStart) / 1000 : undefined}
            loading={corridor.isFetching}
            error={corridor.isError ? corridor.error.message : undefined}
            anchor={anchor}
            onAnchorChange={changeAnchor}
            layer={heatLayer}
            onLayerChange={setHeatLayer}
            onTimeChange={setHeatTime}
          />
        </MapView>
      </Box>
    </Box>
  )
}
