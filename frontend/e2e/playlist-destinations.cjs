// ListenBrainz and Jellyfin as playlist destinations in the sync wizard and transfer form.
// Account rows mirror /api/accounts: a Jellyfin profile without a User ID stays browse-only.
const assert = require('node:assert/strict')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const BASE = {
  auth_kind: 'api_key', state: 'connected', detail: '', is_default: true, removable: false, fields: [],
  preserves_order: false, public_playlists: true, editable_details: [], source_capable: true, supports_playlists: true,
}
const ACCOUNTS = [
  { ...BASE, id: 'tidal', provider: 'tidal', name: 'TIDAL', provider_name: 'TIDAL', label: 'TIDAL', transferable: true,
    capabilities: { library_read: true, library_write: true, public_playlist_read: true, favorites_write: true } },
  { ...BASE, id: 'loves', provider: 'listenbrainz', name: 'ListenBrainz', provider_name: 'ListenBrainz', label: 'ListenBrainz',
    transferable: true,
    capabilities: { library_read: true, library_write: true, public_playlist_read: false, favorites_write: true } },
  { ...BASE, id: 'jf', provider: 'jellyfin', name: 'Jellyfin', provider_name: 'Jellyfin', label: 'Jellyfin', transferable: true,
    capabilities: { library_read: true, library_write: true, public_playlist_read: false, favorites_write: false } },
  { ...BASE, id: 'jf-browse', provider: 'jellyfin', name: 'Living room Jellyfin', provider_name: 'Jellyfin', label: 'Living room',
    is_default: false, removable: true, transferable: false, source_capable: false, supports_playlists: false,
    detail: 'Add a User ID to sync playlists.',
    capabilities: { library_read: true, library_write: false, public_playlist_read: false, favorites_write: false } },
]
const PLAYLISTS = { tidal: [{ id: 'road', name: 'Road trip', count: 2, image: '', owned: true }] }

async function main() {
  const dist = path.resolve(__dirname, '../dist')
  const server = http.createServer((req, res) => {
    const asset = path.resolve(dist, '.' + new URL(req.url, 'http://localhost').pathname)
    const file = asset.startsWith(dist + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile()
      ? asset : path.join(dist, 'index.html')
    res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png' }[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } })
  page.setDefaultTimeout(10_000)
  const errors = [], saved = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const request = route.request(), url = new URL(request.url())
    const send = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/api/accounts') return send(ACCOUNTS)
    if (url.pathname === '/api/syncs' && request.method() === 'POST') {
      const job = { id: 'job', ...request.postDataJSON() }
      saved.push(job)
      return send(job)
    }
    if (url.pathname === '/api/sync/status') return send({ jobs: [], running: false })
    if (url.pathname === '/api/playlists') return send(PLAYLISTS[url.searchParams.get('provider')] ?? [])
    if (url.pathname.startsWith('/api/playlists') || ['/api/syncs', '/api/links', '/api/playlist-backups', '/api/transfers'].includes(url.pathname)) return send([])
    return send({})
  })
  await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))

  try {
    await page.goto(base + '/sync')
    await page.getByRole('button', { name: 'New sync', exact: true }).first().click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Name', { exact: false }).fill('TIDAL to my servers')
    await dialog.getByRole('radio', { name: 'TIDAL', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Services', exact: true }).click()
    for (const name of [/^ListenBrainz/, /^Jellyfin/]) {
      assert.equal(await dialog.getByRole('button', { name }).getAttribute('aria-pressed'), 'true',
        `${name} joins as a playlist destination`)
    }
    assert.equal(await dialog.getByRole('button', { name: /Living room/ }).count(), 0,
      'A Jellyfin profile without a User ID is not offered for sync')
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    await dialog.getByRole('checkbox', { name: 'Road trip', exact: false }).locator('..').click()
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 1000 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    }
    await page.setViewportSize({ width: 1280, height: 1000 })
    await dialog.getByRole('button', { name: 'Create sync', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(saved.length, 1)
    const providers = saved[0].providers.split(',')
    assert.equal(saved[0].source, 'tidal')
    assert.ok(providers.includes('loves') && providers.includes('jf') && !providers.includes('jf-browse'), saved[0].providers)
    assert.equal(saved[0].playlists, 'Road trip')
    console.log('PASS: the sync wizard offers ListenBrainz and Jellyfin as playlist destinations and saves them')

    await page.goto(base + '/transfers')
    const sourceService = page.getByLabel('Service', { exact: true }).first()
    const sources = await sourceService.locator('option').allTextContents()
    assert.ok(sources.includes('ListenBrainz') && sources.includes('Jellyfin'), sources.join(', '))
    assert.ok(!sources.includes('Living room Jellyfin'), 'A browse-only Jellyfin profile cannot be a transfer source')
    await sourceService.selectOption('tidal')
    const destination = page.locator('[data-tour="transfer-destination"]').getByLabel('Service', { exact: true })
    const destinations = await destination.locator('option').allTextContents()
    assert.ok(destinations.includes('ListenBrainz') && destinations.includes('Jellyfin'), destinations.join(', '))
    assert.ok(!destinations.includes('Living room Jellyfin'), 'A browse-only Jellyfin profile cannot be a destination')
    await destination.selectOption('jf')
    assert.equal(await destination.inputValue(), 'jf')
    assert.deepEqual(errors, [])
    console.log('PASS: the transfer form lists both services as sources and destinations, excluding browse-only Jellyfin')
  } finally {
    await page.close()
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
