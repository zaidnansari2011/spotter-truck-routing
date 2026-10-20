import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import LinearProgress from '@mui/material/LinearProgress'
import Typography from '@mui/material/Typography'
import { usePlan } from './api/hooks.ts'
import type { IntervalKey, PlanRequest } from './api/types.ts'
import Legend from './components/Legend.tsx'
import MapView from './components/MapView.tsx'
import Results, { ResultsSkeleton } from './components/Results.tsx'
import TripForm from './components/TripForm.tsx'
import { tokens } from './theme.ts'

export default function App() {
  const plan = usePlan()
  const [request, setRequest] = useState<PlanRequest>()
  const [interval, setInterval] = useState<IntervalKey>('25')
  const [selectedId, setSelectedId] = useState<string>()

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

        <TripForm busy={plan.isPending} onSubmit={findRoutes} />

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
            onIntervalChange={setInterval}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        )}
      </Box>

      <Box
        component="main"
        sx={{
          order: { xs: 1, md: 2 },
          flex: 1,
          position: 'relative',
          height: { xs: '48vh', md: 'auto' },
          minHeight: 280,
        }}
      >
        <MapView
          plan={plan.data}
          interval={interval}
          selectedId={selectedId}
          recommendedId={plan.data?.rankings[interval].recommended_id}
          onSelectRoute={setSelectedId}
        >
          {plan.isPending && (
            <LinearProgress
              aria-label="Finding routes"
              sx={{ position: 'absolute', top: 0, left: 0, right: 0 }}
            />
          )}
          <Legend />
        </MapView>
      </Box>
    </Box>
  )
}
