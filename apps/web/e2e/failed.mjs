/**
 * Phase: `failed` — the card's failure notice.
 *
 * The offline planner never fails on its own, so this drives a real agenda to
 * needs_review and then flips the draft row in the throwaway SQLite file.
 * Needs AGENT_AUTOSTART=true.
 */
import { execFileSync } from 'node:child_process'

import { cardState, config, profilePointCount, shot } from './harness.mjs'

export const autostart = true

export async function run({ browser, api, checks }) {
  const holder = await api.signup()
  const agenda = await api.createAgenda(holder.headers, {
    title: 'Launch my SaaS to 100 paying users',
    description: 'Ship the product and get the first 100 customers onto the Pro plan.',
    timeframe_days: 21,
  })
  await api.generate(holder.headers, agenda.id)
  await api.waitForDraft(holder.headers, agenda.id, ['needs_review'])

  // SQLAlchemy stores UUIDs as 32-char hex with no dashes.
  const flipped = execFileSync('python3', [
    '-c',
    `import sqlite3
c = sqlite3.connect(${JSON.stringify(config.db)})
cur = c.execute(
    "UPDATE agenda_drafts SET status='failed', error=? WHERE agenda_id=?",
    ("The upstream model timed out while writing day 14.", ${JSON.stringify(agenda.id.replace(/-/g, ''))}),
)
c.commit()
print(cur.rowcount)`,
  ])
    .toString()
    .trim()
  checks.ok(Number(flipped) === 1, `failed: expected to flip 1 draft row, flipped ${flipped}`)

  await shot(browser, {
    name: 'failed',
    width: 1440,
    height: 1000,
    session: holder.session,
    agendaId: agenda.id,
    expect: '::-p-text(The route failed)',
    settle: 1200,
    probe: async (page) => {
      checks.ok((await profilePointCount(page)) >= 2, 'failed: the route profile drew fewer than 2 points')
      checks.contains(await cardState(page), 'FAILED', 'failed: card is not in the FAILED state')
    },
  })
}
