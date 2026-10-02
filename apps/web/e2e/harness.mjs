/**
 * Shared plumbing for the web smoke harness.
 *
 * The e2e run drives a real headless Chrome through the first-agenda flow
 * against a live API and Vite, writes the screenshots the review loop reads,
 * and fails loudly when a state does not render. It is a smoke test, not a
 * pixel test: it proves the flow works and the card is drawn.
 */
import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import puppeteer from 'puppeteer-core'

export const HERE = path.dirname(fileURLToPath(import.meta.url))
export const WEB_DIR = path.resolve(HERE, '..')
export const ROOT = path.resolve(WEB_DIR, '..', '..')
export const API_DIR = path.join(ROOT, 'apps', 'api')

/** Today's date in an IANA zone, as YYYY-MM-DD. */
function todayIn(timeZone) {
  return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(
    new Date(),
  )
}

const apiBase = process.env.E2E_API ?? 'http://127.0.0.1:8000/api/v1'

export const config = {
  /** API root, including the version prefix. */
  api: apiBase,
  /** API origin, for the root-level /healthz probe. */
  apiOrigin: new URL(apiBase).origin,
  /** Vite dev server. */
  web: (process.env.E2E_WEB ?? 'http://localhost:5173').replace(/\/+$/, ''),
  /** Where screenshots land. */
  out: process.env.E2E_OUT ?? path.join(ROOT, '.impeccable', 'review'),
  /** Where the HTML snapshots for the URL detector land. */
  snap: process.env.E2E_SNAP ?? path.join(os.tmpdir(), 'agentda-e2e-snap'),
  /** SQLite file the managed API runs against. */
  db: process.env.E2E_DB ?? path.join(os.tmpdir(), `agentda-e2e-${process.pid}.db`),
  /** Explicit Chrome path; auto-detected when null. */
  chrome: process.env.CHROME ?? null,
  /** Fixed agenda start date; defaults to today in the agenda's zone. */
  startDate: process.env.E2E_START_DATE ?? todayIn('Africa/Lagos'),
  /** Whether run.mjs owns the servers (false => attach to servers you started). */
  manageServers: !process.env.E2E_NO_SERVER,
  /** Keep the throwaway database after the run. */
  keepDb: Boolean(process.env.E2E_KEEP_DB),
}

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** Find a Chrome/Chromium binary the way a person would. */
export async function resolveChrome() {
  if (config.chrome) return config.chrome

  const known = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ]
  for (const candidate of known) {
    try {
      await fs.access(candidate)
      return candidate
    } catch {
      /* keep looking */
    }
  }
  for (const name of ['google-chrome', 'chromium', 'chromium-browser', 'chrome']) {
    try {
      const found = execFileSync('which', [name], { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
      if (found) return found
    } catch {
      /* keep looking */
    }
  }
  throw new Error('No Chrome found. Install Chrome/Chromium or set CHROME=/path/to/chrome.')
}

export async function launchBrowser() {
  return puppeteer.launch({
    executablePath: await resolveChrome(),
    headless: true,
    userDataDir: path.join(os.tmpdir(), `agentda-e2e-chrome-${Date.now()}`),
    args: [
      '--headless=new',
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--hide-scrollbars',
      '--font-render-hinting=none',
    ],
  })
}

/* ------------------------------------------------------------------ checks */

/** Collect smoke-check failures and report them without stopping the run. */
export function createChecks() {
  const failures = []
  return {
    failures,
    ok(condition, message) {
      if (!condition) failures.push(message)
    },
    contains(haystack, needle, message) {
      if (!String(haystack ?? '').includes(needle)) {
        failures.push(`${message} (looked for ${JSON.stringify(needle)})`)
      }
    },
    report(phase) {
      if (failures.length === 0) {
        console.log(`  ok  ${phase}`)
      } else {
        console.log(`  FAIL ${phase} (${failures.length})`)
        for (const failure of failures) console.log(`      - ${failure}`)
      }
      return failures.length === 0
    },
  }
}

/* --------------------------------------------------------------- api client */

export function createApi(base = config.api) {
  const parse = async (response) => {
    const text = await response.text()
    return text ? JSON.parse(text) : null
  }
  const expectOk = async (response, what) => {
    if (!response.ok) throw new Error(`${what} failed: ${response.status} ${await response.text()}`)
    return response
  }

  return {
    /** Create a throwaway holder; returns headers and a browser session. */
    async signup(overrides = {}) {
      const email = `e2e.${Date.now()}.${Math.random().toString(36).slice(2, 7)}@example.com`
      const response = await fetch(`${base}/auth/signup`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          email,
          password: 'route-card-1234',
          full_name: 'Wale',
          timezone: 'Africa/Lagos',
          ...overrides,
        }),
      })
      await expectOk(response, 'signup')
      const auth = await parse(response)
      return {
        auth,
        headers: { 'content-type': 'application/json', authorization: `Bearer ${auth.access_token}` },
        session: { access_token: auth.access_token, refresh_token: auth.refresh_token, user: auth.user },
      }
    },

    async createAgenda(headers, body) {
      const response = await fetch(`${base}/agendas`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          reminder_channel: 'email',
          reminder_time: '08:00',
          timezone: 'Africa/Lagos',
          start_date: config.startDate,
          ...body,
        }),
      })
      await expectOk(response, 'create agenda')
      return parse(response)
    },

    async generate(headers, id) {
      const response = await fetch(`${base}/agendas/${id}/generate`, { method: 'POST', headers })
      await expectOk(response, 'generate')
      return parse(response)
    },

    async approve(headers, id) {
      const response = await fetch(`${base}/agendas/${id}/approve`, { method: 'POST', headers })
      await expectOk(response, 'approve')
      return parse(response)
    },

    async patchDay(headers, id, dayIndex, body) {
      const response = await fetch(`${base}/agendas/${id}/days/${dayIndex}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(body),
      })
      await expectOk(response, 'patch day')
      return parse(response)
    },

    /** Poll the draft until it reaches one of `wanted`, or throw. */
    async waitForDraft(headers, id, wanted, timeoutMs = 60_000) {
      const deadline = Date.now() + timeoutMs
      let last = null
      while (Date.now() < deadline) {
        const response = await fetch(`${base}/agendas/${id}/draft`, { headers })
        if (response.ok) {
          last = await response.json()
          if (wanted.includes(last.status)) return last
        }
        await sleep(150)
      }
      throw new Error(`draft never reached ${wanted.join('/')} (last: ${last?.status ?? 'unavailable'})`)
    },
  }
}

/* ------------------------------------------------------------ page capture */

const urlFor = (agendaId) => `${config.web}/new${agendaId ? `?agenda=${agendaId}` : ''}`

async function settlePage(page) {
  await page.evaluate(() => document.fonts.ready)
  // Two frames so the ResizeObserver-driven profile has a measured width before
  // the shot; a single frame can capture it blank.
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(null)))),
  )
}

/** Open the card with an injected session and a settled layout. */
async function openCard(browser, { session, expect, agendaId = null, width, height, mobile }) {
  const page = await browser.newPage()
  await page.setViewport({ width, height, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile })
  if (session) {
    await page.evaluateOnNewDocument((payload) => {
      localStorage.setItem('agentda.auth', JSON.stringify(payload))
    }, session)
  }
  await page.goto(urlFor(agendaId), { waitUntil: 'load' })
  await page.waitForSelector(expect, { timeout: 30_000 })
  await settlePage(page)
  return page
}

/** Screenshot one card state, optionally running a probe first. */
export async function shot(
  browser,
  { name, session, expect, agendaId = null, width = 1440, height = 900, mobile = false, settle = 900, fullPage = true, probe },
) {
  const page = await openCard(browser, { session, expect, agendaId, width, height, mobile })
  await sleep(settle)
  if (probe) await probe(page)
  await page.screenshot({ path: path.join(config.out, `${name}.png`), fullPage })
  await page.close()
  console.log(`  captured ${name}.png`)
}

/** Dump a settled page as self-contained HTML for the URL detector. */
export async function dumpHtml(
  browser,
  { name, session, expect, agendaId = null, width = 1440, height = 900, mobile = false },
) {
  const page = await openCard(browser, { session, expect, agendaId, width, height, mobile })
  await sleep(1200)
  const html = await page.content()
  await fs.writeFile(path.join(config.snap, `${name}.html`), html, 'utf8')
  await page.close()
  console.log(`  dumped ${name}.html`)
}

/* --------------------------------------------------------------- page probes */

/** How many plotted points the route profile currently draws. */
export function profilePointCount(page) {
  return page.evaluate(() => {
    const path = document.querySelector('[data-testid="profile"] svg path')
    if (!path) return 0
    return ((path.getAttribute('d') ?? '').match(/[ML]/g) ?? []).length
  })
}

/** The header band's state word (NEW, UNDER SURVEY, …). */
export function cardState(page) {
  return page.evaluate(() => document.querySelector('[data-testid="card-state"]')?.textContent?.trim() ?? '')
}
