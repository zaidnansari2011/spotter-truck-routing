import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiFetch } from './client.ts'
import type { CorridorFrames, Place, Plan, PlanRequest } from './types.ts'

export function usePlan() {
  return useMutation({
    mutationFn: (request: PlanRequest) =>
      apiFetch<Plan>('/plan/', { method: 'POST', body: JSON.stringify(request) }),
  })
}

export function usePlaceSuggestions(query: string) {
  const debounced = useDebounced(query.trim(), 250)
  return useQuery({
    queryKey: ['suggest', debounced.toLowerCase()],
    queryFn: ({ signal }) =>
      apiFetch<Place[]>(`/suggest/?q=${encodeURIComponent(debounced)}`, { signal }),
    enabled: debounced.length >= 2,
    staleTime: 60 * 60 * 1000,
  })
}

export function useCorridor(plan: Plan | undefined, start: string | undefined) {
  return useQuery({
    queryKey: ['corridor', plan?.generated_at, start],
    queryFn: ({ signal }) =>
      apiFetch<CorridorFrames>('/corridor/', {
        method: 'POST',
        signal,
        body: JSON.stringify({ points: plan!.corridor.points, start, load_lb: plan!.load_lb }),
      }),
    enabled: Boolean(plan && start && plan.corridor.points.length),
    staleTime: 10 * 60 * 1000,
  })
}

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
