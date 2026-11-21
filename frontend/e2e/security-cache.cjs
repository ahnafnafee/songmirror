// Settings snapshots must never preserve credentials from older releases.
const assert = require('node:assert/strict')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { chromium } = require('playwright')

const root = path.resolve(__dirname, '..')
const vite = path.join(path.dirname(require.resolve('vite/package.json')), 'bin/vite.js')
const base = 'http://127.0.0.1:4329'

async function main() {
  const server = spawn(process.execPath, [vite, 'preview', '--host', '127.0.0.1', '--port', '4329', '--strictPort'],
    { cwd: root, stdio: 'ignore', windowsHide: true })
  let browser
  try {
    let ready = false
    for (let i = 0; i < 100; i++) {
      try { ready = (await fetch(base)).ok } catch { /* wait for preview */ }
      if (ready) break
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    assert(ready, 'preview server did not start')
    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext()
    await context.addInitScript(() => {
      const data = { DISPLAY_NAME: 'Old value', LASTFM_SESSION_KEY: 'private-session', DEEZER_ARL: 'private-cookie' }
      for (const version of [1, 2]) {
        localStorage.setItem(`songmirror-cache-v${version}:settings`, JSON.stringify({ version, savedAt: Date.now(), data }))
      }
    })
    await context.route('**/api/**', async route => {
      const endpoint = new URL(route.request().url()).pathname
      const data = endpoint === '/api/settings'
        ? { DISPLAY_NAME: 'Safe listener', DOWNLOAD_DIR: '', LOCAL_MIRROR_FORMAT: '', create_playlist_default_source: 'file' }
        : endpoint === '/api/sync/status' ? { jobs: [], master: false } : []
      await route.fulfill({ json: data })
    })
    await context.route('**/events', route => route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' }))
    const page = await context.newPage()
    await page.goto(base + '/settings')
    await page.getByLabel('Display name').waitFor()
    await page.waitForFunction(() => {
      const saved = localStorage.getItem('songmirror-cache-v2:settings')
      return saved && JSON.parse(saved).data.DISPLAY_NAME === 'Safe listener'
    })
    const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }))
    assert(!storage.includes('private-session') && !storage.includes('private-cookie'))
    assert(!storage.includes('songmirror-cache-v1:settings'))
    assert.equal(await page.getByLabel('Display name').inputValue(), 'Safe listener')
    await context.close()
    console.log('ok settings cache removes old credential payloads and retains public settings')
  } finally {
    if (browser) await browser.close()
    server.kill()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
