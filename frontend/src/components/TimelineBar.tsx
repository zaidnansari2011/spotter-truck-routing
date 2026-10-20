import { useEffect, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import Slider from '@mui/material/Slider'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import PauseRounded from '@mui/icons-material/PauseRounded'
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded'
import type { HeatLayer } from '../api/types.ts'
import { formatClock, formatDuration, timeZoneName } from '../lib/format.ts'
import { FRAME_COUNT, HEAT_LAYERS, THRESHOLDS } from '../lib/heatmap.ts'
import { tokens } from '../theme.ts'

export type Anchor = 'departure' | 'now'

const LAST_HOUR = FRAME_COUNT - 1
const PLAY_HOURS_PER_SECOND = 6
const MARKS = [0, 12, 24, 36, 48].map((value) => ({ value, label: `${value} h` }))

interface Props {
  hours?: number[] // unix seconds of the 49 hourly forecast frames
  startTs?: number // unix seconds the slider's 0 stands for: the departure or the moment "now" was picked
  loading: boolean
  error?: string
  anchor: Anchor
  onAnchorChange: (anchor: Anchor) => void
  layer: HeatLayer
  onLayerChange: (layer: HeatLayer) => void
  onTimeChange: (frameIndex: number) => void
}

function thresholdHint(layer: HeatLayer): string {
  const [moderate] = THRESHOLDS[layer]
  if (layer === 'wind') return `Colored from ${moderate} mph (Moderate)`
  if (layer === 'rain' || layer === 'snow')
    return `Colored from ${(moderate / 100).toFixed(2)} in/hr (Moderate)`
  return 'Colored from Moderate risk'
}

export default function TimelineBar({
  hours,
  startTs,
  loading,
  error,
  anchor,
  onAnchorChange,
  layer,
  onLayerChange,
  onTimeChange,
}: Props) {
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const frame = useRef<number | undefined>(undefined)

  // Frames start on the hour; the slider starts at the exact departure, so offset into the frames.
  const frameOffset = hours && startTs ? (startTs - hours[0]) / 3600 : 0

  // Paint the map whenever the time, the offset or the paint function (layer) changes.
  useEffect(() => onTimeChange(frameOffset + time), [time, frameOffset, onTimeChange])

  useEffect(() => {
    if (!playing) return
    let last = performance.now()
    const step = (now: number) => {
      const elapsed = (now - last) / 1000
      last = now
      setTime((t) => {
        const next = t + elapsed * PLAY_HOURS_PER_SECOND
        if (next >= LAST_HOUR) {
          setPlaying(false)
          return LAST_HOUR
        }
        return next
      })
      frame.current = requestAnimationFrame(step)
    }
    frame.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame.current!)
  }, [playing])

  function togglePlay() {
    if (!playing && time >= LAST_HOUR) setTime(0)
    setPlaying(!playing)
  }

  const ready = Boolean(hours && startTs) && !loading
  const moment = hours && startTs ? startTs + time * 3600 : undefined
  const relative =
    time === 0
      ? anchor === 'departure'
        ? 'At departure'
        : 'Now'
      : `${formatDuration(time * 3600)} ${anchor === 'departure' ? 'after departure' : 'from now'}`

  return (
    <Paper
      elevation={3}
      component="section"
      aria-label="Weather forecast timeline"
      sx={{
        position: 'absolute',
        left: { xs: 8, sm: 16 },
        right: { xs: 8, sm: 16 },
        bottom: { xs: 8, sm: 24 },
        maxWidth: 760,
        mx: 'auto',
        px: { xs: 1.5, sm: 2 },
        pt: 1,
        pb: 0.5,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <IconButton
          onClick={togglePlay}
          disabled={!ready}
          aria-label={playing ? 'Pause forecast' : 'Play forecast'}
          sx={{
            bgcolor: tokens.asphalt,
            color: tokens.laneWhite,
            '&:hover': { bgcolor: tokens.routeInk },
          }}
        >
          {playing ? <PauseRounded /> : <PlayArrowRounded />}
        </IconButton>
        <Box sx={{ flex: 1, minWidth: 0, px: 1 }}>
          <Slider
            value={time}
            min={0}
            max={LAST_HOUR}
            step={0.25}
            marks={MARKS}
            disabled={!ready}
            onChange={(_, value) => {
              setPlaying(false)
              setTime(value as number)
            }}
            aria-label="Forecast hour"
            getAriaValueText={() =>
              moment ? `${formatClock(moment)}, ${relative}` : 'Forecast loading'
            }
            sx={{
              color: tokens.centerLine,
              '& .MuiSlider-markLabel': { fontSize: '0.75rem', color: 'text.secondary' },
              '& .MuiSlider-rail': { opacity: 0.35, bgcolor: tokens.asphalt },
            }}
          />
        </Box>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          columnGap: 2,
          rowGap: 0.5,
          pb: 0.5,
        }}
      >
        <Box aria-live="polite" sx={{ minWidth: 170 }}>
          {loading && (
            <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={14} /> Loading the corridor forecast
            </Typography>
          )}
          {!loading && error && (
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          )}
          {!loading && !error && moment && (
            <>
              <Typography sx={{ fontWeight: 800, lineHeight: 1.2 }}>
                {formatClock(moment)} {timeZoneName(moment)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {relative}. {thresholdHint(layer)}
              </Typography>
            </>
          )}
          {!loading && !error && !moment && (
            <Typography variant="body2" color="text.secondary">
              Find routes to see the forecast along the trip
            </Typography>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={anchor}
            onChange={(_, value: Anchor | null) => {
              if (!value) return
              setTime(0)
              onAnchorChange(value)
            }}
            aria-label="Start the timeline at"
          >
            <ToggleButton value="departure" sx={{ py: 0.25 }}>
              From departure
            </ToggleButton>
            <ToggleButton value="now" sx={{ py: 0.25 }}>
              From now
            </ToggleButton>
          </ToggleButtonGroup>
          <Select
            size="small"
            value={layer}
            onChange={(e) => onLayerChange(e.target.value as HeatLayer)}
            inputProps={{ 'aria-label': 'Weather shown on the map' }}
            sx={{ fontSize: '0.875rem', '& .MuiSelect-select': { py: 0.5 } }}
          >
            {HEAT_LAYERS.map((option) => (
              <MenuItem key={option.id} value={option.id}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </Box>
      </Box>
    </Paper>
  )
}
