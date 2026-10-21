import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Typography from '@mui/material/Typography'
import type { DepartureAdvice, DepartureOption } from '../api/types.ts'
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
  // Hovering previews an hour; clicking picks it. Planning it is a separate, explicit step.
  const [picked, setPicked] = useState<number>()
  const [hovered, setHovered] = useState<number>()
  const shownOffset = hovered ?? picked
  const shown = advice.options.find((o) => o.offset_h === shownOffset)

  return (
    <Box component="section" aria-labelledby="departure-heading">
      <Typography id="departure-heading" variant="h2" component="h2">
        Best time to leave
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Each bar is a departure time, from your planned one to 24 hours later, colored by the worst
        weather the best route would meet if you left then. Select a bar to see it.
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

      <Box
        role="group"
        aria-label="Departure hours"
        onMouseLeave={() => setHovered(undefined)}
        sx={{ display: 'flex', gap: '2px' }}
      >
        {advice.options.map((option) => {
          const style = levelStyle(option.worst_level)
          const isSuggestion = suggestion?.offset_h === option.offset_h
          const label = optionText(option)
          return (
            <ButtonBase
              key={option.offset_h}
              aria-label={label}
              aria-pressed={picked === option.offset_h}
              disabled={busy}
              onClick={() => setPicked(option.offset_h)}
              onMouseEnter={() => setHovered(option.offset_h)}
              onFocus={() => setHovered(option.offset_h)}
              onBlur={() => setHovered(undefined)}
              sx={{
                flex: 1,
                height: 22,
                borderRadius: '3px',
                bgcolor: style.color,
                outline:
                  option.offset_h === 0 || option.offset_h === picked
                    ? `2px solid ${tokens.asphalt}`
                    : 'none',
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

      <Box aria-live="polite" sx={{ mt: 1, minHeight: 56 }}>
        {shown ? (
          <>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              {optionText(shown)}
            </Typography>
            {shown.offset_h === 0 ? (
              <Typography variant="body2" color="text.secondary">
                This is the departure you planned.
              </Typography>
            ) : picked === shown.offset_h ? (
              <Button
                size="small"
                variant="outlined"
                disabled={busy}
                onClick={() => onReplan(shown.departure)}
                sx={{ mt: 0.75 }}
              >
                Plan this departure ({formatClock(shown.departure)})
              </Button>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Select the bar to plan this departure.
              </Typography>
            )}
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Nothing selected. Point at or select a bar to see that departure.
          </Typography>
        )}
      </Box>
    </Box>
  )
}

function optionText(option: DepartureOption): string {
  const style = levelStyle(option.worst_level)
  const when = option.offset_h === 0 ? 'planned' : `in ${option.offset_h} h`
  const severe = option.severe_miles ? `, ${formatMiles(option.severe_miles)} Severe` : ''
  return (
    `Leave ${formatClock(option.departure)} (${when}): Route ${option.route_id}, ` +
    `worst weather ${style.label}${severe}`
  )
}
