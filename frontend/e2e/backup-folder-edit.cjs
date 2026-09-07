// Focused regression: editing a folder is safe while a backup is running;
// applying that change must wait, and polling must preserve the draft.
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
    const mime = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.woff2': 'font/woff2' }
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage()
    const job = { account_id: 'spotify', provider: 'spotify', provider_name: 'Spotify', account_name: 'Spotify',
      enabled: true, interval: '24h', format: 'json', retention: 5, storage_dir: '',
      default_storage_dir: '/data/playlist_backups', storage_path: '/data/playlist_backups/spotify',
      running: true, next_run_at: null, snapshot_count: 1, last_success: null, last_failure: null }
    let saved = null
    let nativeRequests = 0
    const createdFolders = []
    await page.route('**/api/**', async route => {
      const req = route.request()
      const url = new URL(req.url())
      let body = []
      if (url.pathname === '/api/accounts') body = [{ id: 'spotify', provider: 'spotify', label: '', name: 'Spotify', state: 'connected', fields: [], transferable: true }]
      if (url.pathname === '/api/settings') body = { DISPLAY_NAME: '', DOWNLOAD_DIR: '/music', LOCAL_MIRROR_FORMAT: '' }
      if (url.pathname === '/api/sync/status') body = { running: false, jobs: [], last: null }
      if (url.pathname === '/api/playlist-backups') body = [job]
      if (url.pathname === '/api/playlist-backups/spotify' && req.method() === 'PUT') {
        saved = req.postDataJSON()
        Object.assign(job, saved)
        body = job
      }
      if (url.pathname === '/api/folders/config') body = { scope: 'container', mounts: [{ host: 'F:\\Torrent\\Music', server: '/music' }], locations: [{ name: 'App data', path: '/data' }] }
      if (url.pathname === '/api/folders' && req.method() === 'POST') {
        const values = req.postDataJSON()
        if (values.name === 'existing') return route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'A file or folder with that name already exists. Choose another name.' }) })
        createdFolders.push(values)
        body = { path: values.parent + '/' + values.name }
      }
      if (url.pathname === '/api/folders' && req.method() === 'GET') {
        const folder = url.searchParams.get('path') || '/data'
        body = { path: folder, parent: '/data', writable: true, directories: [], breadcrumbs: [{ name: 'App data', path: '/data' }] }
      }
      if (url.pathname.startsWith('/api/folders/pick')) nativeRequests++
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    })
    await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
    await page.goto(`http://127.0.0.1:${server.address().port}/settings?section=backups`)
    const folder = page.getByLabel('Backup folder', { exact: true })
    await folder.waitFor()
    assert.equal(await folder.isEnabled(), true, 'A running backup must not disable folder browsing')
    assert.equal(await page.getByRole('switch', { name: 'Use default backup folder' }).isEnabled(), true)
    await folder.click()
    await page.getByRole('dialog', { name: 'Choose backup folder' }).waitFor()
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    await page.getByRole('button', { name: 'Enter path manually', exact: true }).click()
    await folder.fill('/data/custom-backups')
    const save = page.getByRole('button', { name: 'Save Spotify backup schedule' })
    assert.equal(await save.isDisabled(), true, 'Changing the active destination must wait for completion')
    await page.getByText('You can choose a folder now. Save the new location after this backup finishes.').waitFor()
    job.running = false
    await page.waitForFunction(() => !document.querySelector('[aria-label="Save Spotify backup schedule"]').disabled, null, { timeout: 8000 })
    assert.equal(await folder.inputValue(), '/data/custom-backups', 'Polling must preserve the selected draft')
    await Promise.all([page.waitForResponse(response => response.url().endsWith('/api/playlist-backups/spotify') && response.request().method() === 'PUT'), save.click()])
    assert.equal(saved.storage_dir, '/data/custom-backups')
    await page.getByRole('link', { name: 'Downloads & Jellyfin', exact: true }).click()
    await page.getByLabel('Download folder', { exact: true }).click()
    await page.getByRole('dialog', { name: 'Choose download folder' }).waitFor()
    const dialog = page.getByRole('dialog', { name: 'Choose download folder' })
    await dialog.getByText('Docker storage, not your whole computer').waitFor()
    await dialog.getByText('Container path:', { exact: false }).waitFor()
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 900 })
      await dialog.getByRole('button', { name: 'New folder', exact: true }).click()
      const name = dialog.getByLabel('Folder name', { exact: true })
      await name.fill('unused')
      await dialog.getByRole('button', { name: 'Cancel creation', exact: true }).click()
      assert.equal(createdFolders.length, width === 1280 ? 0 : 1, 'Cancel creation must not write a folder')
      await dialog.getByRole('button', { name: 'New folder', exact: true }).click()
      await name.fill('existing')
      await name.press('Enter')
      await dialog.getByRole('alert').filter({ hasText: 'already exists' }).waitFor()
      assert.equal(await name.inputValue(), 'existing', 'An error must preserve the entered name')
      await name.fill('My backups ' + width)
      fs.mkdirSync(path.join(__dirname, 'screenshots'), { recursive: true })
      await page.screenshot({ path: path.join(__dirname, `screenshots/new-folder-${width}.png`) })
      await name.press('Enter')
      await dialog.getByRole('status').filter({ hasText: 'Created My backups ' + width }).waitFor()
      assert.ok((await dialog.innerText()).includes('Cancelling the picker will not delete it.'))
      const size = await dialog.evaluate(el => ({ scroll: el.scrollWidth, client: el.clientWidth }))
      assert.ok(size.scroll <= size.client, 'Folder controls must fit at ' + width)
    }
    assert.equal(createdFolders[0].parent, '/music')
    assert.equal(createdFolders[1].parent, '/music/My backups 1280')
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
    assert.equal((await page.getByLabel('Download folder', { exact: true }).innerText()).trim(), 'F:\\Torrent\\Music', 'Creating a folder must not change the saved location')
    assert.equal(nativeRequests, 0, 'Neither picker may request a desktop helper')
    await page.goto(`http://127.0.0.1:${server.address().port}/accounts`)
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 900 })
      const controls = [page.getByLabel('Provider', { exact: true }), page.getByLabel('New profile label', { exact: true }), page.getByRole('button', { name: 'Add profile', exact: true })]
      const boxes = await Promise.all(controls.map(control => control.boundingBox()))
      if (width === 1280) {
        assert.ok(Math.max(...boxes.map(box => box.y)) - Math.min(...boxes.map(box => box.y)) <= 1, 'Profile fields and button must align at the top')
        assert.ok(Math.max(...boxes.map(box => box.y + box.height)) - Math.min(...boxes.map(box => box.y + box.height)) <= 1, 'Profile fields and button must align at the bottom')
      } else assert.ok(boxes[0].y < boxes[1].y && boxes[1].y < boxes[2].y, 'Profile controls stack on mobile')
      await page.screenshot({ path: path.join(__dirname, `screenshots/account-profile-alignment-${width}.png`) })
    }
    console.log('PASS: running-backup editing, draft preservation, no helper, Docker path guidance, folder creation/cancellation/errors on desktop and mobile')
    console.log('PASS: account profile row aligns on desktop and stacks on mobile')
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
