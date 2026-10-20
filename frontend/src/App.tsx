import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './api/client.ts'
import MapView from './components/MapView.tsx'

export default function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<{ status: string }>('/health/'),
  })

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Paper square elevation={2} sx={{ width: 380, p: 2, zIndex: 1, overflowY: 'auto' }}>
        <Typography variant="h6" component="h1">
          Weather-Aware Truck Routing
        </Typography>
        <Chip
          size="small"
          sx={{ mt: 1 }}
          color={health.isSuccess ? 'success' : health.isError ? 'error' : 'default'}
          label={
            health.isSuccess ? 'API connected' : health.isError ? 'API unreachable' : 'Connecting'
          }
        />
      </Paper>
      <Box sx={{ flex: 1, position: 'relative' }}>
        <MapView />
      </Box>
    </Box>
  )
}
