/**
 * Phase: `snap` — settled, self-contained HTML of the four card states the
 * URL detector scores. Write these, then serve `config.snap` and point
 * `impeccable detect --url` at each file.
 *
 * Needs AGENT_AUTOSTART=true.
 */
import { dumpHtml } from './harness.mjs'

export const autostart = true

const OBJECTIVE = {
  title: 'Launch my SaaS to 100 paying users',
  description: 'Ship the product and get the first 100 customers onto the Pro plan.',
  timeframe_days: 21,
}

export async function run({ browser, api }) {
  const holder = await api.signup()
  const agenda = await api.createAgenda(holder.headers, OBJECTIVE)
  await api.generate(holder.headers, agenda.id)
  await api.waitForDraft(holder.headers, agenda.id, ['needs_review'])

  await dumpHtml(browser, {
    name: 'capture',
    session: holder.session,
    expect: '[data-testid="objective"]',
  })
  await dumpHtml(browser, {
    name: 'capture-mobile',
    width: 390,
    height: 844,
    mobile: true,
    session: holder.session,
    expect: '[data-testid="objective"]',
  })
  await dumpHtml(browser, {
    name: 'review',
    session: holder.session,
    agendaId: agenda.id,
    expect: '[data-testid="camp-list"]',
  })
  await dumpHtml(browser, {
    name: 'review-mobile',
    width: 390,
    height: 844,
    mobile: true,
    session: holder.session,
    agendaId: agenda.id,
    expect: '[data-testid="camp-list"]',
  })
}
