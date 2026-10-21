import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import Snackbar from '@mui/material/Snackbar'
import LinkRounded from '@mui/icons-material/LinkRounded'
import ThunderstormRounded from '@mui/icons-material/ThunderstormRounded'
import Skeleton from '@mui/material/Skeleton'
import Stack from '@mui/material/Stack'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import { INTERVALS, type IntervalKey, type Plan } from '../api/types.ts'
import CheckpointTable from './CheckpointTable.tsx'
import DepartureWindow from './DepartureWindow.tsx'
import RecommendationSign from './RecommendationSign.tsx'
import RouteList from './RouteList.tsx'
import WhyPanel from './WhyPanel.tsx'

interface Props {
  plan: Plan
  destination: string
  interval: IntervalKey
  onIntervalChange: (interval: IntervalKey) => void
  selectedId?: string
  onSelect: (id: string) => void
  busy: boolean
  updating: boolean // a different interval is loading; the shown results are the previous ones
  onReplan: (departure: string) => void
  demoStorm: boolean // the simulated storm is on, so it is not offered again
}

export default function Results({
  plan,
  destination,
  interval,
  onIntervalChange,
  selectedId,
  onSelect,
  busy,
  updating,
  onReplan,
  demoStorm,
}: Props) {
  const ranking = plan.ranking
  const recommended = plan.routes.find((r) => r.id === ranking.recommended_id)!
  const selected = plan.routes.find((r) => r.id === selectedId) ?? recommended
  const [copied, setCopied] = useState(false)

  async function copyLink() {
    await navigator.clipboard.writeText(window.location.href)
    setCopied(true)
  }

  // The same trip with the simulated storm on; the shared link plans it straight away.
  const stormParams = new URLSearchParams(window.location.search)
  stormParams.set('demo', 'storm')

  return (
    <Stack
      spacing={3}
      aria-busy={updating}
      sx={{ mt: 3, opacity: updating ? 0.55 : 1, transition: 'opacity 150ms' }}
    >
      <RecommendationSign route={recommended} ranking={ranking} destination={destination} />
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mt: '8px !important' }}>
        <Button size="small" startIcon={<LinkRounded />} onClick={copyLink}>
          Copy link to this trip
        </Button>
        {!demoStorm && (
          <Button
            size="small"
            startIcon={<ThunderstormRounded />}
            href={`?${stormParams.toString()}`}
          >
            Try it in a simulated storm
          </Button>
        )}
      </Stack>
      <Snackbar
        open={copied}
        autoHideDuration={2500}
        onClose={() => setCopied(false)}
        message="Link copied"
      />

      {plan.notices.map((notice) => (
        <Alert severity="info" key={notice}>
          {notice}
        </Alert>
      ))}

      <section aria-labelledby="routes-heading">
        <Stack
          direction="row"
          sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1, gap: 1 }}
        >
          <Typography id="routes-heading" variant="h2" component="h2">
            Route options
          </Typography>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={interval}
            onChange={(_, value: IntervalKey | null) => value && onIntervalChange(value)}
            aria-label="Weather checkpoint spacing"
          >
            {INTERVALS.map((value) => (
              <ToggleButton key={value} value={value} sx={{ px: 1.25, py: 0.25 }}>
                {value} mi
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Weather is checked every {interval} miles. Select a route to see it on the map.
        </Typography>
        <RouteList plan={plan} selectedId={selected.id} onSelect={onSelect} />
      </section>

      <WhyPanel ranking={ranking} />
      <DepartureWindow advice={plan.departure_options} busy={busy} onReplan={onReplan} />
      <CheckpointTable route={selected} interval={plan.interval_mi} />
    </Stack>
  )
}

export function ResultsSkeleton() {
  return (
    <Stack spacing={1.5} sx={{ mt: 3 }} aria-label="Loading routes">
      <Skeleton variant="rounded" height={150} />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} variant="rounded" height={64} />
      ))}
    </Stack>
  )
}
