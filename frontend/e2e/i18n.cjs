// Localization behavior against the production SPA. Every API request is
// intercepted; changing a language or saving the fixture cannot reach a service.
const assert = require('node:assert/strict')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const LANGUAGES = ['en', 'ar', 'tr', 'es', 'zh', 'fr', 'pt', 'de', 'ja', 'hi', 'bn', 'id', 'ko', 'it', 'vi']
const STORAGE_KEY = 'songmirror.language'
const BACKUP_DATE = '2026-09-01T17:23:00Z'
const NEXT_RUN = Math.floor(Date.now() / 1000) + 5 * 3600 + 12 * 60
const CATALOGS = Object.fromEntries(LANGUAGES.map(code => [code, require(`../src/i18n/locales/${code}.json`)]))

function message(code, key, values = {}, count) {
  const pluralKey = count === undefined ? key : `${key}_${new Intl.PluralRules(code).select(count)}`
  const template = CATALOGS[code][pluralKey] ?? CATALOGS[code][key]
  assert.equal(typeof template, 'string', `Missing ${code} translation: ${pluralKey}`)
  return template.replace(/{{\s*([^}]+?)\s*}}/g, (_, name) => {
    assert.ok(Object.hasOwn(values, name), `Missing interpolation ${name}`)
    return String(values[name])
  })
}

function normalized(value) {
  return value.replace(/\s+/g, ' ').trim()
}

async function screenshot(page, name) {
  if (process.env.CI) return
  const shots = path.resolve(__dirname, '../../.unlazy/i18n/format')
  fs.mkdirSync(shots, { recursive: true })
  await page.screenshot({ path: path.join(shots, `${name}.png`), fullPage: true })
}

async function installMocks(page, { unavailable = false } = {}) {
  const state = { settings: { DISPLAY_NAME: 'Maya', DOWNLOAD_DIR: '/music', LOCAL_MIRROR_FORMAT: 'mp3' }, mutations: [], unexpected: [] }
  const account = { id: 'spotify', provider: 'spotify', label: '', name: 'Spotify', state: 'connected', fields: [], transferable: true }
  const playlists = [
    { id: 'zero', name: 'Empty / قائمة', count: 0, image: '', external_url: '' },
    { id: 'one', name: 'One / 一', count: 1, image: '', external_url: '' },
    { id: 'many', name: 'Large library / المكتبة', count: 1234, image: '', external_url: '' },
    { id: 'unknown', name: 'Unknown count', count: null, image: '', external_url: '' },
    { id: 'inspect', name: 'Road Trip / رحلة', count: 2, image: '', external_url: '' },
    { id: 'few', name: 'Small mix', count: 3, image: '', external_url: '' },
    { id: 'hundred', name: 'Album archive', count: 100, image: '', external_url: '' },
  ]
  await page.route('**/api/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()
    if (method !== 'GET') state.mutations.push({ path: url.pathname, method, body: request.postDataJSON() })
    if (unavailable && url.pathname === '/api/settings') {
      return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Fixture backend unavailable' }) })
    }
    let body
    if (url.pathname === '/api/settings' && method === 'PUT') {
      Object.assign(state.settings, request.postDataJSON())
      body = { ok: true }
    } else if (url.pathname === '/api/settings' && method === 'GET') body = state.settings
    else if (url.pathname === '/api/accounts' && method === 'GET') body = [account]
    else if (url.pathname === '/api/sync/status' && method === 'GET') {
      body = { running: false, mode: null, running_job: null, master: true, scheduled: true, next_run_at: NEXT_RUN, last: null, jobs: [] }
    } else if (['/api/syncs', '/api/transfers', '/api/links', '/api/resolve-cache'].includes(url.pathname) && method === 'GET') body = []
    else if (url.pathname === '/api/playlists' && method === 'GET') {
      assert.equal(url.searchParams.get('provider'), 'spotify', 'Provider API identifiers must stay unchanged')
      body = playlists
    } else if (url.pathname === '/api/playlists/spotify/inspect' && method === 'GET') {
      body = { ...playlists[4], provider: 'spotify', description: 'User-authored playlist description', editable: false, complete: true, tracks: [
        { position: 0, id: 'track-1', isrc: 'GB0000000001', occurrence_id: '', name: 'Original Track / أغنية', artist: 'Original Artist', album: 'Album', duration_ms: 125000, image: '', added_at: BACKUP_DATE, external_url: '' },
        { position: 1, id: 'track-2', isrc: '', occurrence_id: '', name: 'Unknown duration', artist: 'Original Artist', album: null, duration_ms: null, image: '', added_at: '', external_url: '' },
      ] }
    } else if (url.pathname === '/api/playlist-backups' && method === 'GET') {
      body = [{ account_id: 'spotify', provider: 'spotify', provider_name: 'Spotify', account_name: 'Spotify', enabled: true, interval: '24h', format: 'json', retention: 30, running: false, next_run_at: NEXT_RUN, snapshot_count: 1, storage_path: '/data/playlist_backups/spotify', storage_dir: '', default_storage_dir: '/data/playlist_backups', last_failure: null,
        last_success: { at: BACKUP_DATE, filename: 'songmirror-spotify-playlists.json', format: 'json', playlist_count: 1, track_count: 1234, pruned: 0 } }]
    } else if (url.pathname === '/api/folders/config' && method === 'GET') body = { scope: 'container', mounts: [], locations: [{ name: 'App data', path: '/data' }] }
    else {
      state.unexpected.push(`${method} ${url.pathname}`)
      return route.fulfill({ status: 501, contentType: 'application/json', body: JSON.stringify({ detail: 'Unexpected fixture request' }) })
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
  return state
}

async function waitForLanguage(page, code) {
  await page.waitForFunction(language => document.documentElement.lang === language, code)
  assert.equal(await page.locator('html').getAttribute('dir'), code === 'ar' ? 'rtl' : 'ltr')
}

async function chooseLanguage(page, code) {
  await page.getByTestId('language-select').selectOption(code)
  await waitForLanguage(page, code)
  await page.waitForFunction(value => document.querySelector('[data-testid="language-select"]').value === value, code)
}

async function checkOverflow(page, label) {
  const metrics = await page.evaluate(() => {
    const width = document.documentElement.clientWidth
    const outside = [...document.querySelectorAll('main a, main button, main input, main select, main h1, [role="dialog"]')]
      .filter(element => {
        const rect = element.getBoundingClientRect()
        return rect.width > 0 && rect.height > 0 && (rect.left < -1 || rect.right > width + 1)
      })
      .map(element => `${element.tagName}: ${element.textContent?.trim().slice(0, 70)}`)
    return { width, documentWidth: document.documentElement.scrollWidth, bodyWidth: document.body.scrollWidth, outside }
  })
  assert.ok(metrics.documentWidth <= metrics.width + 1 && metrics.bodyWidth <= metrics.width + 1, `${label}: horizontal page overflow ${JSON.stringify(metrics)}`)
  assert.deepEqual(metrics.outside, [], `${label}: controls must fit without relying on overflow clipping`)
}

async function checkSwitches(page, label) {
  await assert.doesNotReject(() => page.waitForFunction(() => {
    const tracks = [...document.querySelectorAll('[role="switch"] > span[aria-hidden="true"]')]
    return tracks.length > 0 && tracks.every(track => {
      const knob = track.firstElementChild
      if (!knob) return false
      const outer = track.getBoundingClientRect()
      const inner = knob.getBoundingClientRect()
      const checked = track.parentElement.getAttribute('aria-checked') === 'true'
      const rtl = getComputedStyle(track).direction === 'rtl'
      const pointsRight = inner.left + inner.width / 2 > outer.left + outer.width / 2
      return inner.left >= outer.left && inner.right <= outer.right && pointsRight === (checked !== rtl)
    })
  }, null, { timeout: 2000 }), `${label}: switch thumbs must stay inside their tracks and reflect the reading direction`)
}

async function newFixture(browser, { locale = 'en-US', languages, stored, unavailable = false, storageDenied = false } = {}) {
  const context = await browser.newContext({ locale, timezoneId: 'UTC', viewport: { width: 1280, height: 900 } })
  if (languages || stored !== undefined) {
    await context.addInitScript(({ languages, stored, key }) => {
      if (languages) Object.defineProperty(navigator, 'languages', { configurable: true, value: languages })
      // Seed once so a subsequent reload can test changes made by the app.
      if (stored !== undefined && !sessionStorage.getItem('i18n-fixture-seeded')) {
        localStorage.setItem(key, stored)
        sessionStorage.setItem('i18n-fixture-seeded', '1')
      }
    }, { languages, stored, key: STORAGE_KEY })
  }
  if (storageDenied) {
    await context.addInitScript(key => {
      for (const method of ['getItem', 'setItem', 'removeItem']) {
        const original = Storage.prototype[method]
        Storage.prototype[method] = function (name, ...args) {
          if (name === key) throw new DOMException('Storage is unavailable', 'SecurityError')
          return original.call(this, name, ...args)
        }
      }
    }, STORAGE_KEY)
  }
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const state = await installMocks(page, { unavailable })
  return { context, page, state, errors }
}

async function main() {
  const dist = path.resolve(__dirname, '../dist')
  assert.ok(fs.existsSync(path.join(dist, 'index.html')), 'Build the frontend before running localization checks')
  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname
    if (pathname.startsWith('/api/') || pathname === '/events') {
      response.writeHead(500).end('API request escaped the browser mocks')
      return
    }
    const asset = path.resolve(dist, '.' + pathname)
    const file = asset.startsWith(dist + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile() ? asset : path.join(dist, 'index.html')
    const mime = { '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.html': 'text/html', '.woff2': 'font/woff2', '.png': 'image/png', '.svg': 'image/svg+xml' }
    response.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(response)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  let browser
  try {
    browser = await chromium.launch({ headless: true })
    const fixture = await newFixture(browser, { locale: 'es-MX', languages: ['es-MX', 'en-US'] })
    const { page, state, errors } = fixture
    await page.goto(base + '/settings')
    await waitForLanguage(page, 'es')
    await page.getByRole('heading', { name: message('es', 'Settings'), exact: true }).waitFor()
    const select = page.getByTestId('language-select')
    assert.equal(await select.inputValue(), 'system')
    assert.deepEqual(await select.locator('option').evaluateAll(options => options.map(option => option.value)), ['system', ...LANGUAGES])
    assert.equal(await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY), null, 'Browser detection must not save an override')
    const draft = 'Maya / মায়া / مايا <&>'
    const displayName = page.locator('form input').first()
    await displayName.fill(draft)
    await page.locator('main').evaluate(main => {
      const control = document.createElement('button')
      control.id = 'overflow-oracle-control'
      control.style.cssText = 'position:fixed;left:-200px;width:100px;height:20px'
      main.appendChild(control)
    })
    await assert.rejects(() => checkOverflow(page, 'Overflow oracle control'), /overflow|controls must fit/, 'The overflow check must detect a clipped control')
    await page.locator('#overflow-oracle-control').evaluate(control => control.remove())
    const documentToken = await page.evaluate(() => (window.localizationDocumentToken = Math.random()))
    for (const code of LANGUAGES) {
      await chooseLanguage(page, code)
      await page.getByRole('heading', { name: message(code, 'Settings'), exact: true }).waitFor()
      assert.equal(await page.getByRole('combobox', { name: message(code, 'Language'), exact: true }).count(), 1, `${code}: language selector must have a translated accessible name`)
      assert.equal(await displayName.inputValue(), draft, `${code}: unsaved form state must survive a language switch`)
      assert.equal(await page.evaluate(() => window.localizationDocumentToken), documentToken, `${code}: switching must not reload the document`)
      assert.equal(await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY), code)
      await checkSwitches(page, `${code} Settings`)
      await checkOverflow(page, `${code} desktop Settings`)
      if (code === 'ar') {
        const sidebar = await page.locator('aside').boundingBox()
        const main = await page.locator('main').boundingBox()
        assert.ok(sidebar.x > main.x, 'Arabic desktop navigation must be on the right')
        await page.getByRole('switch').click()
        await checkSwitches(page, 'Arabic Settings, switch off')
        await page.getByRole('switch').click()
        await checkSwitches(page, 'Arabic Settings, switch on')
        await screenshot(page, 'arabic-settings-desktop')
      }
      await page.setViewportSize({ width: 375, height: 900 })
      await checkOverflow(page, `${code} mobile Settings`)
      if (code === 'ar') {
        const brand = await page.locator('header a').first().boundingBox()
        const menu = await page.locator('header button').first().boundingBox()
        assert.ok(brand.x > menu.x, 'Arabic mobile navigation must start on the right')
        await screenshot(page, 'arabic-settings-mobile')
      }
      if (code === 'bn') await screenshot(page, 'bengali-settings-mobile')
      await page.setViewportSize({ width: 1280, height: 900 })
    }
    assert.equal(state.mutations.length, 0, 'Language changes must remain browser-local')
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/settings') && response.request().method() === 'PUT'),
      page.locator('form button[type="submit"]').click(),
    ])
    assert.deepEqual(state.mutations, [{ path: '/api/settings', method: 'PUT', body: { DISPLAY_NAME: draft } }], 'Localization must preserve API keys and user-authored values')
    await chooseLanguage(page, 'ar')
    await page.reload()
    await waitForLanguage(page, 'ar')
    assert.equal(await select.inputValue(), 'ar', 'Manual preference must survive reload and override browser Spanish')
    await page.evaluate(() => {
      Object.defineProperty(navigator, 'languages', { configurable: true, value: ['de-DE'] })
      window.dispatchEvent(new Event('languagechange'))
    })
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    await waitForLanguage(page, 'ar')
    await select.selectOption('system')
    await waitForLanguage(page, 'de')
    assert.equal(await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY), null, 'Automatic mode must remove the manual preference')
    assert.deepEqual(errors, [])
    assert.deepEqual(state.unexpected, [])
    await fixture.context.close()

    for (const scenario of [
      { locale: 'fr-CA', languages: ['xx-ZZ', 'fr-CA'], expected: 'fr' },
      { locale: 'en-US', languages: ['zh-Hant-TW'], expected: 'zh' },
      { locale: 'en-US', languages: ['xx-ZZ', 'pl-PL'], expected: 'en' },
      { locale: 'de-DE', stored: 'ja-JP', expected: 'ja', preference: 'ja' },
      { locale: 'fr-CA', stored: 'unsupported', expected: 'fr' },
      { locale: 'en-US', stored: 'system', expected: 'en' },
      { locale: 'en-US', unavailable: true, expected: 'en' },
    ]) {
      const current = await newFixture(browser, scenario)
      await current.page.goto(base + '/settings')
      await waitForLanguage(current.page, scenario.expected)
      await current.page.getByTestId('language-select').waitFor()
      assert.equal(await current.page.getByTestId('language-select').inputValue(), scenario.preference ?? 'system')
      await chooseLanguage(current.page, 'tr')
      await current.page.getByRole('heading', { name: message('tr', 'Settings'), exact: true }).waitFor()
      assert.equal(current.state.mutations.length, 0)
      assert.deepEqual(current.state.unexpected, [])
      assert.deepEqual(current.errors, [])
      await current.context.close()
    }

    {
      const current = await newFixture(browser, { locale: 'es-MX', storageDenied: true })
      await current.page.goto(base + '/settings')
      await waitForLanguage(current.page, 'es')
      await chooseLanguage(current.page, 'ar')
      await current.page.getByRole('heading', { name: message('ar', 'Settings'), exact: true }).waitFor()
      await current.page.reload()
      await waitForLanguage(current.page, 'es')
      assert.equal(await current.page.getByTestId('language-select').inputValue(), 'system', 'Denied storage must still allow browser detection and in-session switches')
      assert.deepEqual(current.errors, [])
      assert.equal(current.state.mutations.length, 0)
      await current.context.close()
    }

    {
      const current = await newFixture(browser, { stored: 'es' })
      let requests = 0
      await current.page.route('**/assets/es-*', route => {
        requests++
        return requests === 1
          ? route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Fixture locale temporarily absent"}' })
          : route.continue()
      })
      await current.page.goto(base + '/settings')
      await current.page.getByRole('heading', { name: message('en', 'Settings'), exact: true }).waitFor()
      await waitForLanguage(current.page, 'en')
      assert.equal(requests, 1, 'The startup fallback must be tested against an actual failed locale request')
      assert.equal(await current.page.evaluate(key => localStorage.getItem(key), STORAGE_KEY), 'es', 'A missing startup catalog must retain the preference for retry')
      const displayName = current.page.locator('form input').first()
      await displayName.fill('Retry keeps this draft')
      await chooseLanguage(current.page, 'en')
      await chooseLanguage(current.page, 'es')
      await current.page.getByRole('heading', { name: message('es', 'Settings'), exact: true }).waitFor()
      assert.ok(requests >= 2, 'An explicit retry must fetch the failed catalog again')
      assert.equal(await displayName.inputValue(), 'Retry keeps this draft')
      assert.deepEqual(current.errors, [])
      assert.equal(current.state.mutations.length, 0)
      await current.context.close()
    }

    {
      const current = await newFixture(browser)
      await current.page.goto(base + '/settings')
      await current.page.getByTestId('language-select').waitFor()
      const displayName = current.page.locator('form input').first()
      await displayName.fill('Latest language wins')
      let releaseSlow
      const slowGate = new Promise(resolve => { releaseSlow = resolve })
      await current.page.route('**/assets/fr-*', async route => {
        await slowGate
        await route.continue()
      })
      try {
        const slowRequested = current.page.waitForRequest('**/assets/fr-*')
        await current.page.getByTestId('language-select').selectOption('fr')
        await slowRequested
        await chooseLanguage(current.page, 'ja')
        const slowResponse = current.page.waitForResponse('**/assets/fr-*')
        releaseSlow()
        await (await slowResponse).finished()
        await current.page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        await waitForLanguage(current.page, 'ja')
        assert.equal(await current.page.getByTestId('language-select').inputValue(), 'ja', 'A slower earlier request must not replace the latest selection')
        assert.equal(await current.page.evaluate(key => localStorage.getItem(key), STORAGE_KEY), 'ja')
        assert.equal(await displayName.inputValue(), 'Latest language wins')
        assert.deepEqual(current.errors, [])
        assert.equal(current.state.mutations.length, 0)
      } finally {
        releaseSlow()
        await current.context.close()
      }
    }

    // The browser stays en-US/UTC while each chosen locale controls clocks,
    // dates, digits, plural categories, and duration units in actual views.
    for (const code of ['en', 'de', 'ja', 'ar', 'bn']) {
      const current = await newFixture(browser, { stored: code })
      const { page } = current
      await page.goto(base + '/')
      await waitForLanguage(page, code)
      const clock = await page.evaluate(({ code, epoch }) => new Intl.DateTimeFormat(code, { hour: 'numeric', minute: '2-digit', timeZone: 'UTC' }).format(epoch * 1000), { code, epoch: NEXT_RUN })
      await page.getByText(clock, { exact: false }).first().waitFor()
      await page.goto(base + '/settings?section=backups')
      const date = await page.evaluate(({ code, value }) => new Intl.DateTimeFormat(code, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)), { code, value: BACKUP_DATE })
      await page.getByText(date, { exact: false }).first().waitFor()
      assert.equal(await page.locator('select').filter({ has: page.locator('option[value="24h"]') }).inputValue(), '24h', 'Translated interval labels must preserve backend syntax')
      await page.goto(base + '/playlists')
      for (const count of [0, 1, 2, 3, 100, 1234]) {
        const formattedCount = await page.evaluate(({ code, count }) => new Intl.NumberFormat(code).format(count), { code, count })
        const expected = message(code, '{{formattedCount}} track', { formattedCount }, count)
        await page.getByText(expected, { exact: true }).first().waitFor()
      }
      const unknown = page.getByRole('button').filter({ hasText: 'Unknown count' })
      await unknown.waitFor()
      assert.ok(!/null|NaN/.test(await unknown.innerText()), 'Unknown track counts must be omitted')
      await page.getByRole('button').filter({ hasText: 'Road Trip / رحلة' }).click()
      const dialog = page.getByRole('dialog')
      const durationRow = dialog.locator('ol > li').filter({ hasText: 'Original Track / أغنية' })
      await durationRow.scrollIntoViewIfNeeded()
      const duration = await page.evaluate(code => new Intl.NumberFormat(code, { style: 'unit', unit: 'minute', unitDisplay: 'narrow' }).format(2) + ' '
        + new Intl.NumberFormat(code, { style: 'unit', unit: 'second', unitDisplay: 'narrow', minimumIntegerDigits: 2 }).format(5), code)
      await durationRow.getByText(duration, { exact: true }).waitFor()
      assert.ok(normalized(await durationRow.innerText()).includes(normalized(duration)), `${code}: track duration must use the selected locale`)
      const missingDuration = dialog.locator('ol > li').filter({ hasText: 'Unknown duration' })
      await missingDuration.scrollIntoViewIfNeeded()
      await missingDuration.getByText('—', { exact: true }).waitFor()
      if (code === 'ar') {
        await page.setViewportSize({ width: 375, height: 900 })
        await checkOverflow(page, 'Arabic mobile playlist dialog')
      }
      assert.deepEqual(current.errors, [])
      assert.deepEqual(current.state.unexpected, [])
      assert.equal(current.state.mutations.length, 0)
      await current.context.close()
    }
    console.log('localization browser checks passed: 15 languages, detection, persistence, fallback, denied storage, chunk retry, selection races, RTL, form state, API values, clocks, dates, counts, and durations')
  } finally {
    if (browser) await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
