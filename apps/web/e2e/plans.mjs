/**
 * Phase: `plans` — the index of every plan, populated, filtered and empty.
 *
 * Writes plans.png, plans-filtered.png, plans-mobile.png, plans-empty.png,
 * plans-delete-armed.png and plans-deleted.png.
 * Needs AGENT_AUTOSTART=true.
 */
import { shot, sleep } from './harness.mjs'

export const autostart = true

// The offline planner only treats an objective as specific once the description
// reaches 30 characters; below that it stops for clarifying questions instead of
// reaching `needs_review`, so keep every description here comfortably over it.
const DRAFT = {
  title: 'Learn to play the piano',
  description: 'Get through the first book and play one piece from memory.',
  timeframe_days: 60,
}

const REVIEW = {
  title: 'Launch my SaaS to 100 paying users',
  description: 'Ship the product and get the first 100 customers onto the Pro plan.',
  timeframe_days: 21,
}

const ACTIVE = {
  title: 'Get properly fit',
  description: 'Get in shape and stay there, with three sessions a week.',
  timeframe_days: 14,
}

const ROWS = '[data-testid="plan-list"] article'

export async function run({ browser, api, checks }) {
  // ---- empty: a brand-new holder with no plans --------------------------
  const empty = await api.signup()
  await shot(browser, {
    name: 'plans-empty',
    width: 1440,
    height: 900,
    session: empty.session,
    route: '/plans',
    expect: '[data-testid="plan-list"]',
    settle: 700,
    fullPage: false,
    probe: async (page) => {
      const rows = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(rows === 0, `plans-empty: expected no rows, saw ${rows}`)
      const text = await page.$eval('[data-testid="plan-list"]', (node) => node.textContent ?? '')
      checks.ok(text.includes('No plans yet'), 'plans-empty: the empty state is missing')
    },
  })

  // ---- populated: one draft, one ready to review, one active ------------
  const holder = await api.signup()

  // `created_at` is second-precision in SQLite, so space the creations out:
  // without this the three rows tie and the newest-first order is not visible.
  await api.createAgenda(holder.headers, DRAFT)
  await sleep(1100)

  const review = await api.createAgenda(holder.headers, REVIEW)
  await api.generate(holder.headers, review.id)
  await api.waitForDraft(holder.headers, review.id, ['needs_review'])
  await sleep(1100)

  const active = await api.createAgenda(holder.headers, ACTIVE)
  await api.generate(holder.headers, active.id)
  await api.waitForDraft(holder.headers, active.id, ['needs_review'])
  await api.approve(holder.headers, active.id)

  await shot(browser, {
    name: 'plans',
    width: 1440,
    height: 900,
    session: holder.session,
    route: '/plans',
    expect: '[data-testid="plan-list"]',
    settle: 900,
    fullPage: false,
    probe: async (page) => {
      const rows = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(rows === 3, `plans: expected 3 rows, saw ${rows}`)
      const text = await page.$eval('[data-testid="plan-list"]', (node) => node.textContent ?? '')
      for (const word of ['Draft', 'Ready to review', 'Active']) {
        checks.ok(text.includes(word), `plans: the list is missing the "${word}" status`)
      }
      // The contract orders the list by `created_at desc`; the newest plan is first.
      const first = await page.$eval(`${ROWS} a[href^="/new?agenda="]`, (node) => node.textContent ?? '')
      checks.ok(first.includes(ACTIVE.title), `plans: the newest plan is not first (saw "${first.trim()}")`)
    },
  })

  // ---- filtered: the Active tab narrows the list ------------------------
  await shot(browser, {
    name: 'plans-filtered',
    width: 1440,
    height: 900,
    session: holder.session,
    route: '/plans',
    expect: '[data-testid="plan-list"]',
    settle: 900,
    fullPage: false,
    probe: async (page) => {
      await page.evaluate(() => {
        const button = [...document.querySelectorAll('button')].find(
          (node) => node.textContent?.trim() === 'Active',
        )
        button?.click()
      })
      await sleep(800)
      const rows = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(rows === 1, `plans-filtered: expected 1 row, saw ${rows}`)
      const url = page.url()
      checks.ok(url.includes('status=active'), `plans-filtered: the URL did not record the filter (${url})`)
    },
  })

  // ---- mobile ----------------------------------------------------------
  await shot(browser, {
    name: 'plans-mobile',
    width: 390,
    height: 844,
    mobile: true,
    session: holder.session,
    route: '/plans',
    expect: '[data-testid="plan-list"]',
    settle: 900,
    fullPage: true,
  })

  // ---- delete: arm, confirm, and the row is gone for good ---------------
  await shot(browser, {
    name: 'plans-delete-armed',
    width: 1440,
    height: 900,
    session: holder.session,
    route: '/plans',
    expect: '[data-testid="plan-list"]',
    settle: 900,
    fullPage: false,
    probe: async (page) => {
      // The first press only arms the control; the label names the consequence.
      const deleteButton = await page.$(`${ROWS} button[aria-label^="Delete "]`)
      checks.ok(deleteButton !== null, 'plans-delete-armed: no delete control on a plan row')
      if (!deleteButton) return
      await deleteButton.click()
      const armed = await page.$eval(`${ROWS} button[aria-label^="Delete "]`, (node) => node.textContent ?? '')
      checks.ok(
        armed.includes('Delete for good'),
        `plans-delete-armed: the control did not arm (saw "${armed.trim()}")`,
      )
      const rows = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(rows === 3, `plans-delete-armed: arming must not delete anything (saw ${rows} rows)`)
    },
  })

  await shot(browser, {
    name: 'plans-deleted',
    width: 1440,
    height: 900,
    session: holder.session,
    route: '/plans',
    expect: '[data-testid="plan-list"]',
    settle: 900,
    fullPage: false,
    probe: async (page) => {
      const before = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(before === 3, `plans-deleted: expected 3 rows before deleting, saw ${before}`)

      const deleteButton = await page.$(`${ROWS} button[aria-label^="Delete "]`)
      checks.ok(deleteButton !== null, 'plans-deleted: no delete control on a plan row')
      if (!deleteButton) return
      await deleteButton.click()

      await Promise.all([
        page.waitForResponse((response) => response.request().method() === 'DELETE' && response.ok()),
        deleteButton.click(),
      ])
      await sleep(400)

      const after = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(after === 2, `plans-deleted: expected 2 rows after deleting, saw ${after}`)

      await page.reload({ waitUntil: 'load' })
      await page.waitForSelector(ROWS, { timeout: 10_000 })
      await sleep(600)
      const persisted = await page.$$eval(ROWS, (nodes) => nodes.length)
      checks.ok(persisted === 2, `plans-deleted: the deleted plan came back after reload (${persisted} rows)`)
    },
  })
}
