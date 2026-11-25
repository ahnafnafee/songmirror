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
    res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' }[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  const browser = await chromium.launch({ headless: true })
  const errors = [], connections = [], saved = [], profiles = [], removals = []
  let holdAccountsRefresh
  const guideSteps = [
    ['Emby', 'emby', 'AuthenticateByName'],
    ['Plex', 'plex', 'X-Plex-Token'],
    ['Mopidy', 'mopidy', 'playlists_dir'],
    ['Lyrion Music Server', 'lyrion', 'Playlist Folder'],
    ['Anghami', 'anghami', 'Anghami Developer Portal'],
    ['QQ Music', 'qqmusic', 'QQ Music Skills'],
  ]
  const accounts = [
    { id: 'apple', provider: 'apple', name: 'Apple Music', state: 'connected', fields: [], transferable: false },
    { id: 'amazon', provider: 'amazon', name: 'Amazon Music', state: 'expired', auth_kind: 'token_paste',
      fields: [], transferable: true },
    { id: 'cloud', provider: 'soundcloud', name: 'SoundCloud', provider_name: 'SoundCloud',
      auth_kind: 'oauth_redirect', fields: [], transferable: true, source_capable: true,
      supports_playlists: true, supports_favorites: false,
      callback_url: base + '/oauth/soundcloud/callback', browser_mode: false },
    { id: 'loves', provider: 'listenbrainz', name: 'ListenBrainz', provider_name: 'ListenBrainz',
      transferable: true, source_capable: true, supports_playlists: true,
      fields: [{ key: 'LISTENBRAINZ_USER', label: 'Username', required: true, secret: false },
        { key: 'LISTENBRAINZ_TOKEN', label: 'User token', required: false, secret: true }],
      capabilities: { library_read: true, library_write: false, favorites_write: false, public_playlist_read: false } },
    { id: 'local', provider: 'subsonic', name: 'Navidrome / Subsonic', provider_name: 'Navidrome / Subsonic',
      transferable: true, source_capable: true, supports_playlists: true,
      fields: [{ key: 'SUBSONIC_URL', label: 'Server URL' }, { key: 'SUBSONIC_USER', label: 'Username' },
        { key: 'SUBSONIC_PASSWORD', label: 'Password', secret: true }].map(field => ({ required: true, ...field })),
      capabilities: { library_read: true, library_write: true, favorites_write: true, public_playlist_read: true } },
    ...guideSteps.map(([name, provider]) => ({
      id: provider, provider, name, provider_name: name, fields: [], transferable: true,
      state: provider === 'emby' ? 'error' : 'unconfigured',
    })),
    { id: 'gaana', provider: 'gaana', name: 'Gaana', provider_name: 'Gaana', auth_kind: 'public_link',
      transferable: true, source_capable: false, supports_playlists: true,
      playlist_browser: { login_url: 'https://gaana.com/music', request_hint: 'myplaylists', active: false },
      fields: [{ key: 'GAANA_PUBLIC_PLAYLIST', label: 'Public playlist link', required: true, secret: false }],
      capabilities: { library_read: false, library_write: false, favorites_write: false, public_playlist_read: true } },
    { id: 'audiomack', provider: 'audiomack', name: 'Audiomack', provider_name: 'Audiomack', auth_kind: 'public_link',
      show_in_accounts: false, transferable: true,
      playlist_browser: { login_url: 'https://audiomack.com/my-library/playlists', request_hint: 'v1/user/playlists', active: false },
      fields: [{ key: 'AUDIOMACK_PUBLIC_PLAYLIST', label: 'Public playlist link', required: true, secret: false }] },
  ].map(account => ({ auth_kind: 'api_key', state: 'unconfigured', label: account.name, detail: '',
    is_default: true, removable: false, show_in_accounts: true, preserves_order: false, ...account,
    fields: account.fields.map(field => ({ value: '', configured: false, ...field })) }))

  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } })
  page.setDefaultTimeout(10_000)
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url())
    const send = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/api/accounts') {
      if (request.method() === 'POST') {
        const profile = request.postDataJSON()
        profiles.push(profile)
        const account = accounts.find(row => row.provider === profile.provider && row.is_default)
        if (!account.show_in_accounts && profile.reuse_default) {
          account.show_in_accounts = true
          return send(account)
        }
        const label = profile.label || `${account.provider_name} 2`
        const added = { ...account, id: 'new-profile', label, name: `${account.provider_name} · ${label}`,
          is_default: false, removable: true }
        accounts.push(added)
        return send(added)
      }
      if (holdAccountsRefresh) await holdAccountsRefresh
      return send(accounts)
    }
    if (url.pathname === '/api/accounts/new-profile' && request.method() === 'PATCH') {
      const { label } = request.postDataJSON()
      if (accounts.some(row => row.id !== 'new-profile' && row.label.toLowerCase() === label.toLowerCase())) {
        return route.fulfill({ status: 409, contentType: 'application/json', body: '{}' })
      }
      const account = accounts.find(row => row.id === 'new-profile')
      Object.assign(account, { label, name: `${account.provider_name} · ${label}` })
      return send(account)
    }
    if (url.pathname === '/api/accounts/audiomack' && request.method() === 'DELETE') {
      removals.push('audiomack')
      Object.assign(accounts.find(row => row.id === 'audiomack'), { show_in_accounts: false, state: 'unconfigured' })
      return send({ ok: true })
    }
    if (url.pathname === '/api/accounts/cloud/soundcloud/browser') {
      const account = accounts.find(row => row.id === 'cloud')
      account.browser_mode = request.method() === 'POST'
      account.state = account.browser_mode ? 'connected' : 'unconfigured'
      return send({ state: account.state, detail: '' })
    }
    if (url.pathname === '/api/accounts/qqmusic/qqmusic/browser') {
      const account = accounts.find(row => row.id === 'qqmusic')
      account.browser_mode = request.method() === 'POST'
      account.state = account.browser_mode ? 'connected' : 'unconfigured'
      return send({ state: account.state, detail: '' })
    }
    if (url.pathname === '/api/accounts/gaana/playlist-browser') {
      const account = accounts.find(row => row.id === 'gaana')
      account.playlist_browser.active = request.method() === 'POST'
      account.capabilities.library_read = account.playlist_browser.active
      return send({ state: 'connected', detail: '' })
    }
    if (url.pathname === '/api/accounts/audiomack/playlist-browser' && request.method() === 'POST') {
      const account = accounts.find(row => row.id === 'audiomack')
      account.playlist_browser.active = true
      account.state = 'connected'
      return send({ state: 'connected', detail: '' })
    }
    if (/\/api\/accounts\/[^/]+\/connect$/.test(url.pathname)) {
      const account = accounts.find(account => url.pathname.includes(`/${account.id}/`))
      const values = request.postDataJSON()
      connections.push({ provider: account.provider, values })
      if (values.LISTENBRAINZ_TOKEN === 'wrong-profile-token') {
        return send({ kind: 'api_key', state: 'error', detail: 'ListenBrainz token belongs to a different username.' })
      }
      for (const field of account.fields) {
        if (values[field.key]) {
          field.configured = true
          field.value = field.secret ? '' : values[field.key]
        }
      }
      if (values.LISTENBRAINZ_TOKEN) {
        account.capabilities.favorites_write = true
        account.capabilities.library_write = true
      }
      account.state = 'connected'
      return send({ kind: account.auth_kind, state: 'connected', detail: account.name })
    }
    if (url.pathname === '/api/syncs') {
      if (request.method() === 'POST') {
        const job = { id: 'job', ...request.postDataJSON() }
        saved.push(job)
        return send(job)
      }
      return send(saved)
    }
    if (url.pathname === '/api/sync/status') return send({ jobs: [], running: false })
    if (url.pathname.startsWith('/api/playlists')) return send([])
    if (['/api/links', '/api/playlist-backups', '/api/transfers'].includes(url.pathname)) return send([])
    return send({})
  })
  await page.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
  await page.route('https://m.media-amazon.com/**', route => route.fulfill({
    contentType: 'image/png', body: fs.readFileSync(path.join(__dirname, 'fixtures/amazon-music.png')),
  }))

  try {
    await page.goto(base + '/accounts')
    const picker = page.getByRole('button', { name: 'Add account', exact: true })
    const search = page.getByRole('combobox', { name: 'Search', exact: true })
    const accountCards = page.locator('[data-tour="account-card"]')
    const attention = page.getByRole('heading', { name: 'Needs a look', exact: true })
    const connected = page.getByRole('heading', { name: 'Connected accounts', exact: true })
    const amazon = accountCards.filter({ has: page.getByRole('heading', { name: 'Amazon Music', exact: true }) })
    await attention.waitFor()
    assert.deepEqual((await accountCards.getByRole('heading', { level: 3 }).allTextContents()).slice(0, 2), ['Amazon Music', 'Emby'])
    assert.ok((await attention.boundingBox()).y < (await amazon.boundingBox()).y)
    assert.ok((await amazon.boundingBox()).y < (await connected.boundingBox()).y)
    assert.ok((await connected.boundingBox()).y < (await page.getByRole('heading', { name: 'Apple Music' }).boundingBox()).y)
    await amazon.getByRole('button', { name: 'Reconnect', exact: true }).click()
    const amazonDialog = page.getByRole('dialog', { name: 'Connect Amazon Music', exact: true })
    assert.equal(await amazonDialog.getByRole('link', { name: 'music.amazon.com', exact: true }).getAttribute('href'), 'https://music.amazon.com/')
    await amazonDialog.getByRole('button', { name: 'Close', exact: true }).click()
    assert.equal(await page.getByRole('heading', { name: 'Audiomack', exact: true }).count(), 0)
    await picker.click()
    let menu = page.getByRole('listbox', { name: 'Add account', exact: true })
    await menu.waitFor()
    assert.equal(await menu.getByRole('option').count(), 25)
    assert.equal(await menu.getByRole('option', { name: 'SoundCloud', exact: true }).count(), 1)
    const providersWithMarks = [
      'Spotify', 'TIDAL', 'Qobuz', 'Deezer', 'Amazon Music', 'Apple Music', 'YouTube Music', 'SoundCloud',
      'Last.fm', 'ListenBrainz', 'Navidrome / Subsonic', 'Jellyfin', 'Emby', 'Plex', 'Mopidy', 'Lyrion Music Server',
      'Anghami', 'QQ Music', 'Audiomack', 'Gaana', 'JioSaavn', 'LINE MUSIC', 'NetEase Cloud Music', 'Pandora', 'Naver Vibe',
    ]
    async function verifyServiceMarks(listbox, theme) {
      const marks = await Promise.all(providersWithMarks.map(async name => {
        const mark = listbox.getByRole('option', { name, exact: true }).locator('img')
        const { src, colorScheme, outerPixelAlpha, hasArtwork } = await mark.evaluate(async img => {
          await img.decode()
          const canvas = document.createElement('canvas')
          canvas.width = canvas.height = 64
          const context = canvas.getContext('2d')
          context.drawImage(img, 0, 0, 64, 64)
          const pixels = context.getImageData(0, 0, 64, 64).data
          const outerPixelAlpha = [0, 63, 63 * 64, 64 * 64 - 1].map(i => pixels[i * 4 + 3])
          return {
            src: img.currentSrc,
            colorScheme: getComputedStyle(img).colorScheme,
            outerPixelAlpha,
            hasArtwork: pixels.some((value, index) => index % 4 === 3 && value === 255),
          }
        })
        assert.ok(src.startsWith('data:image/svg+xml') || (src.startsWith(base + '/') && src.endsWith('.svg')),
          `${name} uses a bundled SVG`)
        assert.equal(colorScheme, theme, `${name} follows SongMirror's theme`)
        assert.deepEqual(outerPixelAlpha, [0, 0, 0, 0], `${name} has transparent corners`)
        assert.ok(hasArtwork, `${name} has a visible mark`)
        return src
      }))
      assert.equal(new Set(marks).size, providersWithMarks.length, 'Every provider has distinct artwork')
      return marks
    }
    const darkMarks = await verifyServiceMarks(menu, 'dark')
    assert.equal(await search.evaluate(el => el === document.activeElement), true)
    await search.fill('fictional-provider')
    await page.getByText('No matching services', { exact: true }).waitFor()
    await search.press('Enter')
    assert.equal(profiles.length, 0)
    await search.fill('vibe')
    assert.deepEqual(await menu.getByRole('option').allTextContents(), ['Naver Vibe'])
    await search.press('Escape')
    assert.equal(await picker.evaluate(el => el === document.activeElement), true)
    assert.equal(await picker.getAttribute('aria-expanded'), 'false')
    const screenshotDir = process.env.SONGMIRROR_E2E_SCREENSHOTS
    if (screenshotDir) fs.mkdirSync(screenshotDir, { recursive: true })
    for (const width of [1280, 375, 320]) {
      await page.setViewportSize({ width, height: 812 })
      await picker.click()
      menu = page.getByRole('listbox', { name: 'Add account', exact: true })
      await menu.waitFor()
      await menu.getByRole('option', { name: 'Navidrome / Subsonic', exact: true }).scrollIntoViewIfNeeded()
      const box = await menu.boundingBox()
      assert.ok(box.x >= 0 && box.x + box.width <= width, 'Provider menu fits the viewport')
      assert.ok(box.y >= 0 && box.y + box.height <= 812, 'Provider menu fits vertically')
      assert.equal(await menu.locator('img').evaluateAll(images => images.every(img => img.complete && img.naturalWidth > 0)), true)
      if (width < 768) {
        assert.ok((await menu.getByRole('option').first().boundingBox()).height >= 44)
      }
      if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, `provider-icons-${width}.png`), fullPage: true })
      await page.getByRole('heading', { name: 'Accounts', exact: true }).click()
      await menu.waitFor({ state: 'hidden' })
    }
    await page.setViewportSize({ width: 1280, height: 1000 })
    await picker.press('ArrowDown')
    await search.fill('listen')
    await search.press('Enter')
    const setup = page.getByRole('dialog', { name: /^Connect ListenBrainz · / })
    await setup.waitFor()
    assert.deepEqual(profiles, [{ provider: 'listenbrainz', label: '', reuse_default: true }])
    const name = setup.getByRole('textbox', { name: 'Profile label', exact: true })
    await name.fill('  GAANA  ')
    await setup.getByRole('button', { name: 'Save', exact: true }).click()
    await setup.getByText('That profile name is already in use.', { exact: true }).waitFor()
    await name.fill('Test listener')
    await setup.getByRole('button', { name: 'Save', exact: true }).click()
    await setup.getByRole('heading', { name: 'Connect ListenBrainz · Test listener', exact: true }).waitFor()
    await setup.getByRole('button', { name: 'Close', exact: true }).click()
    await page.evaluate(() => localStorage.setItem('songmirror-theme', 'light'))
    await page.reload()
    await picker.click()
    menu = page.getByRole('listbox', { name: 'Add account', exact: true })
    assert.deepEqual(await verifyServiceMarks(menu, 'light'), darkMarks)
    if (screenshotDir) {
      await menu.getByRole('option', { name: 'Naver Vibe', exact: true }).scrollIntoViewIfNeeded()
      await page.screenshot({ path: path.join(screenshotDir, 'provider-icons-light.png'), fullPage: true })
    }
    await search.press('Escape')
    await picker.click()
    await menu.getByRole('option', { name: 'Audiomack', exact: true }).click()
    const audioSetup = page.getByRole('dialog', { name: 'Connect Audiomack', exact: true })
    await audioSetup.getByText('v1/user/playlists', { exact: true }).waitFor()
    assert.equal(await audioSetup.getByRole('link', { name: 'web player', exact: true }).getAttribute('href'),
      'https://audiomack.com/my-library/playlists')
    const audioRequest = "curl 'https://api.audiomack.com/v1/user/playlists/page/1?oauth_consumer_key=audiomack-web&oauth_token=fixture-token-123456&oauth_signature=fixture-signature'"
    const signingCookie = 'fixture-secret-123456'
    await audioSetup.getByRole('textbox', { name: 'Signed-in playlist request' }).fill(audioRequest)
    await audioSetup.getByLabel('Signing cookie', { exact: true }).fill(signingCookie)
    const audioResponse = page.waitForResponse(response => response.url().endsWith('/audiomack/playlist-browser'))
    const audioCard = page.locator('[data-tour="account-card"]').filter({
      has: page.getByRole('heading', { name: 'Audiomack', exact: true }),
    })
    let releaseAccountsRefresh
    holdAccountsRefresh = new Promise(resolve => { releaseAccountsRefresh = resolve })
    try {
      await audioSetup.getByRole('button', { name: 'Connect account', exact: true }).click()
      assert.deepEqual((await audioResponse).request().postDataJSON(), { request: audioRequest, signing_cookie: signingCookie })
      await audioSetup.waitFor({ state: 'hidden' })
      await audioCard.getByRole('status').filter({ hasText: 'Updating account…' }).waitFor()
    } finally {
      holdAccountsRefresh = undefined
      releaseAccountsRefresh()
    }
    await audioCard.getByText('Connected', { exact: true }).waitFor()
    assert.ok((await connected.boundingBox()).y < (await audioCard.boundingBox()).y)
    await audioCard.getByRole('button', { name: 'Remove', exact: true }).click()
    const confirm = page.getByRole('dialog', { name: 'Remove Audiomack?', exact: true })
    await confirm.getByRole('button', { name: 'Cancel', exact: true }).click()
    assert.deepEqual(removals, [], 'Cancelling keeps the account')
    await audioCard.getByRole('button', { name: 'Remove', exact: true }).click()
    await confirm.getByRole('button', { name: 'Remove profile', exact: true }).click()
    await audioCard.waitFor({ state: 'detached' })
    assert.deepEqual(removals, ['audiomack'])
    await page.reload()
    assert.equal(await page.getByRole('heading', { name: 'Audiomack', exact: true }).count(), 0)
    console.log('PASS: provider marks, search, keyboard setup, unique profile names, signed-in Audiomack setup, and confirmed removal')
    await page.goto(base)
    const roster = page.getByRole('heading', { name: 'Your services', exact: true }).locator('../..')
    await roster.getByText('SoundCloud', { exact: true }).waitFor()
    assert.equal(await roster.getByText('Audiomack', { exact: true }).count(), 0)
    assert.equal(await page.getByText("Audiomack isn't set up", { exact: true }).count(), 0)
    const listedCount = accounts.filter(account => account.show_in_accounts).length
    const connectedCount = accounts.filter(account => account.show_in_accounts && account.state === 'connected').length
    await page.getByText(`${connectedCount} of ${listedCount} up to date`, { exact: true }).waitFor()
    await page.getByRole('button', { name: "What's new Unread updates", exact: true }).click()
    const updates = page.getByRole('dialog', { name: "What's new", exact: true })
    await updates.getByText('Audiomack', { exact: true }).waitFor()
    await updates.getByRole('button', { name: 'Close', exact: true }).click()
    await page.reload()
    await page.getByRole('button', { name: "What's new", exact: true }).waitFor()
    await page.goto(base + '/accounts')
    console.log("PASS: Accounts puts attention first, links Amazon Music, and shows connection refresh progress. The dashboard omits unadded services and marks viewed updates as read.")
    const cloudCard = page.locator('[data-tour="account-card"]').filter({ has: page.getByRole('heading', { name: 'SoundCloud', exact: true }) })
    await cloudCard.getByRole('button', { name: 'Connect', exact: true }).click()
    const cloudDialog = page.getByRole('dialog')
    await cloudDialog.getByText(base + '/oauth/soundcloud/callback', { exact: true }).waitFor()
    assert.equal(await cloudDialog.locator('input[type="password"]').count(), 0)
    assert.equal(await cloudDialog.getByRole('button', { name: 'Save and continue' }).isEnabled(), true)
    await cloudDialog.getByText('No-quota mode', { exact: true }).click()
    await cloudDialog.getByText('/me/library/all', { exact: true }).waitFor()
    const browserRequest = "curl 'https://api-v2.soundcloud.com/me/library/all?client_id=mock-app' -H 'authorization: OAuth mock-token'"
    const pageRequest = "curl 'https://soundcloud.com/you/sets' -b 'site_session=mock-session'"
    await cloudDialog.getByRole('textbox', { name: 'Raw request headers' }).fill(browserRequest)
    assert.equal(await cloudDialog.getByRole('button', { name: 'Enable no-quota mode' }).isDisabled(), true)
    await cloudDialog.getByRole('textbox', { name: 'SoundCloud playlist page request' }).fill(pageRequest)
    const enableResponse = page.waitForResponse(r => r.url().endsWith('/cloud/soundcloud/browser') && r.request().method() === 'POST')
    await cloudDialog.getByRole('button', { name: 'Enable no-quota mode' }).click()
    assert.deepEqual((await enableResponse).request().postDataJSON(), { headers: browserRequest, page_request: pageRequest })
    await cloudDialog.getByText('No-quota mode is on.', { exact: true }).waitFor()
    await cloudDialog.getByRole('button', { name: 'Switch back to OAuth' }).click()
    await cloudDialog.getByRole('button', { name: 'Enable no-quota mode' }).waitFor()
    await page.keyboard.press('Escape')
    await cloudDialog.waitFor({ state: 'hidden' })
    for (const [name, provider, hint] of guideSteps) {
      const card = page.locator('[data-tour="account-card"]').filter({ has: page.getByRole('heading', { name, exact: true }) })
      await card.getByRole('button', { name: 'Connect', exact: true }).click()
      const dialog = page.getByRole('dialog')
      const guide = dialog.locator('details[open]').filter({ hasText: 'How to get these' })
      assert.equal(await guide.getByText(hint, { exact: false }).first().isVisible(), true)
      if (provider === 'qqmusic') {
        await dialog.getByText('No-quota mode', { exact: true }).click()
        const playlist = 'https://y.qq.com/n/ryqq/playlist/7256912512'
        await dialog.getByRole('textbox', { name: 'Playlist link' }).fill(playlist)
        const savedMode = page.waitForResponse(r => r.url().endsWith('/qqmusic/qqmusic/browser') && r.request().method() === 'POST')
        await dialog.getByRole('button', { name: 'Enable no-quota mode' }).click()
        assert.deepEqual((await savedMode).request().postDataJSON(), { url: playlist })
        await dialog.getByText('No-quota mode is on.', { exact: true }).waitFor()
        await dialog.getByRole('button', { name: 'Switch back to API access' }).click()
        await dialog.getByRole('button', { name: 'Enable no-quota mode' }).waitFor()
      }
      await page.keyboard.press('Escape')
      await dialog.waitFor({ state: 'hidden' })
    }
    const gaanaCard = page.locator('[data-tour="account-card"]').filter({ has: page.getByRole('heading', { name: 'Gaana', exact: true }) })
    await gaanaCard.getByRole('button', { name: 'Connect', exact: true }).click()
    const publicDialog = page.getByRole('dialog')
    await publicDialog.locator('details[open]').getByText('Open a public playlist in your browser', { exact: false }).waitFor()
    assert.equal(await publicDialog.locator('input[type="password"]').count(), 0)
    assert.equal(await publicDialog.getByRole('button', { name: 'Connect', exact: true }).isDisabled(), true)
    const gaanaUrl = 'https://gaana.com/playlist/gaana-dj-gaana-international-top-50'
    await publicDialog.getByRole('textbox', { name: 'Public playlist link' }).fill(gaanaUrl)
    await publicDialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await publicDialog.getByRole('status').filter({ hasText: 'Gaana is connected.' }).waitFor()
    await publicDialog.waitFor({ state: 'hidden' })
    assert.deepEqual(connections.pop(), { provider: 'gaana', values: { GAANA_PUBLIC_PLAYLIST: gaanaUrl } })
    await gaanaCard.getByRole('button', { name: 'Reconnect', exact: true }).click()
    await publicDialog.getByText('myplaylists', { exact: true }).waitFor()
    assert.equal(await publicDialog.getByRole('link', { name: 'web player', exact: true }).getAttribute('href'),
      'https://gaana.com/music')
    assert.equal(await publicDialog.getByRole('button', { name: 'Connect account', exact: true }).isDisabled(), true)
    const privateRequest = "curl 'https://api.gaana.com/user.php?type=myplaylists&token=local-fixture-token'"
    await publicDialog.getByRole('textbox', { name: 'Signed-in playlist request' }).fill(privateRequest)
    const privateResponse = page.waitForResponse(r => r.url().endsWith('/gaana/playlist-browser'))
    await publicDialog.getByRole('button', { name: 'Connect account', exact: true }).click()
    assert.deepEqual((await privateResponse).request().postDataJSON(), { request: privateRequest })
    await publicDialog.waitFor({ state: 'hidden' })
    const lovesCard = page.locator('[data-tour="account-card"]').filter({ has: page.getByRole('heading', { name: 'ListenBrainz', exact: true }) })
    const localCard = page.locator('[data-tour="account-card"]').filter({ has: page.getByRole('heading', { name: 'Navidrome / Subsonic', exact: true }) })
    await lovesCard.getByRole('button', { name: 'Connect', exact: true }).click()
    let dialog = page.getByRole('dialog')
    assert.equal(await dialog.getByLabel('Password', { exact: false }).count(), 0)
    await dialog.getByLabel('Username', { exact: false }).fill('listener')
    await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await dialog.getByRole('status').filter({ hasText: 'ListenBrainz is connected.' }).waitFor()
    await dialog.waitFor({ state: 'hidden' })

    await localCard.getByRole('button', { name: 'Connect', exact: true }).click()
    dialog = page.getByRole('dialog')
    await dialog.getByLabel('Server URL', { exact: false }).fill('https://music.example/navidrome')
    await dialog.getByLabel('Username', { exact: false }).fill('listener')
    const password = dialog.getByLabel('Password', { exact: false })
    assert.equal(await password.getAttribute('type'), 'password')
    await password.fill('secret')
    await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await dialog.getByRole('status').filter({ hasText: 'Navidrome / Subsonic is connected.' }).waitFor()
    await dialog.waitFor({ state: 'hidden' })
    assert.deepEqual(connections, [
      { provider: 'listenbrainz', values: { LISTENBRAINZ_USER: 'listener', LISTENBRAINZ_TOKEN: '' } },
      { provider: 'subsonic', values: { SUBSONIC_URL: 'https://music.example/navidrome', SUBSONIC_USER: 'listener', SUBSONIC_PASSWORD: 'secret' } },
    ])
    console.log('PASS: username-only ListenBrainz setup and masked Subsonic password setup')

    await page.goto(base + '/sync')
    await page.getByRole('button', { name: 'New sync', exact: true }).first().click()
    dialog = page.getByRole('dialog')
    await dialog.getByLabel('Name', { exact: false }).fill('Independent favorites')
    await dialog.getByRole('radio', { name: 'ListenBrainz', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    const loved = dialog.getByRole('checkbox', { name: 'ListenBrainz Loved Recordings', exact: true })
    assert.equal(await loved.isChecked(), false, 'A ListenBrainz source no longer forces a loves-only job')
    await loved.locator('..').click()
    assert.equal(await loved.isChecked(), true)
    assert.equal(await dialog.getByRole('switch', { name: 'Also sync every regular playlist', exact: false }).isChecked(), false)
    assert.equal(await dialog.getByRole('radio', { name: 'Use Navidrome / Subsonic Starred Songs', exact: true }).isChecked(), true)
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 1000 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    }
    if (screenshotDir) {
      fs.mkdirSync(screenshotDir, { recursive: true })
      await page.screenshot({ path: path.join(screenshotDir, 'listenbrainz-sync-mobile.png'), fullPage: true })
    }
    await dialog.getByRole('button', { name: 'Create sync', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(saved.length, 1)
    assert.equal(saved[0].source, 'loves')
    assert.equal(saved[0].sync_playlists, false)
    assert.equal(saved[0].liked_tracks, true)
    assert.deepEqual(saved[0].liked_routes, { local: { kind: 'native' } })
    await page.getByText(/One-way · ListenBrainz → Navidrome \/ Subsonic/).first().waitFor()
    await page.goto(base + '/')
    await page.getByText(/One-way · ListenBrainz → Navidrome \/ Subsonic/).first().waitFor()
    assert.deepEqual(errors, [])
    console.log('PASS: ListenBrainz loves route saves correctly and both sync summaries retain the source name')

    for (const cached of [true, false]) {
      const context = await browser.newContext()
      if (cached) {
        await context.addInitScript(rows => localStorage.setItem('songmirror-cache-v2:accounts', JSON.stringify({
          version: 2, savedAt: Date.now(), data: rows,
        })), accounts)
      }
      const probe = await context.newPage()
      probe.on('pageerror', error => errors.push(error.message))
      let releaseAccounts
      const gate = new Promise(resolve => { releaseAccounts = resolve })
      let submitted
      await probe.route('**/api/**', async route => {
        const request = route.request(), url = new URL(request.url())
        const send = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
        if (url.pathname === '/api/accounts') {
          await gate
          return send(accounts.map(account => ({ ...account, detail: 'Rechecked connection' })))
        }
        if (url.pathname === '/api/syncs' && request.method() === 'POST') {
          submitted = request.postDataJSON()
          return send({ id: 'delayed-accounts', ...submitted })
        }
        if (url.pathname === '/api/sync/status') return send({ jobs: [], running: false })
        if (['/api/syncs', '/api/links', '/api/playlist-backups'].includes(url.pathname)
          || url.pathname.startsWith('/api/playlists')) return send([])
        return send({})
      })
      await probe.route('**/events*', route => route.fulfill({ contentType: 'text/event-stream', body: '' }))
      try {
        await probe.goto(base + '/sync')
        await probe.getByRole('button', { name: 'New sync', exact: true }).first().click()
        const draft = probe.getByRole('dialog')
        await draft.getByLabel('Name', { exact: false }).fill('Keep this draft')
        await draft.getByRole('radio', { name: 'Schedule', exact: true }).click()
        await draft.getByRole('switch', { name: 'Active', exact: false }).click()
        releaseAccounts()
        await probe.waitForFunction(() => JSON.parse(localStorage.getItem('songmirror-cache-v2:accounts'))?.data[0].detail === 'Rechecked connection')
        await probe.evaluate(() => new Promise(requestAnimationFrame))
        assert.equal(await draft.getByLabel('Name', { exact: false }).inputValue(), 'Keep this draft')
        assert.equal(await draft.getByRole('radio', { name: 'Schedule', exact: true }).isChecked(), true)
        assert.equal(await draft.getByRole('switch', { name: 'Active', exact: false }).isChecked(), false)
        await draft.getByRole('radio', { name: 'Direction', exact: true }).click()
        await draft.getByRole('radio', { name: 'ListenBrainz', exact: true }).click()
        await draft.getByRole('radio', { name: 'Playlists', exact: true }).click()
        await draft.getByRole('checkbox', { name: 'ListenBrainz Loved Recordings', exact: true }).locator('..').click()
        await draft.getByRole('button', { name: 'Create sync', exact: true }).click()
        await draft.waitFor({ state: 'hidden' })
        assert.equal(submitted.name, 'Keep this draft')
        assert.equal(submitted.enabled, false)
        assert.equal(submitted.source, 'loves')
        assert.deepEqual(submitted.liked_routes, { local: { kind: 'native' } })
        console.log(`PASS: ${cached ? 'cached account refresh' : 'initial account load'} preserves the sync draft, step and schedule`)
      } finally {
        releaseAccounts()
        await context.close()
      }
    }

    await page.goto(base + '/accounts')
    await lovesCard.getByRole('button', { name: 'Reconnect', exact: true }).click()
    dialog = page.getByRole('dialog')
    let token = dialog.getByLabel('User token', { exact: false })
    assert.equal(await token.getAttribute('type'), 'password')
    assert.equal(await token.getAttribute('required'), null)
    await token.fill('wrong-profile-token')
    await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await dialog.getByText('ListenBrainz token belongs to a different username.', { exact: true }).waitFor()
    assert.equal(await dialog.isVisible(), true)
    await token.fill('test-user-token')
    await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
    await lovesCard.getByRole('button', { name: 'Reconnect', exact: true }).click()
    dialog = page.getByRole('dialog')
    token = dialog.getByLabel('User token', { exact: false })
    assert.equal(await token.inputValue(), '')
    assert.equal(await token.getAttribute('placeholder'), 'saved — leave blank to keep')
    await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
    assert.deepEqual(connections.at(-1).values, { LISTENBRAINZ_USER: 'listener' }, 'Blank reconnect must not erase a saved token')
    console.log('PASS: optional masked token, visible wrong-profile error, and saved-token reconnect')

    accounts.push({ ...accounts[1], id: 'tidal', provider: 'tidal', name: 'TIDAL', provider_name: 'TIDAL',
      fields: [], state: 'connected' })
    await page.goto(base + '/sync')
    await page.getByRole('button', { name: 'New sync', exact: true }).first().click()
    dialog = page.getByRole('dialog')
    await dialog.getByLabel('Name', { exact: false }).fill('TIDAL favorites to ListenBrainz')
    await dialog.getByRole('radio', { name: 'TIDAL', exact: true }).click()
    await dialog.getByRole('radio', { name: 'Services', exact: true }).click()
    // With a token, ListenBrainz is a full playlist peer and joins by default.
    assert.equal(await dialog.getByRole('button', { name: 'ListenBrainz', exact: true }).getAttribute('aria-pressed'), 'true')
    await dialog.getByRole('radio', { name: 'Playlists', exact: true }).click()
    await dialog.getByRole('checkbox', { name: 'TIDAL Favorite Tracks', exact: true }).locator('..').click()
    const lovesRoute = dialog.getByRole('radio', { name: 'Use ListenBrainz Loved Recordings', exact: true })
    assert.equal(await lovesRoute.isChecked(), true)
    assert.equal(await lovesRoute.isEnabled(), true)
    assert.equal(await dialog.getByText('ListenBrainz has no playlists, so its own collection is the only destination.', { exact: true }).count(), 0)
    assert.equal(await dialog.getByRole('radio', { name: 'Create a new playlist on ListenBrainz', exact: true }).count(), 1)
    for (const width of [1280, 375]) {
      await page.setViewportSize({ width, height: 1000 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, `listenbrainz-destination-${width}.png`), fullPage: true })
    }
    await dialog.getByRole('button', { name: 'Create sync', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(saved.at(-1).source, 'tidal')
    assert.equal(saved.at(-1).sync_playlists, false)
    assert.equal(saved.at(-1).liked_tracks, true)
    assert.deepEqual(saved.at(-1).liked_routes.loves, { kind: 'native' })
    console.log('PASS: TIDAL favorites route to ListenBrainz loves, with a named playlist also offered')
    assert.deepEqual(errors, [])
  } finally {
    await page.close()
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
