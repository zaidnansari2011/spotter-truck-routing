import { useState } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import CircularProgress from '@mui/material/CircularProgress'
import TextField from '@mui/material/TextField'
import { usePlaceSuggestions } from '../api/hooks.ts'
import type { Place } from '../api/types.ts'

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  error?: string
}

export default function PlaceField({ label, value, onChange, error }: Props) {
  const [input, setInput] = useState('')
  const suggestions = usePlaceSuggestions(input)
  const options = suggestions.data ?? []

  const noOptionsText =
    input.trim().length < 2
      ? 'Type at least 2 letters'
      : suggestions.isError
        ? 'Place search is unavailable. Try again shortly.'
        : 'No matching places in the US or Canada'

  return (
    <Autocomplete
      value={value}
      onChange={(_, place) => onChange(place)}
      inputValue={input}
      onInputChange={(_, text) => setInput(text)}
      options={
        value && !options.some((o) => o.label === value.label) ? [value, ...options] : options
      }
      getOptionLabel={(place) => place.label}
      isOptionEqualToValue={(a, b) => a.lat === b.lat && a.lon === b.lon}
      filterOptions={(all) => all} // the server already filters
      loading={suggestions.isFetching}
      noOptionsText={noOptionsText}
      autoHighlight
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          error={Boolean(error)}
          helperText={error}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              endAdornment: (
                <>
                  {suggestions.isFetching ? <CircularProgress color="inherit" size={16} /> : null}
                  {params.slotProps.input.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  )
}
