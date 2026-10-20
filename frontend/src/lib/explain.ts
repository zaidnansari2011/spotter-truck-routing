import type { Ranking } from '../api/types.ts'

// The deciding criterion against the runner-up, in the driver's words.
const HEADLINES: Record<string, string> = {
  forecast: 'The only route with a forecast for the whole trip',
  no_travel_miles: 'Avoids No Travel conditions',
  severe_miles: 'Fewest miles in Severe weather',
  high_miles: 'Fewest miles in High-risk weather',
  avg_risk: 'Lowest average weather risk',
  duration: 'Fastest, with the same weather risk as the others',
  tie: 'Equal to the other routes on every measure',
}

export function recommendationHeadline(ranking: Ranking): string {
  if (ranking.all_no_travel)
    return 'Every route crosses No Travel conditions at this departure time'
  const runnerUp = ranking.comparisons[0]
  if (!runnerUp) return 'The only route available'
  return HEADLINES[runnerUp.decided_by] ?? 'Best match for the ranking rules'
}

/** The order the brief asks for, shown so the driver can see how routes are compared. */
export const RANKING_RULES = [
  'Fewest No Travel miles',
  'Fewest Severe miles',
  'Fewest High miles',
  'Lowest average risk',
  'Shortest travel time',
]
