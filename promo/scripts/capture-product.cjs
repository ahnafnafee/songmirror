// Record the built app with the same fictional accounts used in frontend tests.
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const http = require('node:http')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { createReadStream, existsSync } = require('node:fs')
const { chromium } = require('../../frontend/node_modules/playwright')
const { ACCOUNTS, SHOWCASE_PLAYLISTS, installMocks } = require('../../frontend/e2e/verify.cjs')

const root = path.resolve(__dirname, '../..')
const dist = path.join(root, 'frontend/dist')
const output = path.join(root, 'promo/public/footage')
const recordings = path.join(root, 'promo/out/recordings')
const WIDTH = 1264
const HEIGHT = 792
const TEASER_SECONDS = 4.2
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.woff2': 'font/woff2', '.woff': 'font/woff', '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json' }
const accounts = ACCOUNTS.map(account => ({ ...account, state: 'connected', detail: null }))
const playlists = Object.fromEntries(Object.entries(SHOWCASE_PLAYLISTS).map(([provider, rows]) => [
  provider, rows.map(playlist => ({ ...playlist, owned: true })),
]))
const preview = {
  id: 'road-trip',
  status: 'done',
  phase: 'copying',
  source: { account: 'spotify', provider: 'spotify', name: 'Spotify', playlist_id: 'road-trip', playlist_name: 'Road Trip 2025' },
  dest: { account: 'ytmusic', provider: 'ytmusic', name: 'YouTube Music', playlist_id: 'road-trip-copy', playlist_name: 'Road Trip 2025' },
  added: 118,
  processed: 118,
  total: 118,
  deferred: 0,
  unavailable: 0,
  conflicts: [],
  created_at: '2026-10-16T12:00:00Z',
  started_at: '2026-10-16T12:00:00Z',
  finished_at: '2026-10-16T12:02:00Z',
}

const pause = (ms) => new Promise(resolve => setTimeout(resolve, ms))

async function point(page, locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  assert(box, 'The control must be visible before recording')
  const x = box.x + box.width / 2
  const y = box.y + box.height / 2
  await page.mouse.move(x, y, { steps: 8 })
  await pause(120)
}

async function click(page, locator) {
  await point(page, locator)
  await locator.click()
}

async function record(browser, origin, name, url, ready, action) {
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    recordVideo: { dir: recordings, size: { width: WIDTH, height: HEIGHT } },
    locale: 'en-US',
    timezoneId: 'UTC',
  })
  let video
  let trim
  try {
    await context.addInitScript(() => {
      localStorage.setItem('songmirror-theme', 'dark')
      localStorage.setItem('songmirror.language', 'en')
      for (const page of ['dashboard', 'accounts', 'playlists', 'sync', 'transfers', 'settings', 'downloads']) {
        localStorage.setItem(`songmirror-guide-v1:${page}`, 'hidden')
      }
      window.addEventListener('DOMContentLoaded', () => {
        const cursor = document.createElement('i')
        cursor.style.cssText = 'position:fixed;top:0;left:0;z-index:10000;width:17px;height:17px;border:2px solid #ff985f;background:#21130c9e;border-radius:50%;pointer-events:none;visibility:hidden;box-shadow:0 0 0 2px #241610'
        document.body.append(cursor)
        window.addEventListener('pointermove', ({ clientX, clientY }) => {
          cursor.style.visibility = 'visible'
          cursor.style.transform = `translate(${clientX - 8}px,${clientY - 8}px)`
        })
      })
    })
    const opened = performance.now()
    const page = await context.newPage()
    video = page.video()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await installMocks(page, { accounts, playlists })
    await page.route('**/*', route => {
      const address = new URL(route.request().url())
      if (address.href === 'https://m.media-amazon.com/images/G/01/music/logo/1.0/smile_256x256.png') {
        return route.fulfill({ path: path.join(root, 'frontend/e2e/fixtures/amazon-music.png'), contentType: 'image/png' })
      }
      return address.origin === origin ? route.fallback() : route.abort()
    })
    await page.route('**/api/transfers/history*', route => route.fulfill({ json: {
      items: [preview], total: 1, accounts: accounts.slice(0, 2).map(a => ({ id: a.id, name: a.name })),
      providers: ['spotify', 'ytmusic'],
    } }))
    await page.goto(origin + url, { waitUntil: 'networkidle' })
    await ready(page)
    await page.evaluate(() => document.fonts.ready)
    const start = performance.now()
    // The recorder starts as the page opens. Discard the navigation lead-in.
    trim = (start - opened) / 1000 - 0.06
    await pause(400)
    await action(page)
    await pause(Math.max(800, 4500 - (performance.now() - start)))
    assert.deepEqual(errors, [], `${name}: errors in the recorded UI`)
  } finally {
    await context.close()
  }
  execFileSync('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y', '-ss', String(Math.max(0, trim)), '-i', await video.path(),
    '-t', String(TEASER_SECONDS), '-vf', 'fps=30,tpad=stop_mode=clone:stop_duration=0.35',
    '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path.join(output, name + '.mp4'),
  ], { stdio: 'inherit' })
  await video.delete()
  console.log(`Captured ${name}.mp4 from the built app`)
}

async function main() {
  assert(existsSync(path.join(dist, 'index.html')), 'Build the frontend before recording the trailer')
  await Promise.all([fs.mkdir(output, { recursive: true }), fs.mkdir(recordings, { recursive: true })])
  await fs.copyFile(path.join(root, 'frontend/node_modules/@fontsource-variable/archivo/files/archivo-latin-wght-normal.woff2'), path.join(output, 'archivo.woff2'))
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1')
    const file = path.resolve(dist, '.' + url.pathname)
    const asset = file.startsWith(dist + path.sep) && existsSync(file) ? file : path.join(dist, 'index.html')
    response.setHeader('Content-Type', types[path.extname(asset)] ?? 'application/octet-stream')
    createReadStream(asset).on('error', () => { response.statusCode = 404; response.end() }).pipe(response)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  let browser
  try {
    browser = await chromium.launch({ headless: true })
    const origin = `http://127.0.0.1:${server.address().port}`
    await record(browser, origin, 'sync', '/sync',
      page => page.getByRole('heading', { name: 'Default', exact: true }).waitFor(),
      async page => {
        const job = page.getByRole('heading', { name: 'Default', exact: true }).locator('xpath=ancestor::div[contains(@class,"rounded-card")][1]')
        await click(page, job.getByRole('button', { name: 'Edit', exact: true }))
        await pause(330)
        await click(page, page.getByRole('radio', { name: 'Services', exact: true }))
        for (const name of ['Apple Music', 'YouTube Music', 'Qobuz']) {
          const service = page.getByRole('button', { name, exact: true })
          if (await service.getAttribute('aria-pressed') !== 'true') await click(page, service)
        }
      })
    const transfersReady = page => page.getByRole('heading', { name: 'Transfers', exact: true }).waitFor()
    await record(browser, origin, 'transfer', '/transfers', transfersReady,
      async page => {
        const services = page.getByLabel('Service', { exact: true })
        await point(page, services.nth(0))
        await services.nth(0).selectOption('spotify')
        await click(page, page.getByRole('button', { name: 'Playlist', exact: true }))
        await click(page, page.getByRole('option', { name: /Road Trip 2025/ }))
        await point(page, services.nth(1))
        await services.nth(1).selectOption('ytmusic')
        await click(page, page.getByRole('radio', { name: 'Create new', exact: true }))
      })
    await record(browser, origin, 'history', '/transfers', transfersReady,
      async page => {
        await click(page, page.getByRole('radio', { name: 'Transfer history', exact: true }))
        await page.getByText('118 added', { exact: false }).waitFor()
        await point(page, page.getByText('118 added', { exact: false }))
      })
    await record(browser, origin, 'local', '/settings',
      page => page.getByRole('link', { name: 'Downloads & Jellyfin', exact: true }).waitFor(),
      async page => {
        await click(page, page.getByRole('link', { name: 'Downloads & Jellyfin', exact: true }))
        await pause(400)
        await page.mouse.move(WIDTH * 0.67, HEIGHT * 0.70)
        await page.mouse.wheel(0, 355)
      })
  } finally {
    await browser?.close()
    await new Promise(resolve => server.close(resolve))
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
