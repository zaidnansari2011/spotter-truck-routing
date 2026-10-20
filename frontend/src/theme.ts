import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    primary: { main: '#0b4f6c' },
    secondary: { main: '#f4b942' },
    background: { default: '#f5f7f9' },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  },
})
