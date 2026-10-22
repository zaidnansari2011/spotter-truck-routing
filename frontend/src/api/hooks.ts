import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ApiError, apiFetch } from './client.ts'
import type { CorridorFrames, IntervalKey, Place, Plan, PlanRequest } from './types.ts'

/**
 * One plan per trip and sampling interval. Switching interval keeps the previous results on
 * screen until the new ones arrive; switching back is served from the cache.
 */
export function usePlan(request: PlanRequest | undefined, interval: IntervalKey) {
  return useQuery({
    queryKey: ['plan', request, interval],
    queryFn: ({ signal }) =>
      apiFetch<Plan>('/plan/', {
        method: 'POST',
        signal,
        body: JSON.stringify({ ...request, interval_mi: Number(interval) }),
      }),
    enabled: Boolean(request),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
    // Input and routing errors will not change on retry; only retry an unexpected server error.
    retry: (count, error) => count < 1 && error instanceof ApiError && error.status === 500,
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
    // The grid depends on the routes, not the sampling interval, so key it by the grid itself.
    queryKey: ['corridor', plan?.corridor.points, plan?.load_lb, plan?.simulation, start],
    queryFn: ({ signal }) => {
      if (!plan) throw new Error('No plan to fetch the corridor for') // never runs: see `enabled`
      return apiFetch<CorridorFrames>('/corridor/', {
        method: 'POST',
        signal,
        body: JSON.stringify({
          points: plan.corridor.points,
          start,
          load_lb: plan.load_lb,
          ...(plan.simulation ? { simulation: plan.simulation } : {}),
        }),
      })
    },
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
