import Box from '@mui/material/Box'
import ButtonBase from '@mui/material/ButtonBase'
import Typography from '@mui/material/Typography'
import type { Plan } from '../api/types.ts'
import { formatAvgRisk, formatClock, formatDuration, formatMiles } from '../lib/format.ts'
import { LEVELS } from '../lib/risk.ts'
import { tokens } from '../theme.ts'
import RiskStrip from './RiskStrip.tsx'

interface Props {
  plan: Plan
  selectedId?: string
  onSelect: (id: string) => void
}

export default function RouteList({ plan, selectedId, onSelect }: Props) {
  const ranking = plan.ranking
  const routes = ranking.order.map((id) => plan.routes.find((r) => r.id === id)!)

  return (
    <Box
      component="ol"
      aria-label="Route options, best first"
      sx={{ listStyle: 'none', m: 0, p: 0 }}
    >
      {routes.map((route) => {
        const { checkpoints, summary } = route
        const selected = route.id === selectedId
        const recommended = route.id === ranking.recommended_id
        const miles = summary.miles_by_level
        const notable = LEVELS.slice(2)
          .reverse()
          .filter((level) => miles[level.label] > 0)
          .map((level) => `${level.label} ${formatMiles(miles[level.label])}`)
        return (
          <li key={route.id}>
            <ButtonBase
              onClick={() => onSelect(route.id)}
              aria-pressed={selected}
              sx={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                px: 1.5,
                py: 1.25,
                borderLeft: `4px solid ${selected ? tokens.centerLine : 'transparent'}`,
                borderBottom: `1px solid ${tokens.rule}`,
                bgcolor: selected ? 'rgba(242, 183, 5, 0.08)' : 'transparent',
                '&:hover': {
                  bgcolor: selected ? 'rgba(242, 183, 5, 0.12)' : 'rgba(43, 47, 51, 0.04)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                <Box
                  sx={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    display: 'grid',
                    placeItems: 'center',
                    fontWeight: 800,
                    color: tokens.laneWhite,
                    bgcolor: recommended ? tokens.signGreen : tokens.asphalt,
                    flexShrink: 0,
                  }}
                >
                  {route.id}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 700 }}>
                    {formatDuration(route.duration_s)}{' '}
                    <Typography component="span" variant="body2" color="text.secondary">
                      {formatMiles(route.distance_mi)}, arrives {formatClock(route.arrival)}
                    </Typography>
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {notable.length ? notable.join(', ') : 'No High, Severe or No Travel miles'}.
                    Average risk {formatAvgRisk(summary.avg_risk)}
                    {summary.unknown_miles > 0 &&
                      `. No forecast for ${formatMiles(summary.unknown_miles)}`}
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ mt: 1, ml: '40px' }}>
                <RiskStrip checkpoints={checkpoints} totalMiles={route.distance_mi} />
              </Box>
              {(recommended || summary.do_not_travel || route.source === 'via-waypoint') && (
                <Box sx={{ display: 'flex', gap: 1.5, mt: 0.75, ml: '40px', flexWrap: 'wrap' }}>
                  {recommended && (
                    <Typography variant="body2" sx={{ color: tokens.signGreen, fontWeight: 700 }}>
                      Recommended
                    </Typography>
                  )}
                  {summary.do_not_travel && (
                    <Typography variant="body2" sx={{ color: LEVELS[4].color, fontWeight: 700 }}>
                      Do not travel: crosses No Travel conditions
                    </Typography>
                  )}
                  {route.source === 'via-waypoint' && (
                    <Typography variant="body2" color="text.secondary">
                      Generated through a waypoint
                    </Typography>
                  )}
                </Box>
              )}
            </ButtonBase>
          </li>
        )
      })}
    </Box>
  )
}
