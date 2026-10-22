import Box from '@mui/material/Box'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import type { RouteOption } from '../api/types.ts'
import { formatClock, formatPrecip, formatWind, timeZoneName } from '../lib/format.ts'
import { levelStyle } from '../lib/risk.ts'

interface Props {
  route: RouteOption
  interval: number
}

export default function CheckpointTable({ route, interval }: Props) {
  const checkpoints = route.checkpoints
  return (
    <Box component="section" aria-labelledby="checkpoints-heading">
      <Typography id="checkpoints-heading" variant="h2" component="h2">
        Checkpoints on Route {route.id}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Every {interval} miles, with the forecast for when the truck gets there. Times in{' '}
        {timeZoneName(route.arrival)}, wind in mph, rain and snow in inches per hour.
      </Typography>
      <TableContainer
        sx={{
          maxHeight: 360,
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
          '& .MuiTableCell-root': { px: 1, py: 0.5 },
        }}
      >
        <Table size="small" stickyHeader aria-label={`Checkpoints on route ${route.id}`}>
          <TableHead>
            <TableRow>
              <TableCell align="right">Mile</TableCell>
              <TableCell>Arrives</TableCell>
              <TableCell>Risk</TableCell>
              <TableCell align="right">Wind</TableCell>
              <TableCell align="right">Rain</TableCell>
              <TableCell align="right">Snow</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {checkpoints.map((cp) => {
              const style = levelStyle(cp.level)
              return (
                <TableRow key={cp.index}>
                  <TableCell align="right">{Math.round(cp.mile).toLocaleString('en-US')}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatClock(cp.eta)}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    <Box
                      component="span"
                      sx={{
                        display: 'inline-block',
                        width: 9,
                        height: 9,
                        borderRadius: '50%',
                        bgcolor: style.color,
                        mr: 0.75,
                      }}
                    />
                    {style.label}
                    {cp.load_rule && (
                      <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                        title={cp.load_rule}
                      >
                        {' '}
                        (load)
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {cp.forecast ? formatWind(cp.wind_mph!) : '-'}
                  </TableCell>
                  <TableCell align="right">
                    {cp.forecast ? formatPrecip(cp.rain_in_hr!) : '-'}
                  </TableCell>
                  <TableCell align="right">
                    {cp.forecast ? formatPrecip(cp.snow_in_hr!) : '-'}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  )
}
