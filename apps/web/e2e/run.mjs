#!/usr/bin/env node
/**
 * Web smoke harness orchestrator.
 *
 *   node e2e/run.mjs [all|capture|today|plans|planning|failed|focus|snap]
 *
 * With no arguments this boots a throwaway API (on its own SQLite file) plus
 * Vite, drives the first-agenda flow in headless Chrome, writes the review
 * screenshots and HTML snapshots, then tears everything down. To attach to
 * servers you already run, export E2E_NO_SERVER=1 (you then own autostart).
 */
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'

import { API_DIR, ROOT, WEB_DIR, config, createApi, createChecks, launchBrowser, sleep } from './harness.mjs'

import * as capture from './capture.mjs'
import * as planning from './planning.mjs'
import * as failed from './failed.mjs'
import * as focus from './focus.mjs'
import * as plans from './plans.mjs'
import * as snap from './snap.mjs'
import * as today from './today.mjs'

const PHASES = { capture, planning, failed, focus, snap, plans, today }
// Planning runs last: it is the only phase that needs AGENT_AUTOSTART=false.
const ORDER = ['capture', 'today', 'plans', 'snap', 'focus', 'failed', 'planning']

const apiUrl = new URL(config.api)
const apiHost = apiUrl.hostname
const apiPort = apiUrl.port || '8000'
const webPort = new URL(config.web).port || '5173'

const children = new Set()
let apiProcess = null
let apiAutostart = null
let viteProcess = null
let stopping = false

let apiPython = null

/** The inherited PYTHONPATH, minus the old vendored deps. */
function inheritedPythonPath() {
  const pylibs = path.join(API_DIR, '.pylibs')
  return (process.env.PYTHONPATH ?? '')
    .split(path.delimiter)
    .filter((entry) => entry && path.resolve(entry) !== pylibs)
    .join(path.delimiter)
}

function canImport(python) {
  const env = { ...process.env }
  const cleaned = inheritedPythonPath()
  if (cleaned) env.PYTHONPATH = cleaned
  else delete env.PYTHONPATH
  return spawnSync(python, ['-c', 'import uvicorn, pydantic_core'], { env, stdio: 'ignore' }).status === 0
}

/**
 * The first interpreter that can import the API deps. An explicit
 * E2E_PYTHON/DEV_PYTHON wins; otherwise the shared bootstrap script creates
 * (or repairs) apps/api/.venv.
 */
function resolvePython() {
  if (apiPython) return apiPython

  const e2ePython = process.env.E2E_PYTHON
  if (e2ePython) {
    if (!canImport(e2ePython)) {
      throw new Error(
        `E2E_PYTHON=${e2ePython} cannot import uvicorn/pydantic_core. ` +
          'Point it at a ready interpreter or unset it.',
      )
    }
    apiPython = e2ePython
    return e2ePython
  }

  const devPython = process.env.DEV_PYTHON
  if (devPython) {
    if (canImport(devPython)) {
      apiPython = devPython
      return devPython
    }
    console.warn(
      `[e2e] DEV_PYTHON=${devPython} cannot import uvicorn/pydantic_core; using the repo venv.`,
    )
  }

  const ensure = path.join(WEB_DIR, 'scripts', 'ensure-api-venv.sh')
  const boot = spawnSync('bash', [ensure], { encoding: 'utf8' })
  if (boot.status === 0) {
    const python = boot.stdout.trim().split(/\r?\n/).pop()
    if (python && canImport(python)) {
      apiPython = python
      return python
    }
  } else if (boot.stderr) {
    process.stderr.write(boot.stderr)
  }

  for (const python of [
    path.join(API_DIR, '.venv', 'bin', 'python'),
    path.join(ROOT, '.venv', 'bin', 'python'),
    'python3',
  ]) {
    if (canImport(python)) {
      apiPython = python
      return python
    }
  }

  throw new Error(
    'No Python interpreter can import the API dependencies. Run `npm run dev:all` once ' +
      'to create apps/api/.venv, or set E2E_PYTHON.',
  )
}

async function isUp(url) {
  try {
    const response = await fetch(url, { redirect: 'manual' })
    return response.ok
  } catch {
    return false
  }
}

async function waitFor(url, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await isUp(url)) return
    await sleep(250)
  }
  throw new Error(`${label} did not answer at ${url} within ${timeoutMs}ms`)
}

async function waitForDown(url, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (!(await isUp(url))) return
    await sleep(200)
  }
  throw new Error(`${label} at ${url} did not shut down within ${timeoutMs}ms`)
}

function track(child, label) {
  children.add(child)
  child.on('exit', (code, signal) => {
    children.delete(child)
    if (!stopping && code !== 0 && signal === null) {
      console.error(`[e2e] ${label} exited early (code ${code})`)
    }
  })
  return child
}

function stopProcess(child) {
  if (child && !child.killed) {
    try {
      child.kill('SIGTERM')
    } catch {
      /* already gone */
    }
  }
}

function startApi(autostart) {
  const python = resolvePython()
  const env = {
    ...process.env,
    DATABASE_URL: `sqlite+aiosqlite:///${config.db}`,
    AGENT_AUTOSTART: autostart ? 'true' : 'false',
    SCHEDULER_ENABLED: 'false',
    ENVIRONMENT: 'local',
    // Quiet the "HMAC key is too short" warning the dev default triggers.
    JWT_SECRET: process.env.JWT_SECRET ?? 'agentda-e2e-harness-signing-key-32b+',
  }
  const pythonPathValue = inheritedPythonPath()
  if (pythonPathValue) env.PYTHONPATH = pythonPathValue
  else delete env.PYTHONPATH
  return track(
    spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', apiHost, '--port', apiPort, '--log-level', 'warning'], {
      cwd: API_DIR,
      env,
      stdio: ['ignore', 'ignore', 'inherit'],
    }),
    'API',
  )
}

function startVite() {
  return track(
    spawn(path.join(WEB_DIR, 'node_modules', '.bin', 'vite'), ['--port', webPort, '--strictPort'], {
      cwd: WEB_DIR,
      stdio: ['ignore', 'ignore', 'inherit'],
    }),
    'Vite',
  )
}

async function ensureApi(autostart) {
  const health = `${config.apiOrigin}/healthz`
  if (!config.manageServers) {
    await waitFor(health, 5_000, 'API')
    return
  }
  if (apiProcess && apiAutostart === autostart) return
  if (apiProcess) {
    stopProcess(apiProcess)
    apiProcess = null
    apiAutostart = null
    await waitForDown(health, 10_000, 'API')
  } else if (await isUp(health)) {
    throw new Error(
      `Something is already listening at ${config.apiOrigin}. Stop it, or attach to it with ` +
        `E2E_NO_SERVER=1 (then you own AGENT_AUTOSTART).`,
    )
  }
  console.log(`[e2e] API  -> ${config.apiOrigin} (autostart=${autostart})`)
  apiProcess = startApi(autostart)
  apiAutostart = autostart
  await waitFor(health, 30_000, 'API')
}

async function ensureVite() {
  if (await isUp(config.web)) {
    console.log(`[e2e] web  -> ${config.web} (reusing a running server)`)
    return
  }
  if (!config.manageServers) {
    throw new Error(`No server at ${config.web}. Start one, or drop E2E_NO_SERVER.`)
  }
  console.log(`[e2e] web  -> ${config.web} (starting)`)
  viteProcess = startVite()
  await waitFor(config.web, 30_000, 'Vite')
}

async function cleanup() {
  if (stopping) return
  stopping = true
  stopProcess(viteProcess)
  stopProcess(apiProcess)
  await sleep(300)
  for (const child of children) stopProcess(child)
  if (!config.keepDb) await fs.rm(config.db, { force: true }).catch(() => {})
}

async function main() {
  const requested = process.argv[2] ?? 'all'
  const names = requested === 'all' ? ORDER : [requested]
  for (const name of names) {
    if (!PHASES[name]) {
      throw new Error(`Unknown phase "${name}". Use one of: all, ${Object.keys(PHASES).join(', ')}`)
    }
  }

  await fs.mkdir(config.out, { recursive: true })
  await fs.mkdir(config.snap, { recursive: true })

  console.log(`[e2e] phases: ${names.join(', ')}`)
  console.log(`[e2e] shots:  ${config.out}`)
  console.log(`[e2e] snaps:  ${config.snap}`)
  if (config.manageServers) console.log(`[e2e] db:     ${config.db}`)

  process.on('SIGINT', async () => {
    await cleanup()
    process.exit(130)
  })
  process.on('SIGTERM', async () => {
    await cleanup()
    process.exit(143)
  })

  let passed = true
  let browser = null

  try {
    for (const name of names) {
      const phase = PHASES[name]
      await ensureApi(phase.autostart)
      await ensureVite()

      console.log(`\n[e2e] ${name}`)
      const checks = createChecks()
      if (!browser) browser = await launchBrowser()
      await phase.run({ browser, api: createApi(), checks })
      passed = checks.report(name) && passed
    }
  } finally {
    if (browser) await browser.close().catch(() => {})
    await cleanup()
  }

  console.log(`\n[e2e] ${passed ? 'PASS' : 'FAIL'}`)
  process.exit(passed ? 0 : 1)
}

main().catch(async (error) => {
  console.error(`\n[e2e] ${error?.stack ?? error}`)
  await cleanup()
  process.exit(1)
})
