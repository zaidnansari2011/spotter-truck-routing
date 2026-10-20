import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import { usePlan } from './api/hooks.ts'
import MapView from './components/MapView.tsx'
import TripForm from './components/TripForm.tsx'
import { tokens } from './theme.ts'

export default function App() {
  const plan = usePlan()

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
          width: { md: 420 },
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

        <TripForm busy={plan.isPending} onSubmit={(request) => plan.mutate(request)} />

        {plan.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {plan.error.message}
          </Alert>
        )}
        {plan.data && (
          <Typography variant="body2" sx={{ mt: 2 }}>
            {plan.data.routes.length} routes found.
          </Typography>
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
        <MapView />
      </Box>
    </Box>
  )
}
