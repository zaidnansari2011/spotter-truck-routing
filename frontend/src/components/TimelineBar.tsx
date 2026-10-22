import { memo, useCallback, useEffect, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
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
import { FRAME_COUNT, HEAT_LAYERS, THRESHOLDS, UNIT_SCALE } from '../lib/heatmap.ts'
import { arrivalNote, groupArrivals, type Arrival } from '../lib/trucks.ts'
import { tokens } from '../theme.ts'

export type Anchor = 'departure' | 'now'

const LAST_HOUR = FRAME_COUNT - 1
// Forecast hours played per second. 2 plays the 48 hours in 24 s, slow enough to follow the trucks.
const SPEEDS = [1, 2, 6]
const DEFAULT_SPEED = 2
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
  onTimeChange: (frameIndex: number, momentTs: number | undefined) => void
  arrivals?: Arrival[] // when each route's truck reaches the destination
}

function thresholdHint(layer: HeatLayer): string {
  const moderate = THRESHOLDS[layer][0] / UNIT_SCALE[layer]
  if (layer === 'wind') return `Colored from ${moderate} mph (Moderate)`
  if (layer === 'rain' || layer === 'snow')
    return `Colored from ${moderate.toFixed(2)} in/hr (Moderate)`
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
  arrivals = [],
}: Props) {
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(DEFAULT_SPEED)
  const frame = useRef<number | undefined>(undefined)

  // Frames start on the hour; the slider starts at the exact departure, so offset into the frames.
  const frameOffset = hours && startTs ? (startTs - hours[0]) / 3600 : 0

  // Paint the map whenever the time, the offset or the paint function (layer) changes.
  const momentTs = startTs !== undefined ? startTs + time * 3600 : undefined
  useEffect(
    () => onTimeChange(frameOffset + time, momentTs),
    [time, frameOffset, momentTs, onTimeChange],
  )

  useEffect(() => {
    if (!playing) return
    let last = performance.now()
    const step = (now: number) => {
      const elapsed = (now - last) / 1000
      last = now
      setTime((t) => Math.min(t + elapsed * speed, LAST_HOUR))
      frame.current = requestAnimationFrame(step)
    }
    frame.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame.current!)
  }, [playing, speed])

  const ready = Boolean(hours && startTs) && !loading
  // Playback stops at the last hour (pressing play again starts over) and while the forecast
  // reloads, when the slider is disabled.
  if (playing && (time >= LAST_HOUR || !ready)) setPlaying(false)

  const changeAnchor = useCallback(
    (next: Anchor) => {
      setTime(0)
      onAnchorChange(next)
    },
    [onAnchorChange],
  )

  function togglePlay() {
    if (!playing && time >= LAST_HOUR) setTime(0)
    setPlaying(!playing)
  }

  function nextSpeed() {
    setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])
  }

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
        // Floats over the map on wide screens; on phones it is a strip under the map.
        position: { xs: 'static', md: 'absolute' },
        left: 16,
        right: 16,
        bottom: 24,
        maxWidth: { md: 760 },
        borderRadius: { xs: 0, md: 1 },
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
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            px: 1,
            pt: arrivals.length ? 2 : 0, // room for the arrival flags above the track
            position: 'relative',
          }}
        >
          {ready && startTs !== undefined && <ArrivalFlags arrivals={arrivals} startTs={startTs} />}
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
              // MUI eases the thumb and track over 150 ms. Playback sets the value every frame, which
              // restarts that easing each time, so the thumb never moved off its old position.
              '& .MuiSlider-thumb, & .MuiSlider-track': { transition: 'none' },
            }}
          />
        </Box>
        <Button
          size="small"
          onClick={nextSpeed}
          disabled={!ready}
          aria-label={`Playback speed: ${speed} forecast hours per second. Change speed`}
          title="Playback speed"
          sx={{ minWidth: 0, px: 1, color: 'text.primary', whiteSpace: 'nowrap' }}
        >
          {speed} h/s
        </Button>
      </Box>

      {/* The clock and controls share a row and the description has two lines reserved, so the
          panel keeps its height while the text changes during playback. */}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          columnGap: 2,
          rowGap: 0.5,
        }}
      >
        <Typography sx={{ fontWeight: 800, lineHeight: 1.2 }}>
          {!loading && !error && moment ? `${formatClock(moment)} ${timeZoneName(moment)}` : ' '}
        </Typography>
        <TimelineControls
          anchor={anchor}
          onAnchorChange={changeAnchor}
          layer={layer}
          onLayerChange={onLayerChange}
        />
      </Box>
      <Box aria-live="polite" sx={{ minHeight: '2.9em', pt: 0.25, pb: 0.5, fontSize: '0.8125rem' }}>
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
          <Typography variant="body2" color="text.secondary">
            {[relative, arrivalNote(arrivals, moment), thresholdHint(layer)]
              .filter(Boolean)
              .join('. ')}
          </Typography>
        )}
        {!loading && !error && !moment && (
          <Typography variant="body2" color="text.secondary">
            Find routes to see the forecast along the trip
          </Typography>
        )}
      </Box>
    </Paper>
  )
}

/**
 * Timeline start and weather layer. Memoized, like ArrivalFlags: they do not change while the
 * forecast plays, and re-rendering them every frame was most of the timeline's render work.
 */
const TimelineControls = memo(function TimelineControls({
  anchor,
  onAnchorChange,
  layer,
  onLayerChange,
}: {
  anchor: Anchor
  onAnchorChange: (anchor: Anchor) => void
  layer: HeatLayer
  onLayerChange: (layer: HeatLayer) => void
}) {
  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
      <ToggleButtonGroup
        size="small"
        exclusive
        value={anchor}
        onChange={(_, value: Anchor | null) => value && onAnchorChange(value)}
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
  )
})

/** A route letter above the slider at the hour each truck arrives, so the trip's end is visible. */
const ArrivalFlags = memo(function ArrivalFlags({
  arrivals,
  startTs,
}: {
  arrivals: Arrival[]
  startTs: number
}) {
  return (
    <Box aria-hidden sx={{ position: 'absolute', left: 8, right: 8, top: 0, height: 26 }}>
      {groupArrivals(arrivals, startTs).map((group) => {
        const hour = group.hour
        const color =
          group.items.length === 1 && group.items[0].recommended ? tokens.signGreen : tokens.asphalt
        return (
          <Box
            key={group.items[0].id}
            title={group.items.map((a) => `Route ${a.id} arrives ${formatClock(a.ts)}`).join('\n')}
            sx={{
              position: 'absolute',
              left: `${(hour / LAST_HOUR) * 100}%`,
              transform: 'translateX(-50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <Box
              sx={{
                minWidth: 16,
                height: 16,
                px: group.items.length > 1 ? '5px' : 0,
                borderRadius: '8px',
                whiteSpace: 'nowrap',
                bgcolor: color,
                color: tokens.laneWhite,
                fontSize: 10,
                fontWeight: 800,
                lineHeight: '16px',
                textAlign: 'center',
              }}
            >
              {group.items.map((a) => a.id).join(' ')}
            </Box>
            {/* A short stem from the letter down to the track. */}
            <Box sx={{ width: 2, height: 8, bgcolor: color }} />
          </Box>
        )
      })}
    </Box>
  )
})
