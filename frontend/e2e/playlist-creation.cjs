// Production-bundle regressions for history recovery and the creation workspace.
// Every API response is local; no music service or real playlist is contacted.
const assert = require('node:assert/strict')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function main() {
  const dist = path.resolve(__dirname, '../dist')
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname
    const asset = path.resolve(dist, '.' + pathname)
    const file = asset.startsWith(dist + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile()
      ? asset : path.join(dist, 'index.html')
    const mime = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.woff2': 'font/woff2' }
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  const browser = await chromium.launch({ headless: true })
  const errors = []
  const job = {
    id: 'review', status: 'ready', source_kind: 'text', destination_account: 'spotify',
    destination_name: 'Weekend playlist', destination_description: '', destination_mode: 'create',
    created_at: '2026-09-14T00:00:00Z', updated_at: '2026-09-14T00:00:00Z', total_tracks: 1,
    matched_tracks: 1, unmatched_tracks: 0, needs_review: 0, tracks_added: 0, tracks_skipped: 0, tracks_failed: 0,
  }
  const track = { import_id: job.id, position: 0, title: 'One More Time', artist: 'Daft Punk',
    parse_status: 'parsed', decision: 'auto', resolved_target_id: 'track-1', score: 0.99, write_status: 'pending' }

  async function makePage(state = {}) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/**', async route => {
      const req = route.request()
      const url = new URL(req.url())
      const send = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      if (url.pathname === '/api/accounts') return send([{ id: 'spotify', provider: 'spotify', provider_name: 'Spotify',
        label: 'Spotify', name: 'Spotify', state: 'connected', fields: [], transferable: true,
        capabilities: { library_read: true, library_write: true, public_playlist_read: true } }])
      if (url.pathname === '/api/settings') return send({ create_playlist_default_source: 'text' })
      if (url.pathname === '/api/playlists' || url.pathname === '/api/links') return send([])
      if (url.pathname === '/api/imports') {
        state.historyRequests = (state.historyRequests || 0) + 1
        if (state.history === 'pending') return
        if (state.history === 'error') return send({ detail: 'History is temporarily unavailable' }, 503)
        return send({ jobs: state.jobs || [] })
      }
      if (url.pathname === '/api/imports/text') return send(job, 201)
      if (url.pathname === '/api/imports/review/match') return send({ ...job, status: 'matching', matched_tracks: 0 }, 202)
      if (url.pathname === '/api/imports/search-track') {
        assert.equal(url.searchParams.get('account'), job.destination_account)
        if (url.searchParams.get('query') !== state.spotifyLink) return send({ results: [] })
        return send({ results: [{ id: '5gYvPf8SQBXm6ogGsyWhaG', name: 'Love of My Life - Live',
          artist: 'Scorpions', album: 'CAPITAL ROCK 100 X 100' }] })
      }
      if (url.pathname === '/api/imports/review/tracks/0') {
        state.decision = req.postDataJSON()
        return send({ ...state.track, ...state.decision, resolved_method: 'manual', score: 1 })
      }
      if (url.pathname === '/api/imports/review') {
        if (req.method() === 'DELETE') { state.jobs = []; return send({ ok: true }) }
        state.jobReads = (state.jobReads || 0) + 1
        state.onJobRead?.()
        if (url.search) await new Promise(resolve => setTimeout(resolve, state.jobDelay || 100))
        return send({ job: state.reviewJob || job, tracks: [state.track || track], candidates: state.candidates || {} })
      }
      return send({})
    })
    await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
    return page
  }

  try {
    const page = await makePage()
    await page.goto(base + '/playlists')
    await page.getByRole('button', { name: 'Create Playlist', exact: true }).click()
    await page.getByLabel('Paste your tracks', { exact: true }).fill('Daft Punk - One More Time')
    await page.getByLabel('Playlist Name', { exact: true }).fill('My draft')
    await page.getByRole('link', { name: 'Import history', exact: true }).click()
    await page.waitForURL(base + '/playlists/create/history')
    await page.getByText('No imports yet', { exact: true }).waitFor()
    assert.equal(await page.getByRole('link', { name: 'Import history', exact: true }).getAttribute('aria-current'), 'page')
    assert.equal(await page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Imports', exact: true }).count(), 0)
    assert.equal(await page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Playlists', exact: true }).getAttribute('aria-current'), 'page')
    const shots = path.join(__dirname, 'screenshots')
    fs.mkdirSync(shots, { recursive: true })
    await page.screenshot({ path: path.join(shots, 'playlist-history-desktop.png'), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: 'Create Playlist', exact: true }).click()
    await page.waitForURL(base + '/playlists/create')
    await page.getByLabel('Paste your tracks', { exact: true }).waitFor({ state: 'visible' })
    assert.equal(await page.getByRole('link', { name: 'New playlist', exact: true }).getAttribute('aria-current'), 'page')
    assert.equal(await page.getByLabel('Paste your tracks', { exact: true }).inputValue(), 'Daft Punk - One More Time')
    assert.equal(await page.getByLabel('Playlist Name', { exact: true }).inputValue(), 'My draft')
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Creation must fit the viewport')
      await page.screenshot({ path: path.join(shots, `playlist-creation-${width}.png`), fullPage: true, animations: 'disabled' })
    }
    await page.getByRole('button', { name: 'Find matches', exact: true }).click()
    await page.getByRole('heading', { name: 'Review Matches', exact: true }).waitFor({ timeout: 8000 })
    console.log('PASS: creation entry, history navigation, draft preservation, mobile layout, delayed matching completion')
    await page.close()

    const timed = { history: 'pending' }
    const slow = await makePage(timed)
    await slow.clock.install()
    await slow.goto(base + '/imports')
    await slow.getByRole('status').filter({ hasText: 'Loading import history' }).waitFor()
    await slow.clock.fastForward(11000)
    await slow.getByRole('button', { name: 'Retry', exact: true }).waitFor()
    assert.equal(await slow.getByText('No imports yet', { exact: true }).count(), 0, 'A failed request must not appear as empty history')
    timed.history = 'ok'
    await slow.getByRole('button', { name: 'Retry', exact: true }).click()
    await slow.getByText('No imports yet', { exact: true }).waitFor()
    console.log('PASS: stalled history request times out and recovers through Retry')
    await slow.close()

    const state = { history: 'error', jobs: [job] }
    const history = await makePage(state)
    await history.goto(base + '/playlists/create/history')
    await history.getByRole('alert').filter({ hasText: 'History is temporarily unavailable' }).waitFor()
    assert.equal(await history.getByText('No imports yet', { exact: true }).count(), 0)
    state.history = 'ok'
    await history.getByRole('button', { name: 'Retry', exact: true }).click()
    await history.getByRole('link', { name: job.destination_name, exact: true }).waitFor()
    for (let attempt = 0; attempt < 2; attempt++) {
      const before = state.jobReads || 0
      await history.getByRole('link', { name: job.destination_name, exact: true }).click()
      await history.getByRole('heading', { name: 'Review Matches', exact: true }).waitFor()
      await history.waitForURL(base + '/playlists/create')
      assert.ok(state.jobReads > before, 'Opening the same saved import again must load its current state')
      await history.getByRole('link', { name: 'Import history', exact: true }).click()
    }
    state.history = 'error'
    await history.getByRole('button', { name: 'Refresh', exact: true }).click()
    await history.getByRole('alert').waitFor()
    assert.equal(await history.getByRole('link', { name: job.destination_name, exact: true }).isVisible(), true, 'Refresh failure must retain the last successful history')
    state.history = 'ok'
    await history.getByRole('button', { name: 'Retry', exact: true }).click()
    await history.getByRole('button', { name: 'Delete', exact: true }).click()
    await history.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click()
    await history.getByText('No imports yet', { exact: true }).waitFor()
    console.log('PASS: history failure recovery, repeated resume, cached rows on refresh failure, deletion')

    const shazam = {
      reviewJob: { ...job, source_kind: 'file', matched_tracks: 0, unmatched_tracks: 1, needs_review: 1 },
      track: { ...track, title: 'Love of My Life (Live)', artist: 'Scorpions',
        decision: 'unmatched', resolved_target_id: null, score: null },
      spotifyLink: 'https://open.spotify.com/track/5gYvPf8SQBXm6ogGsyWhaG?si=shared',
    }
    const review = await makePage(shazam)
    await review.goto(base + '/create-playlist?resume=review')
    await review.getByRole('button', { name: 'Search & Assign', exact: true }).click()
    const search = review.getByRole('dialog', { name: 'Search for Track' })
    await search.getByText('You can also paste a Spotify track link or ID.', { exact: true }).waitFor()
    await search.getByRole('button', { name: 'Search', exact: true }).click()
    await search.getByText('No matching tracks found', { exact: true }).waitFor()
    await search.getByRole('textbox', { name: 'Search', exact: true }).fill(shazam.spotifyLink)
    await search.getByRole('textbox', { name: 'Search', exact: true }).press('Enter')
    await search.getByRole('button', { name: /Love of My Life - Live.*CAPITAL ROCK 100 X 100/ }).click()
    await search.waitFor({ state: 'hidden' })
    assert.deepEqual(shazam.decision, { decision: 'selected', resolved_target_id: '5gYvPf8SQBXm6ogGsyWhaG' })
    console.log('PASS: unmatched Shazam row can be assigned by a Spotify track link')
    await review.close()

    const tied = {
      reviewJob: { ...job, matched_tracks: 0, needs_review: 1 },
      track: { ...track, title: 'Wish You Were Here (Live)', artist: 'Pink Floyd',
        resolved_target_id: null, score: 0.9 },
      candidates: { '0': [
        { target_id: 'pulse', title: 'Wish You Were Here - Live', artist: 'Pink Floyd',
          album: 'Pulse (Live)', duration_ms: 395920, score: 0.9, reason: 'spotify_unavailable' },
        { target_id: 'thunder', title: 'Wish You Were Here - Live', artist: 'Pink Floyd',
          album: 'Delicate Sound of Thunder (Live)', duration_ms: 289093, score: 0.9 },
      ] },
    }
    const tiedReview = await makePage(tied)
    await tiedReview.goto(base + '/create-playlist?resume=review')
    await tiedReview.getByRole('button', { name: 'Review Match', exact: true }).click()
    await tiedReview.getByText(/Pink Floyd · Pulse \(Live\).*Unavailable/).waitFor()
    await tiedReview.getByText(/Pink Floyd · Delicate Sound of Thunder \(Live\)/).waitFor()
    await tiedReview.close()
    console.log('PASS: tied high scores open review with album, duration and availability')

    const pending = { jobDelay: 1000 }
    const started = new Promise(resolve => { pending.onJobRead = resolve })
    const interrupted = await makePage(pending)
    const finished = interrupted.waitForResponse(response => new URL(response.url()).pathname === '/api/imports/review')
    await interrupted.goto(base + '/create-playlist?resume=review')
    await started
    await interrupted.getByRole('link', { name: 'Import history', exact: true }).click()
    await interrupted.waitForURL(base + '/playlists/create/history')
    await interrupted.getByRole('link', { name: 'New playlist', exact: true }).click()
    await interrupted.waitForURL(base + '/playlists/create')
    await finished
    await interrupted.getByLabel('Paste your tracks', { exact: true }).fill('Daft Punk - One More Time')
    assert.equal(await interrupted.getByRole('button', { name: 'Find matches', exact: true }).isEnabled(), true,
      'Leaving a pending resume must not keep the preserved editor busy forever')
    console.log('PASS: switching tabs during a pending resume keeps the editor usable')
    assert.deepEqual(errors, [], 'Browser runtime errors')
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
