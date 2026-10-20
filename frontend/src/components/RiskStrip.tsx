import Box from '@mui/material/Box'
import type { Checkpoint } from '../api/types.ts'
import { levelColor } from '../lib/risk.ts'

interface Props {
  checkpoints: Checkpoint[]
  totalMiles: number
  height?: number
}

/** The route from start to finish as one bar, each stretch colored by its checkpoint's risk. */
export default function RiskStrip({ checkpoints, totalMiles, height = 8 }: Props) {
  return (
    <Box
      aria-hidden
      sx={{
        display: 'flex',
        height,
        borderRadius: height / 2,
        overflow: 'hidden',
        bgcolor: 'divider',
      }}
    >
      {checkpoints.map((cp) => (
        <Box
          key={cp.index}
          sx={{
            flex: `0 0 ${(cp.covered_miles / totalMiles) * 100}%`,
            bgcolor: levelColor(cp.level),
          }}
        />
      ))}
    </Box>
  )
}
