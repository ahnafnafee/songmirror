// Account setup and long-feed layout regressions against the production bundle.
const assert = require('node:assert/strict')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function main() {
  const dist = path.resolve(__dirname, '../dist')
  const server = http.createServer((req, res) => {
    const asset = path.resolve(dist, '.' + new URL(req.url, 'http://localhost').pathname)
    const file = asset.startsWith(dist + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile()
      ? asset : path.join(dist, 'index.html')
    res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json' }[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  const browser = await chromium.launch({ headless: true })
  const errors = []
  const account = {
    id: 'lastfm-test', provider: 'lastfm', provider_name: 'Last.fm', name: 'Last.fm', label: 'Last.fm',
    auth_kind: 'oauth_redirect', state: 'unconfigured', transferable: false, source_capable: true,
    is_default: true, removable: false, preserves_order: false, detail: '',
    supports_playlists: false, callback_url: base + '/oauth/lastfm/callback',
    capabilities: { library_read: false, library_write: false, favorites_write: false, public_playlist_read: false },
    fields: [ ['LASTFM_API_KEY', 'API key', true], ['LASTFM_API_SECRET', 'Shared secret', true],
      ['LASTFM_USER', 'Username', false] ]
      .map(([key, label, secret]) => ({ key, label, secret, required: key === 'LASTFM_API_KEY', configured: false, value: '' })),
  }
  const calls = []
  const job = { id: 'job', name: 'Daily playlists', enabled: true, mode: 'oneway', source: 'spotify',
    providers: 'spotify,lastfm-test', authorities: '', playlists: '', interval: '15m', max_adds: 200, max_removals: 25, download: false }

  async function makePage(events = []) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    page.setDefaultTimeout(8000)
    page.on('pageerror', error => errors.push(error.message))
    await page.addInitScript(events => localStorage.setItem('songmirror-live-feed-v1', JSON.stringify(events)), events)
    await page.route('**/api/**', route => {
      const req = route.request(), url = new URL(req.url())
      const send = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
      if (url.pathname === '/api/accounts') return send([account])
      if (url.pathname === '/api/accounts/lastfm-test/config') { calls.push({ config: req.postDataJSON() }); return send({ ok: true }) }
      if (url.pathname === '/api/accounts/lastfm-test/connect') {
        const body = req.postData() ? req.postDataJSON() : null
        calls.push({ connect: body })
        if (!body) {
          account.state = 'connected'
          account.capabilities.favorites_write = true
          account.authorization_pending = true
          return send({ kind: 'redirect', url: 'https://www.last.fm/api/auth', redirect_uri: account.callback_url })
        }
        return send({ kind: 'token_paste', state: 'connected', detail: 'Connected' })
      }
      if (url.pathname === '/api/syncs') return send([job])
      if (url.pathname === '/api/sync/status') return send({ jobs: [], running: false })
      if (['/api/playlists', '/api/links', '/api/playlist-backups'].includes(url.pathname)) return send([])
      return send({})
    })
    await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
    return page
  }

  try {
    const page = await makePage()
    await page.clock.install()
    await page.goto(base + '/accounts')
    await page.getByRole('button', { name: 'Connect', exact: true }).click()
    const dialog = page.getByRole('dialog')
    assert.equal(await dialog.getByLabel('Signed-in web request').count(), 0)
    await dialog.getByLabel('API key', { exact: false }).fill('api-key')
    assert.equal(await dialog.getByRole('button', { name: 'Save and continue' }).isDisabled(), true, 'API approval requires the shared secret')
    await dialog.getByLabel('Shared secret', { exact: false }).fill('api-secret')
    await dialog.getByRole('button', { name: 'Save and continue' }).click()
    await dialog.getByRole('link', { name: 'Continue to sign in' }).waitFor()
    await page.clock.fastForward(5000)
    assert.equal(await dialog.getByRole('link', { name: 'Continue to sign in' }).isVisible(), true,
      'An existing connection must not finish a new authorization before its callback')
    assert.deepEqual(calls.splice(0), [{ config: { LASTFM_API_KEY: 'api-key', LASTFM_API_SECRET: 'api-secret' } }, { connect: null }])
    assert.equal(await dialog.getByRole('button', { name: 'Playlist web session', exact: true }).count(), 0)
    await dialog.getByRole('button', { name: 'Public history', exact: true }).click()
    assert.equal(await dialog.getByLabel('Shared secret', { exact: false }).count(), 0)
    await dialog.getByLabel('Username', { exact: false }).fill('listener')
    await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await dialog.getByRole('status').filter({ hasText: 'Last.fm is connected.' }).waitFor()
    assert.deepEqual(calls.splice(0), [{ connect: { LASTFM_USER: 'listener', LASTFM_API_KEY: 'api-key' } }])
    await page.close()
    console.log('PASS: API authorization and direct public-history setup; no website playlist option')

    const events = Array.from({ length: 500 }, (_, i) => ({ ts: 1758000000 + i, kind: 'add', tag: 'lastfm-test', message: `Track ${i} added`, data: {} }))
    const feedPage = await makePage(events)
    await feedPage.goto(base + '/sync')
    const feed = feedPage.getByRole('log')
    await feed.locator('li').nth(499).waitFor({ state: 'attached' })
    for (const width of [1440, 375]) {
      await feedPage.setViewportSize({ width, height: 1000 })
      const bounds = await feed.evaluate(el => ({ listHeight: el.clientHeight, listScroll: el.scrollHeight,
        pageHeight: document.documentElement.scrollHeight, pageWidth: document.documentElement.scrollWidth, width: innerWidth }))
      assert.ok(bounds.listScroll > bounds.listHeight * 5, 'Exercise a long scrollable event list')
      assert.ok(bounds.pageHeight < 2500, `Feed must not stretch the page: ${JSON.stringify(bounds)}`)
      assert.ok(bounds.pageWidth <= bounds.width, 'Page must fit horizontally')
      await feed.evaluate(el => { el.scrollTop = 0 })
      const afterScroll = await feedPage.evaluate(() => document.documentElement.scrollHeight)
      assert.ok(afterScroll < 2500, 'Scrolling the feed must not produce blank document overflow')
    }
    // Positive control: removing containment must reproduce the reported bug.
    const leaked = await feed.evaluate(el => { el.style.position = 'static'; el.scrollTop = 0; return document.documentElement.scrollHeight })
    assert.ok(leaked > 5000, `Positive control should reproduce overflow, got ${leaked}`)
    await feed.evaluate(el => { el.style.position = ''; })
    await feedPage.close()
    assert.deepEqual(errors, [])
    console.log('PASS: 500-event feed stays bounded on desktop and mobile; positive control reproduces overflow')
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
