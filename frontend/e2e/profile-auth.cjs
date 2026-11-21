// Owner sign-in confidence test against the real FastAPI app and built SPA.
// Both run on an OS-assigned loopback port with empty, temporary app data.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { once } = require('node:events')
const { setTimeout: delay } = require('node:timers/promises')
const { chromium } = require('playwright')

const root = path.resolve(__dirname, '../..')
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const credentials = { username: 'owner', password: 'disposable confidence-test passphrase' }
const csrf = { 'X-SongMirror-Request': '1' }
const localEnv = new Set(['PATH', 'SYSTEMROOT', 'HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR', 'WINDIR'])

async function main() {
  await fs.access(python)
  await fs.access(path.join(root, 'frontend/dist/index.html'))
  const tempRoot = await fs.realpath(os.tmpdir())
  const data = await fs.mkdtemp(path.join(tempRoot, 'songmirror-owner-e2e-'))
  let server, browser

  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return
    const exited = once(server, 'exit')
    server.kill()
    await exited
  }

  async function start(port = '0') {
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => localEnv.has(key.toUpperCase())))
    server = spawn(python, [
      '-m', 'uvicorn', 'songmirror.web:app', '--host', '127.0.0.1', '--port', port,
      '--forwarded-allow-ips', '127.0.0.1', '--no-access-log', '--no-use-colors',
    ], {
      cwd: root, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'],
      env: { ...env, PYTHON_DOTENV_DISABLED: '1', SONGMIRROR_DATA_DIR: data,
        SONGMIRROR_AUTH_USERNAME: '', SONGMIRROR_AUTH_PASSWORD: '' },
    })
    let log = ''
    let startupError
    server.once('error', (error) => { startupError = error })
    server.stderr.setEncoding('utf8')
    server.stderr.on('data', (chunk) => { log += chunk })
    for (let attempt = 0; attempt < 100; attempt += 1) {
      if (startupError) throw startupError
      if (server.exitCode !== null) break
      const base = log.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1]
      if (base) return { base, code: log.match(/SongMirror owner setup code: ([\w-]{32})/)?.[1] }
      await delay(100)
    }
    const diagnostic = log.replace(/(SongMirror owner setup code: )[^\r\n]+/g, '$1[redacted]').trim()
    throw new Error(`The isolated SongMirror server did not start\n${diagnostic}`)
  }

  try {
    const { base, code } = await start()
    assert.equal(code?.length, 32, 'An unconfigured instance logs an operator setup code')
    console.log(`Owner sign-in confidence test running at ${base}`)
    browser = await chromium.launch()
    const owner = await browser.newContext({ locale: 'en-US', viewport: { width: 375, height: 812 } })
    const guest = await browser.newContext({ locale: 'en-US' })
    const setupUrl = base + '/api/auth/setup'
    const settingsUrl = base + '/settings?section=general'
    const settingsApi = base + '/api/settings'
    const setupData = { ...credentials, setup_code: code }
    const guestStatus = await guest.request.get(base + '/api/auth/session')
    assert.deepEqual(await guestStatus.json(), { enabled: false, authenticated: false })
    assert.equal((await (await guest.request.get(settingsUrl)).text()).includes(code), false)
    assert.equal((await guest.request.get(settingsApi)).status(), 200)
    assert.equal((await guest.request.get(base + '/docs')).status(), 404)
    assert.equal((await guest.request.post(setupUrl, { data: setupData })).status(), 403)
    assert.equal((await guest.request.post(setupUrl, { headers: csrf, data: credentials })).status(), 403)
    assert.equal((await guest.request.post(setupUrl, {
      headers: { ...csrf, Origin: 'null', 'Sec-Fetch-Site': 'cross-site' }, data: setupData,
    })).status(), 403)
    assert.equal((await guest.request.post(setupUrl, { headers: csrf, data: ' '.repeat(8193) })).status(), 413)

    const preSetupFeed = await openFeed(base)
    const page = await owner.newPage()
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto(settingsUrl)
    const name = page.getByLabel('Display name')
    await name.fill('Unsaved display name')
    await page.evaluate(() => {
      localStorage.setItem('songmirror-cache-v2:settings', '{}')
      localStorage.setItem('songmirror-live-feed-v1', '[]')
      localStorage.setItem('songmirror-dismissed-alerts', '[]')
    })
    await page.getByRole('button', { name: 'Set up sign-in' }).click()
    const dialog = page.getByRole('dialog', { name: 'Set up sign-in' })
    await dialog.locator('input[name="setup_code"]').fill('incorrect')
    await dialog.locator('input[name="username"]').fill(credentials.username)
    await dialog.locator('input[name="password"]').fill(credentials.password)
    await dialog.locator('input[name="confirm"]').fill('different passphrase')
    const submit = dialog.getByRole('button', { name: 'Enable sign-in' })
    await submit.click()
    await dialog.getByText('Passwords do not match.').waitFor()
    await dialog.locator('input[name="confirm"]').fill(credentials.password)
    await submit.click()
    await dialog.getByText('The setup code is incorrect or expired.').waitFor()
    await dialog.locator('input[name="setup_code"]').fill(code)
    await submit.click()
    await page.getByText('Sign-in is required to access this instance.').waitFor()
    assert.equal(await name.inputValue(), 'Unsaved display name')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    assert.equal(await page.evaluate(() => Object.keys(localStorage).some((key) =>
      /^songmirror-(?:cache-v|live-feed-v|dismissed-alerts)/.test(key))), false)
    assert.deepEqual(await (await owner.request.get(base + '/api/auth/session')).json(), {
      enabled: true, authenticated: true,
    })
    await waitForFeedToClose(preSetupFeed)
    console.log('PASS: operator setup, validation, Settings draft, and immediate access enforcement')

    const record = await fs.readFile(path.join(data, 'owner-auth/credentials.json'), 'utf8')
    const savedOwner = JSON.parse(record)
    assert.equal(savedOwner.username, credentials.username)
    assert.match(savedOwner.password_hash, /^[a-f\d]{128}$/)
    assert.equal(record.includes(credentials.password) || record.includes(code), false)
    assert.equal((await guest.request.post(setupUrl, { headers: csrf, data: setupData })).status(), 409)
    for (const route of [
      '/api/settings', '/api/accounts', '/api/playlists/spotify/export?format=json',
      '/api/syncs', '/api/transfers/history', '/api/playlist-backups/spotify/latest',
      '/api/folders', '/api/imports', '/api/resolve-cache', '/events',
      '/oauth/spotify/start', '/oauth/spotify/callback', '/openapi.json', '/docs',
    ]) {
      const rejected = await guest.request.get(base + route)
      assert.equal(rejected.status(), 401, route)
      assert.equal(rejected.headers()['cache-control'], 'no-store', route)
      assert.equal(rejected.headers()['x-frame-options'], 'DENY', route)
    }
    assert.equal((await guest.request.get(base + '/health')).status(), 200)
    assert.equal((await owner.request.get(base + '/docs')).status(), 404)
    assert.equal((await owner.request.get(base + '/openapi.json')).status(), 200)
    assert.equal((await guest.request.put(settingsApi, { headers: csrf, data: { DISPLAY_NAME: 'Guest' } })).status(), 401)
    assert.equal((await owner.request.put(settingsApi, { data: { DISPLAY_NAME: 'Missing header' } })).status(), 403)
    assert.equal((await owner.request.put(settingsApi, {
      headers: { ...csrf, Origin: 'http://localhost:9999', 'Sec-Fetch-Site': 'cross-site' },
      data: { DISPLAY_NAME: 'Foreign origin' },
    })).status(), 403)
    assert.equal((await owner.request.put(settingsApi, {
      headers: { ...csrf, Origin: base, 'Sec-Fetch-Site': 'same-origin' }, data: { DISPLAY_NAME: 'Owner' },
    })).status(), 200)
    const proxyLogin = await fetch(base + '/api/auth/login', {
      method: 'POST', headers: { ...csrf, 'Content-Type': 'application/json', 'X-Forwarded-Proto': 'https' },
      body: JSON.stringify(credentials),
    })
    const proxyCookie = proxyLogin.headers.get('set-cookie')
    assert.equal(proxyLogin.status, 204)
    for (const attribute of [/; Secure/i, /; HttpOnly/i, /; SameSite=lax/i, /; Path=\//i]) {
      assert.match(proxyCookie, attribute)
    }
    console.log('PASS: protected reads and writes, origin checks, response headers, and HTTPS cookie attributes')

    const cookie = (await owner.cookies()).find((item) => item.name === 'songmirror_session')
    assert.equal(cookie.httpOnly, true)
    assert.equal(await page.evaluate(() => document.cookie.includes('songmirror_session')), false)
    const cookieHeader = `songmirror_session=${cookie.value}`
    const signedInFeed = await openFeed(base, { Cookie: cookieHeader })
    await page.getByRole('button', { name: 'Open menu' }).click()
    await page.getByRole('button', { name: 'Sign out' }).click()
    const signIn = page.getByRole('heading', { name: 'Sign in', exact: true })
    await signIn.waitFor()
    assert.equal((await fetch(settingsApi, { headers: { Cookie: cookieHeader } })).status, 401)
    await waitForFeedToClose(signedInFeed)
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const rejected = await guest.request.post(base + '/api/auth/login', {
        headers: csrf, data: { ...credentials, password: 'incorrect passphrase' },
      })
      assert.equal(rejected.status(), 401)
    }
    const throttled = await guest.request.post(base + '/api/auth/login', { headers: csrf, data: credentials })
    assert.equal(throttled.status(), 429)
    assert.ok(Number(throttled.headers()['retry-after']) > 0)

    await stop()
    const restarted = await start(new URL(base).port)
    assert.equal(restarted.base, base)
    assert.equal(Boolean(restarted.code), false)
    assert.equal((await guest.request.get(settingsApi)).status(), 401)
    assert.equal((await fetch(settingsApi, { headers: { Cookie: cookieHeader } })).status, 401)
    await page.reload()
    await signIn.waitFor()
    await page.locator('input[name="username"]').fill(credentials.username)
    await page.locator('input[name="password"]').fill(credentials.password)
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.getByText('Sign-in is required to access this instance.').waitFor()
    assert.deepEqual(errors, [])
    console.log('PASS: sign-out revocation, live feed closure, login throttling, and sign-in after restart')
  } finally {
    if (browser) await browser.close()
    await stop()
    assert.equal(path.dirname(data), tempRoot)
    assert.ok(path.basename(data).startsWith('songmirror-owner-e2e-'))
    await fs.rm(data, { recursive: true, force: true })
  }
}

async function openFeed(base, headers) {
  const response = await fetch(base + '/events', { headers, signal: AbortSignal.timeout(15_000) })
  assert.equal(response.status, 200)
  const reader = response.body.getReader()
  assert.match(Buffer.from((await reader.read()).value).toString(), /: connected/)
  return reader
}

async function waitForFeedToClose(reader) {
  while (!(await reader.read()).done) {
    // A heartbeat queued before the session changed may still be in transit.
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1 })
