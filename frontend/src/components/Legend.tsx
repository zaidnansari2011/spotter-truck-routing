import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import { LEVELS, NO_FORECAST } from '../lib/risk.ts'

export default function Legend() {
  return (
    <Paper
      elevation={2}
      component="section"
      aria-label="Risk levels"
      sx={{
        position: 'absolute',
        top: 12,
        left: 12,
        px: 1.5,
        py: 1,
        display: { xs: 'none', sm: 'block' },
      }}
    >
      <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>
        Weather risk
      </Typography>
      {[...LEVELS, NO_FORECAST].map((level) => (
        <Box key={level.label} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: level.color }} />
          <Typography variant="body2">{level.label}</Typography>
        </Box>
      ))}
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mt: 0.75, maxWidth: 170, lineHeight: 1.35 }}
      >
        Dots: weather when the truck gets there. Shading: weather at the time on the slider.
      </Typography>
    </Paper>
  )
}
