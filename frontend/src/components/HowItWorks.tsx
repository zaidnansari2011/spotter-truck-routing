import { useState, type ReactNode } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Link from '@mui/material/Link'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import HelpOutlineRounded from '@mui/icons-material/HelpOutlineRounded'
import { RANKING_RULES } from '../lib/explain.ts'
import { LEVELS } from '../lib/risk.ts'

const REPO_URL = 'https://github.com/zaidnansari2011/spotter-truck-routing'

// The thresholds from the brief, as the backend applies them (planner/domain/risk.py).
const BANDS: { factor: string; cells: string[] }[] = [
  { factor: 'Wind (mph)', cells: ['under 25', '25 to 34', '35 to 44', '45 to 54', '55 or more'] },
  {
    factor: 'Rain (in/hr)',
    cells: ['under 0.10', '0.10 to 0.25', '0.25 to 0.50', '0.50 to 1.00', 'over 1.00'],
  },
  {
    factor: 'Snow (in/hr)',
    cells: ['under 0.5', '0.5 to 1.0', '1.0 to 2.0', '2.0 to 3.0', 'over 3.0'],
  },
]

/** A short explanation of the method, for anyone using the app without reading the README. */
export default function HowItWorks() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button
        size="small"
        startIcon={<HelpOutlineRounded />}
        onClick={() => setOpen(true)}
        sx={{ ml: -0.5, mb: 2 }}
      >
        How it works
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" scroll="paper">
        <DialogTitle>How routes are compared</DialogTitle>
        <DialogContent dividers>
          <Section title="See it in bad weather">
            Real weather is often calm, so every route shows Low. The{' '}
            <Link href="/?demo=storm">simulated storm demo</Link> lays a made-up storm over the real
            forecast, clearly labelled, to show the risk and load rules at work. Try loads of
            20,000, 35,000 and 45,000 lb on the same trip.
          </Section>
          <Section title="1. Three truck routes">
            TomTom truck routing with your load plus an assumed 35,000 lb tractor-trailer (capped at
            80,000 lb). If TomTom returns fewer than 3 distinct routes, the others are found through
            a waypoint and labelled.
          </Section>
          <Section title="2. Weather when the truck gets there">
            Checkpoints sit at the start, every 10, 25 or 50 miles, and the destination. Each one
            gets its arrival time from TomTom&apos;s travel times, and the hourly forecast
            (Open-Meteo) for that time and place. A time past the forecast is shown as &quot;No
            forecast&quot;, never as safe.
          </Section>
          <Section title="3. Risk at each checkpoint">
            The worst of wind, rain and snow. Each band includes its lower value.
          </Section>
          <Box sx={{ overflowX: 'auto', mb: 1.5 }}>
            <Table size="small" aria-label="Risk thresholds">
              <TableHead>
                <TableRow>
                  <TableCell />
                  {LEVELS.map((level) => (
                    <TableCell key={level.label} sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
                      <Box
                        component="span"
                        sx={{
                          display: 'inline-block',
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          bgcolor: level.color,
                          mr: 0.75,
                        }}
                      />
                      {level.label}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {BANDS.map((band) => (
                  <TableRow key={band.factor}>
                    <TableCell sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
                      {band.factor}
                    </TableCell>
                    {band.cells.map((cell) => (
                      <TableCell key={cell} sx={{ whiteSpace: 'nowrap' }}>
                        {cell}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
          <Section title="4. Load rules">
            They can only raise a level: 45 to 54 mph wind with more than 30,000 lb of cargo is No
            Travel, and 35 to 44 mph wind with more than 40,000 lb is Severe. Wind of 55 mph or more
            is No Travel for any load.
          </Section>
          <Section title="5. Ranking">
            Each checkpoint stands for the miles halfway to its neighbors, so every level is counted
            in miles. Routes are compared in this order, each step only breaking ties in the one
            before:
            <Box component="ol" sx={{ my: 0.5, pl: 2.5 }}>
              {RANKING_RULES.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </Box>
            If every route crosses No Travel weather, the sign turns yellow and says so instead of
            recommending one.
          </Section>
          <Section title="6. The map">
            Dots show the weather when the truck reaches them. The shading shows the forecast at the
            time on the slider, for your load. Trucks move with the slider and leave the map when
            they arrive.
          </Section>
          <Typography variant="body2" color="text.secondary">
            More detail, assumptions and measurements:{' '}
            <Link href={REPO_URL} target="_blank" rel="noopener">
              source code and README
            </Link>
            ,{' '}
            <Link href="/api/docs/" target="_blank" rel="noopener">
              API documentation
            </Link>
            .
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="h2" component="h3" sx={{ mb: 0.25 }}>
        {title}
      </Typography>
      <Typography variant="body2" component="div">
        {children}
      </Typography>
    </Box>
  )
}
