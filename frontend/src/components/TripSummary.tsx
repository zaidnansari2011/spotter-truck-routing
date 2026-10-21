import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import EditRounded from '@mui/icons-material/EditRounded'
import type { PlanRequest } from '../api/types.ts'
import { formatClock, timeZoneName } from '../lib/format.ts'
import { tokens } from '../theme.ts'

interface Props {
  request: PlanRequest
  onEdit: () => void
}

/** The planned trip in two lines, standing in for the form once results are shown. */
export default function TripSummary({ request, onEdit }: Props) {
  const details = [
    `Leaves ${formatClock(request.departure)} ${timeZoneName(request.departure)}`,
    `${request.load_lb.toLocaleString('en-US')} lb`,
    request.hos ? 'rest breaks on' : undefined,
  ].filter(Boolean)

  return (
    <Box
      component="section"
      aria-label="Planned trip"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        p: 1.5,
        border: `1px solid ${tokens.rule}`,
        borderRadius: 1,
        bgcolor: tokens.paper,
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontWeight: 800, lineHeight: 1.3 }}>
          {request.origin.label} to {request.destination.label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {details.join(', ')}
        </Typography>
      </Box>
      <Button
        size="small"
        variant="outlined"
        startIcon={<EditRounded />}
        onClick={onEdit}
        sx={{ flexShrink: 0 }}
      >
        Edit trip
      </Button>
    </Box>
  )
}
