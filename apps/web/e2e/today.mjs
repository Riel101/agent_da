/**
 * Phase: `today` — the daily surface, empty and with real to-dos.
 *
 * Writes today-empty.png, today.png and today-mobile.png. The populated probe
 * checks a to-do off through the real UI, waits for the completion request, and
 * reloads to prove the check persisted. Needs AGENT_AUTOSTART=true.
 */
import { shot, sleep } from './harness.mjs'

export const autostart = true

const ACTIVE = {
  title: 'Write the first chapter',
  description: 'Finish a solid first chapter and have someone read it.',
  timeframe_days: 14,
}

const SECOND = {
  title: 'Learn conversational Spanish',
  description: 'Hold a ten-minute conversation without switching to English.',
  timeframe_days: 21,
}

const ROW = '[data-testid="todo-row"]'
const SUMMARY = '[data-testid="today-summary"]'

const readSummary = (page) =>
  page.$eval(SUMMARY, (node) => ({
    done: Number(node.getAttribute('data-done') ?? 0),
    total: Number(node.getAttribute('data-total') ?? 0),
  }))

export async function run({ browser, api, checks }) {
  // ---- empty: a brand-new holder has no plan running today ---------------
  const empty = await api.signup()
  await shot(browser, {
    name: 'today-empty',
    width: 1440,
    height: 900,
    session: empty.session,
    route: '/today',
    expect: '[data-testid="today-empty"]',
    settle: 700,
    fullPage: false,
    probe: async (page) => {
      const text = await page.$eval('[data-testid="today-empty"]', (node) => node.textContent ?? '')
      checks.ok(text.includes('Nothing scheduled today'), 'today-empty: the empty state is missing')
    },
  })

  // ---- populated: an approved plan has a day scheduled today -------------
  const holder = await api.signup()
  const agenda = await api.createAgenda(holder.headers, ACTIVE)
  await api.generate(holder.headers, agenda.id)
  await api.waitForDraft(holder.headers, agenda.id, ['needs_review'])
  await api.approve(holder.headers, agenda.id)

  await shot(browser, {
    name: 'today',
    width: 1440,
    height: 900,
    session: holder.session,
    route: '/today',
    expect: '[data-testid="today-panel"]',
    settle: 900,
    fullPage: false,
    probe: async (page) => {
      const before = await readSummary(page)
      checks.ok(before.total > 0, `today: expected today's to-dos, saw ${before.total}`)
      checks.ok(before.done === 0, `today: expected nothing done yet, saw ${before.done}`)

      const first = await page.$(ROW)
      checks.ok(first !== null, 'today: no to-do rows rendered')
      if (!first) return

      await Promise.all([
        page.waitForResponse(
          (response) =>
            response.request().method() === 'POST' &&
            response.url().includes('/complete') &&
            response.ok(),
        ),
        first.click(),
      ])
      await sleep(500)

      const after = await readSummary(page)
      checks.ok(
        after.done === before.done + 1,
        `today: the summary did not advance (${before.done} -> ${after.done})`,
      )
      const checked = await page.$eval(ROW, (node) => node.getAttribute('data-done'))
      checks.ok(checked === 'true', `today: the row did not check off (data-done=${checked})`)

      // The check is persisted, not just painted.
      await page.reload({ waitUntil: 'load' })
      await page.waitForSelector(ROW, { timeout: 10_000 })
      await sleep(700)
      const persisted = await readSummary(page)
      checks.ok(
        persisted.done === after.done,
        `today: the completion did not persist (${after.done} -> ${persisted.done})`,
      )
    },
  })

  // ---- two plans: tabs pick which day is shown --------------------------
  const second = await api.createAgenda(holder.headers, SECOND)
  await api.generate(holder.headers, second.id)
  await api.waitForDraft(holder.headers, second.id, ['needs_review'])
  await api.approve(holder.headers, second.id)

  await shot(browser, {
    name: 'today-tabs',
    width: 1440,
    height: 900,
    session: holder.session,
    route: '/today',
    expect: '[data-testid="today-panel"]',
    settle: 900,
    fullPage: false,
    probe: async (page) => {
      const tabs = await page.$$('button[aria-pressed]')
      checks.ok(tabs.length === 2, `today-tabs: expected 2 plan tabs, saw ${tabs.length}`)
      if (tabs.length < 2) return

      const before = await page.$eval('[data-testid="today-panel"] h2', (node) => node.textContent ?? '')
      await tabs[1].click()
      await sleep(500)
      const pressed = await page.$$eval('button[aria-pressed]', (nodes) =>
        nodes.map((node) => node.getAttribute('aria-pressed')),
      )
      checks.ok(
        pressed[1] === 'true' && pressed[0] === 'false',
        `today-tabs: the selected tab did not move (${pressed.join(',')})`,
      )
      const after = await page.$eval('[data-testid="today-panel"] h2', (node) => node.textContent ?? '')
      checks.ok(after !== before, 'today-tabs: switching plans did not change the day shown')
    },
  })

  // ---- mobile ------------------------------------------------------------
  await shot(browser, {
    name: 'today-mobile',
    width: 390,
    height: 844,
    mobile: true,
    session: holder.session,
    route: '/today',
    expect: '[data-testid="today-panel"]',
    settle: 900,
    fullPage: true,
  })
}
