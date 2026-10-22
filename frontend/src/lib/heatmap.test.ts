import { describe, expect, it } from 'vitest'
import type { CorridorFrames } from '../api/types.ts'
import {
  colorExpression,
  corridorFeatures,
  opacityExpression,
  radiusExpression,
  valueAt,
} from './heatmap.ts'
import { LEVELS } from './risk.ts'

const row = (value: number | null) => Array.from({ length: 50 }, () => value)

const FRAMES: CorridorFrames = {
  hours: Array.from({ length: 50 }, (_, h) => 1_800_000_000 + h * 3600),
  risk: [row(150), row(null)],
  risk_load: [row(300), row(null)],
  wind: [row(30), row(null)],
  rain: [row(5), row(null)],
  snow: [row(0), row(null)],
}

describe('corridorFeatures', () => {
  it('puts the 50 hourly values of the chosen layer on each point', () => {
    const fc = corridorFeatures(
      [
        [-100, 40],
        [-99.5, 40],
      ],
      FRAMES,
      'wind',
    )

    expect(fc.features).toHaveLength(2)
    expect(fc.features[0].geometry.coordinates).toEqual([-100, 40])
    expect(Object.keys(fc.features[0].properties!)).toHaveLength(50)
    expect(fc.features[0].properties!.v49).toBe(30)
  })

  it('draws missing hours as calm (transparent) rather than failing', () => {
    const fc = corridorFeatures(
      [
        [0, 0],
        [1, 1],
      ],
      FRAMES,
      'risk',
    )
    expect(fc.features[1].properties!.v0).toBe(0)
  })
})

describe('valueAt', () => {
  it('reads a whole hour directly', () => {
    expect(valueAt(12)).toEqual(['get', 'v12'])
  })

  it('blends neighbouring hours for quarter-hour steps', () => {
    expect(valueAt(12.25)).toEqual(['+', ['*', ['get', 'v12'], 0.75], ['*', ['get', 'v13'], 0.25]])
  })

  it('keeps blending at the end of the slider when the departure is not on the hour', () => {
    // Slider hour 48 with a departure 45 minutes past the hour is frame position 48.75.
    expect(valueAt(48.75)).toEqual(['+', ['*', ['get', 'v48'], 0.25], ['*', ['get', 'v49'], 0.75]])
  })

  it('clamps to the frames there are', () => {
    expect(valueAt(-3)).toEqual(['get', 'v0'])
    expect(valueAt(60)).toEqual(['get', 'v49'])
  })
})

describe('colorExpression', () => {
  it('starts each band at its level color and blends only near the next band', () => {
    const expr = colorExpression('risk', 0) as unknown[]
    const stops = expr.slice(3)

    expect(stops).toEqual([
      100,
      LEVELS[1].color, // Moderate from 100
      190,
      LEVELS[1].color, // still Moderate at 190
      200,
      LEVELS[2].color, // High from 200
      290,
      LEVELS[2].color,
      300,
      LEVELS[3].color,
      390,
      LEVELS[3].color,
      400,
      LEVELS[4].color,
    ])
  })

  it('uses each layer’s own thresholds', () => {
    const wind = colorExpression('wind', 0) as unknown[]
    expect(wind.slice(3, 5)).toEqual([250, LEVELS[1].color]) // 25.0 mph in tenths
    const rain = colorExpression('rain', 0) as unknown[]
    expect(rain.at(-2)).toBe(1001) // No Travel is more than 1.000 in/hr
  })
})

describe('opacityExpression', () => {
  it('is fully transparent below Moderate, so Low areas are never tinted', () => {
    const expr = opacityExpression('snow', 0) as unknown[]
    expect(expr.slice(0, 2)).toEqual(['step', ['get', 'v0']])
    expect(expr[2]).toBe(0) // below the first step
    expect(expr[3]).toBe(500) // snow Moderate starts at 0.500 in/hr
  })

  it('gets more opaque as conditions get worse', () => {
    const ramp = (opacityExpression('risk', 0) as unknown[])[4] as unknown[]
    expect(ramp.slice(3)).toEqual([100, 0.3, 200, 0.45, 400, 0.62])
  })
})

describe('radiusExpression', () => {
  it('doubles the radius with every zoom level', () => {
    const expr = radiusExpression(0.35) as unknown[]
    const [, , , z0, r0, z12, r12] = expr as number[]
    expect(z0).toBe(0)
    expect(z12).toBe(12)
    expect(r12 / r0).toBe(2 ** 12)
    expect(r0).toBeCloseTo((0.35 / 360) * 512 * 1.8, 6)
  })
})
