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
const PLAYLISTS = {
  tidal: [{ id: 'road', name: 'Road trip', count: 2, image: '', owned: true }],
  jf: [{ id: 'mix', name: 'Mix', count: 2, image: '', owned: true }],
}

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
    if (url.pathname === '/api/syncs') return send(saved)
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
    const shots = process.env.SONGMIRROR_E2E_SCREENSHOTS
    const nameHint = page.getByText('Enter a name at the top to save this sync.', { exact: true })
    const create = page.getByRole('button', { name: 'Create sync', exact: true })
    assert.equal(await nameHint.isVisible(), true, 'A missing name explains why Create sync is disabled')
    assert.equal(await create.isEnabled(), false)
    // Every service stays listed, sectioned by kind.
    const groups = await dialog.getByRole('radiogroup', { name: 'Source of truth' }).evaluate(picker =>
      [...picker.children].map(group => [
        group.firstElementChild.textContent.trim(),
        [...group.querySelectorAll('[role=radio]')].map(chip => chip.textContent.trim()),
      ]))
    assert.deepEqual(groups.map(([label]) => label), ['Streaming services', 'Self-hosted servers', 'Listening history'])
    assert.deepEqual(groups.map(([, chips]) => chips.length), [1, 1, 1])
    assert.ok(groups[1][1].some(chip => chip.startsWith('Jellyfin')) && groups[2][1][0].startsWith('ListenBrainz'))
    if (shots) await page.screenshot({ path: path.join(shots, 'source-groups-1280.png') })
    await dialog.getByLabel('Name', { exact: false }).fill('TIDAL to my servers')
    assert.equal(await nameHint.count(), 0)
    await dialog.getByRole('radio', { name: 'TIDAL', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Services', exact: true }).click()
    if (shots) {
      for (const width of [1280, 375]) {
        await page.setViewportSize({ width, height: 1000 })
        await page.screenshot({ path: path.join(shots, `service-groups-${width}.png`) })
      }
      await page.setViewportSize({ width: 1280, height: 1000 })
    }
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

    await page.getByRole('button', { name: 'New sync', exact: true }).first().click()
    await dialog.getByLabel('Name', { exact: false }).fill('Jellyfin playlists only')
    await dialog.getByRole('radio', { name: 'TIDAL', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    await dialog.getByRole('checkbox', { name: 'TIDAL Favorite Tracks', exact: false }).locator('..').click()
    await dialog.getByRole('radio', { name: 'Direction', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Jellyfin', exact: true }).click()
    // The saved TIDAL sync already copies TIDAL into Jellyfin, so its deletions would come back.
    const reverse = dialog.getByRole('status').filter({ hasText: 'The sync TIDAL to my servers already copies TIDAL back to Jellyfin' })
    assert.equal(await reverse.isVisible(), true, 'Opposite one-way syncs are flagged on the Direction step')
    await dialog.getByRole('radio', { name: 'Services', exact: true }).click()
    assert.equal(await reverse.isVisible(), true, 'and on the Services step')
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    assert.equal(await dialog.getByRole('checkbox', { name: 'Jellyfin Liked Tracks', exact: false }).count(), 0,
      'A Jellyfin source has no liked-track reader')
    await dialog.getByRole('checkbox', { name: 'Mix', exact: false }).locator('..').click()
    await dialog.getByRole('radio', { name: 'Services', exact: true }).click()
    assert.equal(await reverse.count(), 0, 'Disjoint playlist filters do not copy into each other')
    await dialog.getByRole('button', { name: 'Create sync', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(saved[1].source, 'jf')
    assert.equal(saved[1].liked_tracks, false, 'Switching to Jellyfin clears the previous favorites selection')
    assert.equal(saved[1].sync_playlists, true)
    assert.deepEqual(saved[1].liked_routes, {})
    console.log('PASS: Jellyfin sources hide favorites and clear a previous source’s liked-track selection')

    await page.getByRole('button', { name: 'New sync', exact: true }).first().click()
    await dialog.getByRole('radio', { name: /^Bidirectional/ }).locator('..').click()
    await dialog.getByRole('radio', { name: 'Limits & downloads', exact: true }).click()
    assert.equal(await dialog.getByText('Sync removals', { exact: true }).isVisible(), true)
    assert.equal(await dialog.getByText('Mirror removals', { exact: true }).count(), 0)
    assert.equal(await dialog.getByRole('status').filter({ hasText: 'already copies' }).count(), 0,
      'A Bidirectional sync is the fix, not a conflict')
    await page.keyboard.press('Escape')
    await dialog.waitFor({ state: 'hidden' })
    console.log('PASS: opposite one-way syncs are flagged and Bidirectional mode names its removal switch')

    for (const source of ['tidal', 'jf']) {
      const context = await browser.newContext()
      const probe = await context.newPage()
      probe.setDefaultTimeout(10_000)
      const destination = source === 'jf' ? 'tidal' : 'jf'
      const existing = {
        id: 'existing', name: 'Existing favorites', mode: 'oneway', source, providers: `${source},${destination}`,
        authorities: '', enabled: false, interval: '1h', playlists: '', sync_playlists: false, liked_tracks: true,
        liked_routes: { [destination]: { kind: 'playlist', name: 'Favorites' } }, max_adds: 500,
        max_removals: 0, apply_large_removals: false, download: false,
      }
      let releaseAccounts, edited
      const gate = new Promise(resolve => { releaseAccounts = resolve })
      if (source === 'tidal') releaseAccounts()
      await probe.route('**/api/**', async route => {
        const request = route.request(), url = new URL(request.url())
        const send = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
        if (url.pathname === '/api/accounts') {
          await gate
          return send(ACCOUNTS.map(account => ({ ...account,
            supports_favorites: account.provider !== 'jellyfin',
            state: account.id === 'tidal' && source === 'tidal' ? 'expired' : account.state,
          })))
        }
        if (url.pathname === '/api/syncs/existing' && request.method() === 'PUT') {
          edited = request.postDataJSON()
          return send({ ...existing, ...edited })
        }
        if (url.pathname === '/api/syncs') return send([existing])
        if (url.pathname === '/api/sync/status') return send({ jobs: [], running: false })
        if (url.pathname.startsWith('/api/playlists')) return send([])
        if (['/api/links', '/api/playlist-backups', '/api/transfers'].includes(url.pathname)) return send([])
        return send({})
      })
      await probe.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
      try {
        await probe.goto(base + '/sync')
        await probe.getByRole('button', { name: 'Edit', exact: true }).first().click()
        const editor = probe.getByRole('dialog')
        await editor.getByLabel('Name', { exact: false }).fill('Keep my edited name')
        await editor.getByRole('radio', { name: 'Schedule', exact: true }).click()
        if (source === 'jf') {
          const accountsLoaded = probe.waitForResponse(response => response.url().endsWith('/api/accounts'))
          releaseAccounts()
          await accountsLoaded
          await probe.getByRole('button', { name: 'Edit', exact: true }).first().waitFor()
        }
        assert.equal(await editor.getByRole('radio', { name: 'Schedule', exact: true }).getAttribute('aria-checked'), 'true')
        await editor.getByRole('button', { name: 'Save changes', exact: true }).click()
        await editor.waitFor({ state: 'hidden' })
        assert.equal(edited.name, 'Keep my edited name')
        assert.equal(edited.liked_tracks, source === 'tidal', 'Expired credentials must not change a supported favorites job')
        assert.equal(edited.sync_playlists, source === 'jf')
        assert.deepEqual(edited.liked_routes, source === 'jf' ? {} : existing.liked_routes)
      } finally {
        releaseAccounts()
        await context.close()
      }
    }
    console.log('PASS: editing preserves expired favorites jobs and clears unsupported selections after delayed account loading')

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
