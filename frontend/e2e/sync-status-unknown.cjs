// A dashboard opened while the sync status cannot load must not claim that auto-sync is paused.
const assert = require('node:assert/strict')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const ACCOUNT = {
  id: 'spotify', provider: 'spotify', name: 'Spotify', provider_name: 'Spotify', label: 'Spotify', state: 'connected',
  auth_kind: 'oauth_redirect', detail: '', is_default: true, removable: false, fields: [], transferable: true,
  source_capable: true, supports_playlists: true, preserves_order: true, public_playlists: true, editable_details: [],
  capabilities: { library_read: true, library_write: true, public_playlist_read: true, favorites_write: true },
}
const JOB = {
  id: 'job', name: 'Nightly', enabled: true, mode: 'oneway', source: 'spotify', authorities: '', providers: 'spotify',
  playlists: '', sync_playlists: true, liked_tracks: false, liked_routes: {}, interval: '3h', max_adds: 200,
  max_removals: 50, apply_large_removals: false, download: false, sources: [], destination: null, removal_strategy: 'none',
}
const NEXT = Math.floor(Date.now() / 1000) + 3600
const STATUS = {
  running: false, master: true, scheduled: true, next_run_at: NEXT, last: null,
  jobs: [{ id: 'job', name: 'Nightly', enabled: true, running: false, queued: false, paused: false, next_run_at: NEXT }],
}

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
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let statusUp = false
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url())
    const send = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/api/sync/status') return statusUp ? send(STATUS) : send({ detail: 'Service unavailable' }, 503)
    if (url.pathname === '/api/accounts') return send([ACCOUNT])
    if (url.pathname === '/api/syncs') return send([JOB])
    if (url.pathname.startsWith('/api/playlists') || ['/api/links', '/api/playlist-backups', '/api/transfers'].includes(url.pathname)) return send([])
    return send({})
  })
  await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}/`)
    await page.getByText('Auto-sync: unavailable', { exact: true }).waitFor()
    const body = await page.locator('body').innerText()
    assert.ok(!body.includes('Auto-sync: paused') && !body.includes('Auto-sync paused'), 'An unknown status is not shown as paused')
    assert.ok(!/\bManual\b/.test(body), 'An enabled job is not shown as manual while the status is unknown')
    console.log('PASS: a dashboard without sync status shows it as unavailable, not paused or manual')

    statusUp = true
    await page.getByText('Auto-sync: on', { exact: true }).waitFor()
    assert.equal(await page.getByText('Auto-sync: unavailable', { exact: true }).count(), 0)
    assert.deepEqual(errors, [])
    console.log('PASS: the dashboard shows the real auto-sync state once the status loads')
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
