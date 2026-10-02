/**
 * Phase: `focus` — the two keyboard-focus states no ordinary capture holds:
 * the ruled field's doubled underline and the primary tab's ring.
 *
 * Needs AGENT_AUTOSTART=true (it never generates, but the API must be the
 * managed one so the run owns its lifecycle).
 */
import { shot, sleep } from './harness.mjs'

export const autostart = true

export async function run({ browser, api, checks }) {
  const holder = await api.signup()

  await shot(browser, {
    name: 'focus-field',
    width: 1440,
    height: 900,
    session: holder.session,
    expect: '[data-testid="objective"]',
    fullPage: false,
    settle: 600,
    probe: async (page) => {
      await page.focus('[data-testid="objective"]')
      await sleep(200)
      const focused = await page.evaluate(
        () => document.activeElement?.matches('[data-testid="objective"]') ?? false,
      )
      checks.ok(focused, 'focus-field: the objective field did not take focus')
    },
  })

  await shot(browser, {
    name: 'focus-tab',
    width: 1440,
    height: 900,
    session: holder.session,
    expect: '[data-testid="objective"]',
    fullPage: false,
    settle: 600,
    probe: async (page) => {
      // Walk the tab order with the keyboard so :focus-visible actually fires.
      for (let step = 0; step < 40; step += 1) {
        const onPrimary = await page.evaluate(
          () => document.activeElement?.matches('button.punch-tab') ?? false,
        )
        if (onPrimary) break
        await page.keyboard.press('Tab')
      }
      const focused = await page.evaluate(() => document.activeElement?.matches('button.punch-tab') ?? false)
      checks.ok(focused, 'focus-tab: the primary tab never received keyboard focus')
      await sleep(200)
    },
  })
}
