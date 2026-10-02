/**
 * Phase: `planning` — the card under survey, before the draft lands.
 *
 * Requires AGENT_AUTOSTART=false so /generate only queues the draft.
 */
import { cardState, profilePointCount, shot } from './harness.mjs'

export const autostart = false

export async function run({ browser, api, checks }) {
  const holder = await api.signup()
  const agenda = await api.createAgenda(holder.headers, {
    title: 'Write and publish my first novel',
    description: 'Finish a full draft of the book and get it in front of ten readers.',
    timeframe_days: 90,
  })
  await api.generate(holder.headers, agenda.id)
  const draft = await api.waitForDraft(holder.headers, agenda.id, ['queued', 'running'])
  checks.ok(
    ['queued', 'running'].includes(draft.status),
    `planning: draft is "${draft.status}", expected queued/running`,
  )

  await shot(browser, {
    name: 'planning',
    width: 1440,
    height: 900,
    session: holder.session,
    agendaId: agenda.id,
    expect: '::-p-text(Under survey)',
    settle: 900,
    probe: async (page) => {
      checks.ok((await profilePointCount(page)) >= 2, 'planning: the provisional profile drew fewer than 2 points')
      checks.contains(await cardState(page), 'UNDER SURVEY', 'planning: card is not in the UNDER SURVEY state')
    },
  })
}
