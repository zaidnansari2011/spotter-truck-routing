import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import { LEVELS, NO_FORECAST } from '../lib/risk.ts'

/** Risk key over the map: a column on wide screens, one compact row on phones. */
export default function Legend() {
  return (
    <Paper
      elevation={2}
      component="section"
      aria-label="Risk levels"
      sx={{
        position: 'absolute',
        top: { xs: 8, sm: 12 },
        left: { xs: 8, sm: 12 },
        right: { xs: 56, sm: 'auto' }, // clear of the zoom buttons on phones
        px: { xs: 1, sm: 1.5 },
        py: { xs: 0.5, sm: 1 },
      }}
    >
      <Typography
        variant="body2"
        sx={{ fontWeight: 700, mb: 0.5, display: { xs: 'none', sm: 'block' } }}
      >
        Weather risk
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'row', sm: 'column' },
          flexWrap: 'wrap',
          columnGap: 1.25,
        }}
      >
        {[...LEVELS, NO_FORECAST].map((level) => (
          <Box
            key={level.label}
            sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.5, sm: 1 } }}
          >
            <Box
              sx={{
                width: { xs: 10, sm: 12 },
                height: { xs: 10, sm: 12 },
                borderRadius: '50%',
                bgcolor: level.color,
                flexShrink: 0,
              }}
            />
            <Typography variant="body2" sx={{ fontSize: { xs: '0.75rem', sm: undefined } }}>
              {level.label}
            </Typography>
          </Box>
        ))}
      </Box>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mt: 0.75, maxWidth: 170, lineHeight: 1.35, display: { xs: 'none', sm: 'block' } }}
      >
        Dots: weather when the truck gets there. Shading: weather at the time on the slider.
      </Typography>
    </Paper>
  )
}
