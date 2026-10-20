import { createTheme } from '@mui/material/styles'

// Highway signage palette: guide-sign green, asphalt, lane white and center-line yellow.
export const tokens = {
  signGreen: '#00653A',
  signGreenDark: '#004D2C',
  asphalt: '#2B2F33',
  asphaltSoft: '#5B6268',
  laneWhite: '#FFFFFF',
  paper: '#F6F7F5',
  rule: '#DDE1DC',
  centerLine: '#F2B705',
  routeInk: '#3E5568',
}

export const fontFamily = '"Overpass Variable", "Segoe UI", system-ui, sans-serif'

export const theme = createTheme({
  palette: {
    primary: { main: tokens.signGreen, dark: tokens.signGreenDark, contrastText: tokens.laneWhite },
    secondary: { main: tokens.centerLine, contrastText: tokens.asphalt },
    text: { primary: tokens.asphalt, secondary: tokens.asphaltSoft },
    background: { default: tokens.paper, paper: tokens.laneWhite },
    divider: tokens.rule,
  },
  shape: { borderRadius: 6 },
  typography: {
    fontFamily,
    h1: { fontSize: '1.375rem', fontWeight: 800, lineHeight: 1.2 },
    h2: { fontSize: '1.0625rem', fontWeight: 700, lineHeight: 1.3 },
    body1: { fontSize: '0.9375rem', lineHeight: 1.5 },
    body2: { fontSize: '0.8125rem', lineHeight: 1.45 },
    button: { textTransform: 'none', fontWeight: 700, letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { fontVariantNumeric: 'tabular-nums' },
        ':focus-visible': { outline: `3px solid ${tokens.centerLine}`, outlineOffset: 2 },
        '@media (prefers-reduced-motion: reduce)': {
          '*, *::before, *::after': {
            transitionDuration: '0.01ms !important',
            animationDuration: '0.01ms !important',
          },
        },
      },
    },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiTextField: { defaultProps: { size: 'small', fullWidth: true } },
    MuiToggleButton: { styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } } },
  },
})
