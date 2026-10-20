import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Typography from '@mui/material/Typography'
import type { DepartureAdvice } from '../api/types.ts'
import { advisorGain } from '../lib/explain.ts'
import { formatClock, formatMiles, timeZoneName } from '../lib/format.ts'
import { levelStyle } from '../lib/risk.ts'
import { tokens } from '../theme.ts'

interface Props {
  advice: DepartureAdvice
  busy: boolean
  onReplan: (departure: string) => void
}

const TICKS = [0, 6, 12, 18, 24]

/** Risk of the best route for every departure hour from now to 24 hours later. */
export default function DepartureWindow({ advice, busy, onReplan }: Props) {
  const planned = advice.options[0]
  const suggestion = advice.suggestion

  return (
    <Box component="section" aria-labelledby="departure-heading">
      <Typography id="departure-heading" variant="h2" component="h2">
        Best time to leave
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Worst weather on the best route if you leave later, using the same routes and driving times.
        Select an hour to plan that departure.
      </Typography>

      {suggestion ? (
        <Box sx={{ pl: 1.5, borderLeft: `4px solid ${tokens.signGreen}`, mb: 1.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 700 }}>
            Leaving at {formatClock(suggestion.departure)} ({suggestion.offset_h} h later){' '}
            {advisorGain(planned, suggestion)}.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Route {suggestion.route_id}, arriving {formatClock(suggestion.arrival)}{' '}
            {timeZoneName(suggestion.arrival)}.
          </Typography>
          <Button
            size="small"
            variant="outlined"
            disabled={busy}
            onClick={() => onReplan(suggestion.departure)}
            sx={{ mt: 1 }}
          >
            Plan for {formatClock(suggestion.departure)}
          </Button>
        </Box>
      ) : (
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          Your planned departure is already the safest in the next 24 hours.
        </Typography>
      )}

      <Box role="group" aria-label="Departure hours" sx={{ display: 'flex', gap: '2px' }}>
        {advice.options.map((option) => {
          const style = levelStyle(option.worst_level)
          const isSuggestion = suggestion?.offset_h === option.offset_h
          const label =
            `Leave ${formatClock(option.departure)}: Route ${option.route_id}, worst ${style.label}` +
            (option.severe_miles ? `, ${formatMiles(option.severe_miles)} Severe` : '')
          return (
            <ButtonBase
              key={option.offset_h}
              title={label}
              aria-label={label}
              disabled={busy || option.offset_h === 0}
              onClick={() => onReplan(option.departure)}
              sx={{
                flex: 1,
                height: 22,
                borderRadius: '3px',
                bgcolor: style.color,
                outline: option.offset_h === 0 ? `2px solid ${tokens.asphalt}` : 'none',
                outlineOffset: 1,
                boxShadow: isSuggestion ? `0 0 0 3px ${tokens.centerLine}` : 'none',
                '&:hover': { filter: 'brightness(1.1)' },
              }}
            />
          )
        })}
      </Box>
      <Box sx={{ position: 'relative', height: 18, mt: 0.5 }}>
        {TICKS.map((hour) => (
          <Typography
            key={hour}
            variant="body2"
            color="text.secondary"
            sx={{
              position: 'absolute',
              left: `${(hour / 24) * 100}%`,
              transform:
                hour === 0 ? 'none' : hour === 24 ? 'translateX(-100%)' : 'translateX(-50%)',
              fontSize: '0.75rem',
              whiteSpace: 'nowrap',
            }}
          >
            {hour === 0 ? 'Planned' : `+${hour} h`}
          </Typography>
        ))}
      </Box>
    </Box>
  )
}
