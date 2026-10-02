/**
 * Calendar-date helpers.
 *
 * The API speaks plain `YYYY-MM-DD` dates and local wall-clock `HH:MM` times,
 * so everything here stays in date-space: no timezone math beyond "what is
 * today where the user is".
 */

const MS_PER_DAY = 86_400_000

export type ISODate = string

export function defaultTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

/** Today's calendar date in the given IANA zone, as YYYY-MM-DD. */
export function todayInZone(timeZone: string): ISODate {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
  } catch {
    return new Date().toISOString().slice(0, 10)
  }
}

function parts(iso: ISODate): [number, number, number] {
  const [y, m, d] = iso.split('-').map(Number)
  return [y, m, d]
}

/** A UTC-midnight Date for a calendar date, so day arithmetic never drifts. */
function asUTC(iso: ISODate): Date {
  const [y, m, d] = parts(iso)
  return new Date(Date.UTC(y, m - 1, d))
}

function toISO(date: Date): ISODate {
  const y = date.getUTCFullYear()
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  const d = String(date.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function addDays(iso: ISODate, days: number): ISODate {
  return toISO(new Date(asUTC(iso).getTime() + days * MS_PER_DAY))
}

/** The final day of a plan that starts on `start` and runs `days` days. */
export function summitDate(start: ISODate, days: number): ISODate {
  return addDays(start, Math.max(1, days) - 1)
}

export function daysBetween(from: ISODate, to: ISODate): number {
  return Math.round((asUTC(to).getTime() - asUTC(from).getTime()) / MS_PER_DAY)
}

export function isValidISO(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(asUTC(value).getTime())
}

const utcFormat = (options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat('en-GB', { ...options, timeZone: 'UTC' })

/** `12 Oct` */
export function formatDayMonth(iso: ISODate): string {
  return utcFormat({ day: 'numeric', month: 'short' }).format(asUTC(iso))
}

/** `Sun 12 Oct 2026` */
export function formatFull(iso: ISODate): string {
  return utcFormat({ weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }).format(asUTC(iso))
}

/** `October 2026` */
export function formatMonthYear(iso: ISODate): string {
  return utcFormat({ month: 'long', year: 'numeric' }).format(asUTC(iso))
}

/** `GMT+1` for the zone right now. */
export function offsetLabel(timeZone: string, at: Date = new Date()): string {
  try {
    const found = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'shortOffset' })
      .formatToParts(at)
      .find((part) => part.type === 'timeZoneName')
    return found?.value ?? ''
  } catch {
    return ''
  }
}

/** Turn `08:00` into `8:00 am`. The API keeps 24-hour time. */
export function formatClock(value: string): string {
  const [h, m] = value.split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return value
  const suffix = h < 12 ? 'am' : 'pm'
  const hour = h % 12 === 0 ? 12 : h % 12
  return `${hour}:${String(m).padStart(2, '0')} ${suffix}`
}

/** A plausible list of zones, browser default first — no external data needed. */
export function timezoneChoices(): string[] {
  const local = defaultTimezone()
  const common = [
    'UTC',
    'Europe/London',
    'Europe/Lisbon',
    'Europe/Paris',
    'Europe/Berlin',
    'Europe/Madrid',
    'Africa/Lagos',
    'Africa/Accra',
    'Africa/Nairobi',
    'Africa/Johannesburg',
    'Asia/Dubai',
    'Asia/Karachi',
    'Asia/Kolkata',
    'Asia/Singapore',
    'Asia/Tokyo',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Sao_Paulo',
    'Australia/Sydney',
  ]
  return [local, ...common.filter((zone) => zone !== local)]
}
