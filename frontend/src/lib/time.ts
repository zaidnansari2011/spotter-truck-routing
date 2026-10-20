import dayjs, { type Dayjs } from 'dayjs'

/** The next quarter hour from now, the default departure. */
export function nextQuarterHour(): Dayjs {
  const now = dayjs()
  return now
    .add(15 - (now.minute() % 15), 'minute')
    .second(0)
    .millisecond(0)
}
