import Alert from '@mui/material/Alert'

/** Shown on every view while the simulated storm is on, so its weather is never taken as real. */
export default function DemoBanner({ compact = false }: { compact?: boolean }) {
  return (
    <Alert
      severity="warning"
      variant={compact ? 'filled' : 'standard'}
      sx={{ mb: compact ? 0 : 2.5 }}
    >
      {compact
        ? 'Simulated storm: this weather is not real.'
        : 'Simulated storm. The weather on this page is made up to show how the app responds to a storm. Open the page without ?demo=storm to see real forecasts.'}
    </Alert>
  )
}
