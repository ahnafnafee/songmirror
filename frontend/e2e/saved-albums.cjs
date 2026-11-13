// Saved albums use the normal sync preview/scheduler, with no track/removal controls.
const assert = require('node:assert/strict')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const account = (id, name) => ({
  id, provider: id, name, provider_name: name, label: name, state: 'connected',
  auth_kind: 'token_paste', fields: [], transferable: id !== 'lastfm', source_capable: true,
  supports_playlists: id !== 'lastfm', preserves_order: true,
  capabilities: { library_read: true, library_write: id !== 'lastfm', public_playlist_read: id !== 'lastfm', favorites_write: true },
})

async function main() {
  const dist = path.resolve(__dirname, '../dist')
  const server = http.createServer((req, res) => {
    const asset = path.resolve(dist, '.' + new URL(req.url, 'http://localhost').pathname)
    const file = asset.startsWith(dist + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile()
      ? asset : path.join(dist, 'index.html')
    res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } })
  page.setDefaultTimeout(15_000)
  const errors = [], runs = []
  let saved = null
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url())
    const send = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/api/accounts') return send([account('spotify', 'Spotify'), account('tidal', 'TIDAL'), account('amazon', 'Amazon Music'), account('lastfm', 'Last.fm')])
    if (url.pathname === '/api/sync/status') return send({ running: false, master: true, scheduled: false, jobs: [], last: null })
    if (url.pathname === '/api/syncs' && route.request().method() === 'POST') {
      saved = { ...route.request().postDataJSON(), id: 'albums' }
      return send(saved)
    }
    if (url.pathname === '/api/syncs/albums' && route.request().method() === 'PUT') {
      saved = { ...saved, ...route.request().postDataJSON() }
      return send(saved)
    }
    if (url.pathname === '/api/syncs/albums/run') {
      runs.push(url.searchParams.get('execute'))
      return send({ queued: true }, 202)
    }
    if (url.pathname === '/api/syncs') return send(saved ? [saved] : [])
    if (url.pathname.startsWith('/api/playlists')) return send([])
    return send({})
  })
  await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}/sync`)
    await page.getByRole('button', { name: 'New sync', exact: true }).first().click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Name', { exact: false }).fill('Saved album import')
    await dialog.getByRole('radio', { name: 'Services', exact: true }).click()
    await dialog.getByRole('button', { name: /^Last.fm/ }).click()
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    const albums = dialog.getByRole('switch', { name: /^Saved albums/ })
    await albums.click()
    assert.equal(await albums.getAttribute('aria-checked'), 'true')
    await dialog.getByRole('button', { name: 'Next', exact: true }).click()
    await dialog.getByRole('switch', { name: /^Active/ }).click() // one-time import
    await dialog.getByRole('button', { name: 'Next', exact: true }).click()
    assert.equal(await dialog.getByRole('switch', { name: /Mirror removals|Download this sync/ }).count(), 0)
    await dialog.getByText('All saved albums', { exact: true }).waitFor()
    // Verify the album wizard also fits a narrow screen.
    await page.setViewportSize({ width: 390, height: 844 })
    assert.ok(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1))
    await dialog.getByRole('button', { name: 'Create sync', exact: true }).click()
    await page.getByRole('heading', { name: 'Saved album import', exact: true }).waitFor()
    assert.equal(saved.saved_albums, true)
    assert.deepEqual(new Set(saved.providers.split(',')), new Set(['spotify', 'tidal', 'amazon', 'lastfm']))
    assert.equal(saved.sync_playlists, false)
    assert.equal(saved.liked_tracks, false)
    assert.equal(saved.max_removals, 0)
    assert.equal(saved.download, false)
    assert.equal(saved.enabled, false)
    const previewResponse = page.waitForResponse(response => response.url().includes('/api/syncs/albums/run'))
    await page.getByRole('button', { name: 'Preview', exact: true }).click()
    await previewResponse
    assert.deepEqual(runs, ['0'])
    await page.getByRole('button', { name: 'Edit', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    assert.equal(await dialog.getByRole('switch', { name: /^Saved albums/ }).getAttribute('aria-checked'), 'true')
    await dialog.getByRole('radio', { name: 'Direction', exact: true }).click()
    await dialog.getByRole('radio', { name: /^Bidirectional/ }).locator('..').click()
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    const unavailable = dialog.getByRole('switch', { name: /^Saved albums/ })
    assert.equal(await unavailable.getAttribute('aria-checked'), 'false')
    assert.equal(await unavailable.isDisabled(), true)
    assert.deepEqual(errors, [])
    console.log('PASS: create, preview, reopen, mobile layout, and unsupported-mode guard for saved albums')
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
