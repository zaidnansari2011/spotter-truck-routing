import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import type { Ranking, RouteOption } from '../api/types.ts'
import { recommendationHeadline } from '../lib/explain.ts'
import { formatClock, formatDuration, formatMiles, timeZoneName } from '../lib/format.ts'
import { tokens } from '../theme.ts'

interface Props {
  route: RouteOption
  ranking: Ranking
  destination: string
}

/**
 * The recommendation styled as an overhead guide sign: green panel, white inset border, white
 * mixed-case lettering. When every route crosses No Travel conditions it becomes a yellow
 * warning sign instead.
 */
export default function RecommendationSign({ route, ranking, destination }: Props) {
  const warning = ranking.all_no_travel
  const ink = warning ? tokens.asphalt : tokens.laneWhite
  return (
    <Box
      component="section"
      aria-label="Recommended route"
      sx={{
        bgcolor: warning ? tokens.centerLine : tokens.signGreen,
        color: ink,
        borderRadius: '10px',
        p: '5px',
      }}
    >
      <Box sx={{ border: `2px solid ${ink}`, borderRadius: '7px', px: 2, py: 1.5 }}>
        <Typography component="p" sx={{ fontSize: '1.625rem', fontWeight: 800, lineHeight: 1.1 }}>
          {warning ? `Least risky: Route ${route.id}` : `Take Route ${route.id}`}
        </Typography>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            gap: 2,
            mt: 1,
          }}
        >
          <Typography component="p" sx={{ fontSize: '1.125rem', fontWeight: 700 }}>
            {destination}
          </Typography>
          <Typography component="p" sx={{ fontSize: '1.125rem', fontWeight: 700, flexShrink: 0 }}>
            {formatMiles(route.distance_mi)}
          </Typography>
        </Box>
        <Typography component="p" sx={{ fontSize: '0.9375rem', mt: 0.25 }}>
          {formatDuration(route.duration_s)}
          {route.rest_s > 0 && ` including ${formatDuration(route.rest_s)} of rest`}, arrives{' '}
          {formatClock(route.arrival)} {timeZoneName(route.arrival)}
        </Typography>
        <Typography
          component="p"
          sx={{ fontSize: '0.875rem', mt: 1, pt: 1, borderTop: `1px solid ${ink}`, opacity: 0.95 }}
        >
          {recommendationHeadline(ranking)}
        </Typography>
      </Box>
    </Box>
  )
}
