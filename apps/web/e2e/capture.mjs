/**
 * Phase: `capture` — the whole happy path as one growing sheet.
 *
 * Writes desktop, review, clarify, mobile, mobile-review, review-top,
 * mobile-review-top and approved. Needs AGENT_AUTOSTART=true.
 */
import { cardState, profilePointCount, shot } from './harness.mjs'

export const autostart = true

const LONG_OBJECTIVE = {
  title: 'Launch my SaaS to 100 paying users',
  description: 'Ship the product and get the first 100 customers onto the Pro plan.',
  timeframe_days: 21,
}

const SHORT_OBJECTIVE = {
  title: 'Get properly fit',
  description: 'Get in shape.',
  timeframe_days: 30,
}

export async function run({ browser, api, checks }) {
  // ---- capture: a brand-new holder with no route yet --------------------
  const holder = await api.signup()
  const captureSession = holder.session
  await shot(browser, {
    name: 'desktop',
    width: 1440,
    height: 900,
    session: captureSession,
    expect: '[data-testid="objective"]',
    probe: async (page) => {
      checks.ok((await profilePointCount(page)) >= 2, 'desktop: the route profile drew fewer than 2 points')
      checks.contains(await cardState(page), 'NEW', 'desktop: card is not in the NEW state')
    },
  })

  // ---- review: a long objective plans without interrupting --------------
  const planner = await api.signup()
  const agenda = await api.createAgenda(planner.headers, LONG_OBJECTIVE)
  await api.generate(planner.headers, agenda.id)
  await api.waitForDraft(planner.headers, agenda.id, ['needs_review'])
  await api.patchDay(planner.headers, agenda.id, 3, {
    title: 'Wire the first three onboarding screens',
    expected_outcome: 'A new user reaches the first meaningful action without help.',
  })

  const reviewProbe = async (page) => {
    checks.ok((await profilePointCount(page)) >= 2, 'review: the route profile drew fewer than 2 points')
    checks.contains(await cardState(page), 'IN REVIEW', 'review: card is not in the IN REVIEW state')
  }

  await shot(browser, {
    name: 'review',
    width: 1440,
    height: 1000,
    session: planner.session,
    agendaId: agenda.id,
    expect: '[data-testid="camp-list"]',
    settle: 1400,
    probe: reviewProbe,
  })
  await shot(browser, {
    name: 'review-top',
    width: 1440,
    height: 1000,
    session: planner.session,
    agendaId: agenda.id,
    expect: '[data-testid="camp-list"]',
    settle: 1400,
    fullPage: false,
    probe: reviewProbe,
  })
  await shot(browser, {
    name: 'mobile-review',
    width: 390,
    height: 844,
    mobile: true,
    session: planner.session,
    agendaId: agenda.id,
    expect: '[data-testid="camp-list"]',
    settle: 1400,
    probe: reviewProbe,
  })
  await shot(browser, {
    name: 'mobile-review-top',
    width: 390,
    height: 844,
    mobile: true,
    session: planner.session,
    agendaId: agenda.id,
    expect: '[data-testid="camp-list"]',
    settle: 1400,
    fullPage: false,
    probe: reviewProbe,
  })

  // ---- approved: the route is stamped and live --------------------------
  await api.approve(planner.headers, agenda.id)
  await shot(browser, {
    name: 'approved',
    width: 1440,
    height: 1000,
    session: planner.session,
    agendaId: agenda.id,
    expect: '[data-testid="stamped"]',
    settle: 1400,
    probe: async (page) => {
      checks.ok((await profilePointCount(page)) >= 2, 'approved: the route profile drew fewer than 2 points')
      checks.contains(await cardState(page), 'APPROVED', 'approved: card is not in the APPROVED state')
    },
  })

  // ---- clarify: a short objective makes the agent ask -------------------
  const vague = await api.signup()
  const unclear = await api.createAgenda(vague.headers, SHORT_OBJECTIVE)
  await api.generate(vague.headers, unclear.id)
  const draft = await api.waitForDraft(vague.headers, unclear.id, ['needs_input'])
  checks.ok(
    Array.isArray(draft.clarifying_questions) && draft.clarifying_questions.length > 0,
    'clarify: the agent asked no clarifying questions for a vague objective',
  )
  await shot(browser, {
    name: 'clarify',
    width: 1440,
    height: 1000,
    session: vague.session,
    agendaId: unclear.id,
    expect: '::-p-text(Marginalia)',
    settle: 1200,
    probe: async (page) => {
      checks.contains(await cardState(page), 'NEEDS ANSWERS', 'clarify: card is not in the NEEDS ANSWERS state')
    },
  })

  // ---- mobile capture: the profile rotates to a vertical ascent ---------
  await shot(browser, {
    name: 'mobile',
    width: 390,
    height: 844,
    mobile: true,
    session: captureSession,
    expect: '[data-testid="objective"]',
    settle: 1200,
    probe: async (page) => {
      checks.ok((await profilePointCount(page)) >= 2, 'mobile: the vertical profile drew fewer than 2 points')
    },
  })
}
