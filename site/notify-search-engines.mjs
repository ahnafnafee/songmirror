import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { indexNowKey, keyLocation, searchPages, sitemapUrl, siteUrl } from './search.mjs'

const exec = promisify(execFile)
const doh = process.env.SONGMIRROR_DOH_URL

async function publishedText(url) {
  if (doh) {
    const { stdout } = await exec(process.platform === 'win32' ? 'curl.exe' : 'curl', [
      '--doh-url', doh, '--fail', '--silent', '--show-error', '--max-time', '20', url,
    ])
    return stdout
  }
  const response = await fetch(url, { signal: AbortSignal.timeout(20_000) })
  if (!response.ok) throw new Error(`Could not verify ${url} (HTTP ${response.status})`)
  return response.text()
}

const requested = [...new Set(process.argv.slice(2))]
const urls = requested.length ? requested : searchPages
if (urls.some((url) => !searchPages.includes(url))) {
  throw new Error('Submit only SongMirror pages listed in the sitemap')
}

const [key, sitemap] = await Promise.all([publishedText(keyLocation), publishedText(sitemapUrl)])
if (key.trim() !== indexNowKey || urls.some((url) => !sitemap.includes(`<loc>${url}</loc>`))) {
  throw new Error('The live IndexNow key or sitemap does not match this deployment')
}

const response = await fetch('https://api.indexnow.org/IndexNow', {
  method: 'POST',
  headers: { 'content-type': 'application/json; charset=utf-8' },
  body: JSON.stringify({ host: new URL(siteUrl).hostname, key: indexNowKey, keyLocation, urlList: urls }),
  signal: AbortSignal.timeout(25_000),
})
if (response.status !== 200 && response.status !== 202) {
  throw new Error(`IndexNow rejected the submission (HTTP ${response.status})`)
}
console.log(`IndexNow HTTP ${response.status} for ${urls.join(', ')}`)
if (response.status === 202) console.log('Accepted. IndexNow is still validating the key.')
