import { cp, mkdir, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { indexNowKey, searchPages, sitemapUrl, siteUrl } from './search.mjs'

const site = new URL('./', import.meta.url)
const repo = new URL('../', site)
const output = new URL('dist/', site)
const assets = new URL('assets/', output)
const projectAssets = new URL('.github/assets/', repo)
const logoAssets = new URL('frontend/src/assets/providers/', repo)
const repoUrl = 'https://github.com/ahnafnafee/songmirror'
const require = createRequire(new URL('frontend/package.json', repo))
const { createElement } = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const {
  SiApplemusic, SiCaprover, SiDeezer, SiJellyfin, SiLastdotfm, SiPortainer,
  SiRender, SiSoundcloud, SiSpotify, SiTidal, SiYoutubemusic,
} = require('react-icons/si')
const providerIcons = {
  spotify: SiSpotify,
  apple: SiApplemusic,
  youtube: SiYoutubemusic,
  tidal: SiTidal,
  deezer: SiDeezer,
  soundcloud: SiSoundcloud,
  lastfm: SiLastdotfm,
  jellyfin: SiJellyfin,
  render: SiRender,
  caprover: SiCaprover,
  portainer: SiPortainer,
}
const providerImages = {
  qobuz: new URL('qobuz.svg', logoAssets),
  amazon: new URL('src/amazon-music.png', site),
  listenbrainz: new URL('listenbrainz.svg', logoAssets),
  navidrome: new URL('navidrome.svg', logoAssets),
}

const [template, readme, registry, trailerHtml, cueText] = await Promise.all([
  readFile(new URL('src/index.html', site), 'utf8'),
  readFile(new URL('README.md', repo), 'utf8'),
  readFile(new URL('frontend/src/i18n/languages.ts', repo), 'utf8'),
  readFile(new URL('src/trailer.html', site), 'utf8'),
  readFile(new URL('promo/cues.json', repo), 'utf8'),
])

const quickStart = readme.split('<a id="quick-start"></a>')[1]
const commands = quickStart?.match(/^\x60{3}bash\r?\n([\s\S]+?)\r?\n\x60{3}/m)?.[1]
if (!commands) throw new Error('README Quick Start is missing its Docker Compose commands')

const escapeHtml = (text) => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
const languages = [...registry.matchAll(/\{\s*code: '([a-z]+)', label: '([^']+)'\s*\}/g)]
const guides = languages.map(([, code, name]) => {
  const path = code === 'en' ? 'README.md' : `docs/i18n/README.${code}.md`
  const direction = code === 'ar' ? ' dir="rtl"' : ''
  return `<li><a href="${repoUrl}/blob/main/${path}" lang="${code}" hreflang="${code}"${direction}>${escapeHtml(name)}</a></li>`
}).join('\n            ')
if (!guides) throw new Error('The language registry is empty')

function providerLogo(_marker, provider) {
  const icon = providerIcons[provider]
  if (icon) return renderToStaticMarkup(createElement(icon, { className: 'service-logo', 'aria-hidden': true, focusable: false }))
  if (!providerImages[provider]) throw new Error(`Unknown service logo ${provider}`)
  const filename = providerImages[provider].pathname.split('/').pop()
  return `<img class="service-logo" src="/assets/${filename}" width="17" height="17" alt="">`
}

const trailer = new URL('trailer/', output)
const deploy = new URL('deploy/', output)
await Promise.all([assets, trailer, deploy].map((dir) => mkdir(dir, { recursive: true })))

const cues = JSON.parse(cueText)
const seconds = (beat) => beat * 60 / cues.bpm
const duration = seconds(cues.beats)
const timecode = (beat) => new Date(Math.round(seconds(beat) * 1000)).toISOString().slice(11, 23)
const captionBlocks = cues.scenes.map(({ beat, caption, id }, index) => {
  const end = id === 'host' ? cues.breakBeat : (cues.scenes[index + 1]?.beat ?? cues.beats)
  return `${timecode(beat)} --> ${timecode(end)}\n${caption}`
})
const captions = 'WEBVTT\n\n' + captionBlocks.join('\n\n') + '\n'

const trailerVideo = `<video:video>
      <video:thumbnail_loc>${siteUrl}assets/trailer-poster.webp</video:thumbnail_loc>
      <video:title>SongMirror playlist sync and transfer trailer</video:title>
      <video:description>Preview scheduled playlist sync, one-time transfers, and the Jellyfin-ready music mirror.</video:description>
      <video:content_loc>${siteUrl}assets/songmirror-demo.mp4</video:content_loc>
      <video:duration>${Math.ceil(duration)}</video:duration>
    </video:video>`
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
  <url><loc>${searchPages[0]}</loc></url>
  <url><loc>${searchPages[1]}</loc>
    ${trailerVideo}
  </url>
</urlset>
`

await Promise.all([
  writeFile(new URL('index.html', output), template
    .replace('<!-- INSTALL_COMMANDS -->', () => escapeHtml(commands))
    .replace('<!-- LANGUAGE_GUIDES -->', () => guides)
    .replace(/<!-- logo:([a-z]+) -->/g, providerLogo)),
  writeFile(new URL('sitemap.xml', output), sitemap),
  writeFile(new URL('robots.txt', output), `User-agent: *\nAllow: /\n\nSitemap: ${sitemapUrl}\n`),
  writeFile(new URL(`${indexNowKey}.txt`, output), indexNowKey + '\n'),
  writeFile(new URL('index.html', trailer), trailerHtml.replace('{{TRAILER_SECONDS}}', String(duration))),
  writeFile(new URL('trailer.en.vtt', assets), captions),
  ...['caprover.yml', 'portainer.yml'].map((name) => cp(new URL(`deploy/${name}`, repo), new URL(name, deploy))),
  ...['styles.css', 'install.js', '_headers'].map((name) => cp(new URL(`src/${name}`, site), new URL(name, output))),
  ...['mark.png', 'songmirror-preview.webp', 'social-preview.png', 'songmirror-demo.mp4', 'trailer-poster.webp'].map((name) => cp(new URL(name, projectAssets), new URL(name, assets))),
  ...Object.values(providerImages).map((source) => cp(source, new URL(source.pathname.split('/').pop(), assets))),
  cp(new URL('frontend/node_modules/@fontsource-variable/archivo/files/archivo-latin-wght-normal.woff2', repo), new URL('archivo.woff2', assets)),
  cp(new URL('frontend/node_modules/@fontsource-variable/archivo/LICENSE', repo), new URL('archivo-OFL.txt', assets)),
])
