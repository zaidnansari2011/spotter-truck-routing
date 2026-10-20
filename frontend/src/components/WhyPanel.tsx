import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import type { Ranking } from '../api/types.ts'
import { RANKING_RULES } from '../lib/explain.ts'
import { tokens } from '../theme.ts'

export default function WhyPanel({ ranking }: { ranking: Ranking }) {
  return (
    <Box component="section" aria-labelledby="why-heading">
      <Typography id="why-heading" variant="h2" component="h2" sx={{ mb: 1 }}>
        Why Route {ranking.recommended_id}
      </Typography>
      {ranking.comparisons.length > 0 ? (
        <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
          {ranking.comparisons.map((c) => (
            <Typography component="li" variant="body2" key={c.other_id} sx={{ mb: 0.5 }}>
              {c.reason}
            </Typography>
          ))}
        </Box>
      ) : (
        <Typography variant="body2">It is the only route between these places.</Typography>
      )}

      {ranking.tradeoff && (
        <Typography
          variant="body2"
          sx={{ mt: 1.5, pl: 1.5, borderLeft: `4px solid ${tokens.centerLine}` }}
        >
          {ranking.tradeoff.note}
        </Typography>
      )}

      <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 0.5 }}>
        Routes are compared in this order, each step only breaking ties in the one before:
      </Typography>
      <Box component="ol" sx={{ m: 0, pl: 2.5, color: 'text.secondary' }}>
        {RANKING_RULES.map((rule) => (
          <Typography component="li" variant="body2" key={rule}>
            {rule}
          </Typography>
        ))}
      </Box>
    </Box>
  )
}
