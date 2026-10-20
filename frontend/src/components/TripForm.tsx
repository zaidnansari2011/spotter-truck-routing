import { useState, type FormEvent } from 'react'
import dayjs, { type Dayjs } from 'dayjs'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import InputAdornment from '@mui/material/InputAdornment'
import Link from '@mui/material/Link'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker'
import type { Place, PlanRequest } from '../api/types.ts'
import { timeZoneName } from '../lib/format.ts'
import PlaceField from './PlaceField.tsx'

const MAX_LOAD_LB = 80_000
const EXAMPLE: { origin: Place; destination: Place } = {
  origin: { label: 'Chicago, IL', lat: 41.883229, lon: -87.632398 },
  destination: { label: 'Denver, CO', lat: 39.738453, lon: -104.984853 },
}

interface Props {
  busy: boolean
  onSubmit: (request: PlanRequest) => void
}

function nextQuarterHour(): Dayjs {
  const now = dayjs()
  return now
    .add(15 - (now.minute() % 15), 'minute')
    .second(0)
    .millisecond(0)
}

export default function TripForm({ busy, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState<Dayjs | null>(nextQuarterHour)
  const [load, setLoad] = useState('38000')
  const [errors, setErrors] = useState<Record<string, string>>({})

  function validate(): Record<string, string> {
    const found: Record<string, string> = {}
    if (!origin) found.origin = 'Choose a starting point from the list'
    if (!destination) found.destination = 'Choose a destination from the list'
    if (origin && destination && origin.lat === destination.lat && origin.lon === destination.lon) {
      found.destination = 'Destination must differ from the starting point'
    }
    if (!departure || !departure.isValid()) found.departure = 'Enter a departure date and time'
    else if (departure.isBefore(dayjs().subtract(15, 'minute')))
      found.departure = 'Departure cannot be in the past'
    else if (departure.isAfter(dayjs().add(7, 'day')))
      found.departure = 'Departure must be within the next 7 days'
    const pounds = Number(load)
    if (load.trim() === '' || !Number.isFinite(pounds) || pounds < 0 || pounds > MAX_LOAD_LB) {
      found.load = `Enter a load from 0 to ${MAX_LOAD_LB.toLocaleString('en-US')} lb`
    }
    return found
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length) return
    onSubmit({
      origin: origin!,
      destination: destination!,
      departure: departure!.format(), // ISO 8601 with the viewer's UTC offset
      load_lb: Number(load),
    })
  }

  function fillExample() {
    setOrigin(EXAMPLE.origin)
    setDestination(EXAMPLE.destination)
    setErrors({})
  }

  return (
    <Box component="form" onSubmit={submit} noValidate>
      <Stack spacing={2}>
        <PlaceField label="From" value={origin} onChange={setOrigin} error={errors.origin} />
        <PlaceField
          label="To"
          value={destination}
          onChange={setDestination}
          error={errors.destination}
        />
        <DateTimePicker
          label={`Departure (${timeZoneName()})`}
          value={departure}
          onChange={setDeparture}
          minDateTime={dayjs().subtract(15, 'minute')}
          maxDateTime={dayjs().add(7, 'day')}
          slotProps={{
            textField: {
              size: 'small',
              fullWidth: true,
              error: Boolean(errors.departure),
              helperText: errors.departure,
            },
          }}
        />
        <TextField
          label="Load weight"
          value={load}
          onChange={(e) => setLoad(e.target.value)}
          error={Boolean(errors.load)}
          helperText={errors.load ?? 'Cargo only. Load rules apply above 30,000 and 40,000 lb.'}
          slotProps={{
            htmlInput: { inputMode: 'numeric', min: 0, max: MAX_LOAD_LB, step: 500 },
            input: { endAdornment: <InputAdornment position="end">lb</InputAdornment> },
          }}
          type="number"
        />
        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={busy}
          startIcon={busy ? <CircularProgress size={18} color="inherit" /> : null}
        >
          {busy ? 'Checking routes and forecasts' : 'Find routes'}
        </Button>
        {!origin && !destination && (
          <Typography variant="body2" color="text.secondary">
            New here?{' '}
            <Link
              component="button"
              type="button"
              onClick={fillExample}
              sx={{ verticalAlign: 'baseline' }}
            >
              Fill in Chicago to Denver
            </Link>
          </Typography>
        )}
      </Stack>
    </Box>
  )
}
