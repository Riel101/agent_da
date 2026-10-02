/**
 * The AgentDa REST client.
 *
 * One module-level token store so any call can transparently refresh an expired
 * access token once, and a registered handler so the app can sign out when the
 * refresh token is dead too.
 */

const BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000/api/v1'

export type ReminderChannel = 'email' | 'whatsapp'
export type DraftStatus = 'queued' | 'running' | 'needs_input' | 'needs_review' | 'approved' | 'failed'

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export interface User {
  id: string
  email: string
  full_name: string | null
  timezone: string
  points_balance: number
  current_streak: number
  longest_streak: number
  phone_e164: string | null
  email_verified_at: string | null
}

export interface AuthResponse {
  user: User
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface Agenda {
  id: string
  user_id: string
  title: string
  description: string | null
  timeframe_days: number
  start_date: string
  end_date: string
  reminder_channel: ReminderChannel
  reminder_time: string
  timezone: string
  status: string
  approved_at: string | null
  total_points: number
  perfect_run: boolean
  created_at: string
}

export interface DraftTodo {
  title?: string
  notes?: string | null
  points?: number
  id?: string
  is_done?: boolean
}

export interface DraftDay {
  day_index: number
  scheduled_date: string
  title: string
  description: string | null
  expected_outcome: string | null
  expected_effort_minutes: number | null
  phase: string | null
  todos: DraftTodo[]
}

export interface ValidationIssue {
  severity: string
  code?: string
  day_index?: number | null
  message: string
}

export interface Draft {
  draft_id: string
  agenda_id: string
  status: DraftStatus
  revision: number
  clarifying_questions: string[]
  clarifying_answers: Record<string, string> | null
  validation_issues: ValidationIssue[]
  error: string | null
  model: string | null
  prompt_version: string | null
  repair_passes: number
  sub_agendas: DraftDay[]
  stats: { days: number; todos: number; expanded_days: number }
}

export interface SubAgenda {
  id: string
  agenda_id: string
  day_index: number
  scheduled_date: string
  title: string
  description: string | null
  expected_outcome: string | null
  expected_effort_minutes: number | null
  phase: string | null
  status: string
  is_user_edited: boolean
  todos_expanded: boolean
  done_count: number
  total_count: number
  is_complete: boolean
}

export interface Todo {
  id: string
  sub_agenda_id: string
  position: number
  title: string
  notes: string | null
  points: number
  is_done: boolean
  completed_at: string | null
  source: string
}

export interface DayDetail {
  sub_agenda: SubAgenda
  todos: Todo[]
}

export interface GenerateResult {
  draft_id: string
  status: DraftStatus
  revision: number
}

export interface ApproveResult {
  agenda: Agenda
  scheduled_reminders: number
  expanded_days: number
}

export interface AgendaCreateInput {
  title: string
  description: string
  timeframe_days: number
  start_date: string
  reminder_channel: ReminderChannel
  reminder_time: string
  timezone: string
  phone_e164?: string | null
}

/* ------------------------------------------------------------------ tokens */

interface TokenPair {
  access: string | null
  refresh: string | null
}

let tokens: TokenPair = { access: null, refresh: null }
let authLost: (() => void) | null = null
let refreshInFlight: Promise<string | null> | null = null

export function setTokens(access: string | null, refresh: string | null): void {
  tokens = { access, refresh }
}

export function getRefreshToken(): string | null {
  return tokens.refresh
}

export function setAuthLostHandler(handler: (() => void) | null): void {
  authLost = handler
}

/* ----------------------------------------------------------------- requests */

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

async function parseError(response: Response): Promise<ApiError> {
  let code = `HTTP_${response.status}`
  let message = response.statusText || 'Request failed'
  let details: Record<string, unknown> = {}
  try {
    const payload = (await response.json()) as Partial<ApiErrorBody> & { detail?: unknown }
    if (payload?.error) {
      code = payload.error.code ?? code
      message = payload.error.message ?? message
      details = payload.error.details ?? {}
    } else if (typeof payload?.detail === 'string') {
      message = payload.detail
    } else if (Array.isArray(payload?.detail)) {
      // FastAPI's validation error list.
      code = 'VALIDATION'
      message = payload.detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : String(item)))
        .join('; ')
    }
  } catch {
    /* keep the status defaults */
  }
  return new ApiError(response.status, code, message, details)
}

async function raw(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.auth !== false && tokens.access) headers.Authorization = `Bearer ${tokens.access}`

  return fetch(`${BASE}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
}

async function refreshAccessToken(): Promise<string | null> {
  if (!tokens.refresh) return null
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await raw('/auth/refresh', {
          method: 'POST',
          body: { refresh_token: tokens.refresh },
          auth: false,
        })
        if (!response.ok) return null
        const pair = (await response.json()) as { access_token: string; refresh_token: string }
        tokens = { access: pair.access_token, refresh: pair.refresh_token }
        return pair.access_token
      } catch {
        return null
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await raw(path, options)

  if (response.status === 401 && options.auth !== false && tokens.refresh) {
    const fresh = await refreshAccessToken()
    if (fresh) {
      response = await raw(path, options)
    } else {
      authLost?.()
    }
  }

  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/* ---------------------------------------------------------------- endpoints */

export const api = {
  base: BASE,

  signup(input: {
    email: string
    password: string
    full_name?: string
    timezone: string
    phone_e164?: string | null
  }): Promise<AuthResponse> {
    return request<AuthResponse>('/auth/signup', { method: 'POST', body: input, auth: false })
  },

  login(input: { email: string; password: string }): Promise<AuthResponse> {
    return request<AuthResponse>('/auth/login', { method: 'POST', body: input, auth: false })
  },

  me(): Promise<User> {
    return request<User>('/users/me')
  },

  patchMe(input: { full_name?: string; timezone?: string; phone_e164?: string | null }): Promise<User> {
    return request<User>('/users/me', { method: 'PATCH', body: input })
  },

  createAgenda(input: AgendaCreateInput): Promise<Agenda> {
    return request<Agenda>('/agendas', { method: 'POST', body: input })
  },

  readAgenda(id: string): Promise<Agenda> {
    return request<Agenda>(`/agendas/${id}`)
  },

  generate(id: string): Promise<GenerateResult> {
    return request<GenerateResult>(`/agendas/${id}/generate`, { method: 'POST' })
  },

  draft(id: string, signal?: AbortSignal): Promise<Draft> {
    return request<Draft>(`/agendas/${id}/draft`, { signal })
  },

  answer(id: string, answers: Record<string, string>): Promise<GenerateResult> {
    return request<GenerateResult>(`/agendas/${id}/draft/answers`, { method: 'POST', body: { answers } })
  },

  approve(id: string): Promise<ApproveResult> {
    return request<ApproveResult>(`/agendas/${id}/approve`, { method: 'POST' })
  },

  regenerate(
    id: string,
    input: { scope: 'all' | 'day'; day_index?: number; instructions?: string },
  ): Promise<GenerateResult> {
    return request<GenerateResult>(`/agendas/${id}/regenerate`, { method: 'POST', body: input })
  },

  days(id: string): Promise<SubAgenda[]> {
    return request<SubAgenda[]>(`/agendas/${id}/days`)
  },

  day(id: string, dayIndex: number): Promise<DayDetail> {
    return request<DayDetail>(`/agendas/${id}/days/${dayIndex}`)
  },

  patchDay(
    id: string,
    dayIndex: number,
    input: {
      title?: string
      description?: string | null
      expected_outcome?: string | null
      expected_effort_minutes?: number | null
    },
  ): Promise<SubAgenda> {
    return request<SubAgenda>(`/agendas/${id}/days/${dayIndex}`, { method: 'PATCH', body: input })
  },

  addTodo(subAgendaId: string, input: { title: string; notes?: string | null }): Promise<Todo> {
    return request<Todo>(`/sub-agendas/${subAgendaId}/todos`, { method: 'POST', body: input })
  },

  patchTodo(todoId: string, input: { title?: string; notes?: string | null; position?: number }): Promise<Todo> {
    return request<Todo>(`/todos/${todoId}`, { method: 'PATCH', body: input })
  },

  deleteTodo(todoId: string): Promise<{ detail: string }> {
    return request<{ detail: string }>(`/todos/${todoId}`, { method: 'DELETE' })
  },
}

export function isRateLimited(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 429 || error.code === 'RATE_LIMITED')
}
