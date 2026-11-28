import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const languageSource = readFileSync(new URL('../src/i18n/languages.ts', import.meta.url), 'utf8')
const languages = [...languageSource.matchAll(/\{\s*code:\s*['"]([^'"]+)['"],\s*label:\s*['"]([^'"]+)['"]\s*\}/g)]
  .map(([, code, label]) => ({ code, label }))
assert.equal(languages.length, 15, 'Expected the complete supported-language registry')

const readmeFor = (code) => code === 'en' ? 'README.md' : `docs/i18n/README.${code}.md`
const guideFor = (code) => code === 'en' ? 'docs/user-guide.md' : `docs/i18n/guide.${code}.md`
const normalized = (text) => text.replace(/\r\n/g, '\n')
const matches = (text, regex, group = 1) => [...text.matchAll(regex)].map((match) => match[group])
const sorted = (values) => [...values].sort()
const codeBlocks = (text) => matches(text, /^(```[^\n]*\n[\s\S]*?^```)[ \t]*$/gm)
const withoutCode = (text) => text.replace(/^```[^\n]*\n[\s\S]*?^```[ \t]*$/gm, '')
const translatableProse = (text) => withoutCode(text).replace(/^\|[^|\n]*\]\(https?:\/\/[^|\n]*\|/gm, '|')
const inlineCode = (text) => matches(withoutCode(text), /`([^`\n]+)`/g)
const anchorIds = (text) => matches(withoutCode(text), /<a\s+(?:id|name)="([^"]+)"[^>]*>/g)
const referenceLinks = (text) => new Map([...withoutCode(text).matchAll(/^\[([^\]]+)\]:\s*(\S+)/gm)]
  .map(([, label, target]) => [label.toLowerCase(), target]))
const brands = ['SongMirror', 'Spotify', 'TIDAL', 'Qobuz', 'Deezer', 'Amazon Music', 'Apple Music', 'YouTube Music', 'Jellyfin', 'Soundiiz', 'TuneMyMusic', 'FreeYourMusic', 'RapidFuzz', 'anyascii']

function phraseSignatures(text) {
  const prose = translatableProse(text).replace(/`[^`\n]*`/g, '')
    .replace(/^\[[^\]]+\]:.*$/gm, '')
    .replace(/<!-- LANGUAGE NAVIGATION -->[\s\S]*?<!-- \/LANGUAGE NAVIGATION -->/g, '')
    .replace(/<[^>]*>/g, '').replace(/\]\([^)]*\)/g, ']')
  const signatures = []
  for (let line of prose.split('\n')) {
    if (/^\[!\[/.test(line)) continue
    for (const brand of brands) line = line.replaceAll(brand, '')
    const words = line.match(/[A-Za-z]+(?:['’-][A-Za-z]+)*/g) || []
    for (let index = 0; index <= words.length - 8; index++) signatures.push(words.slice(index, index + 8).join(' ').toLowerCase())
  }
  return signatures
}

function destinations(text) {
  const content = withoutCode(text).replace(/`[^`\n]*`/g, '')
  return [
    ...matches(content, /\]\(([^)\s]+)\)/g),
    ...matches(content, /\b(?:href|src|srcset)="([^"]+)"/g),
    ...matches(content, /<(https?:\/\/[^>]+)>/g),
    ...referenceLinks(content).values(),
  ]
}

function resolveLink(file, target) {
  if (/^[a-z][a-z\d+.-]*:/i.test(target)) return target
  const [urlPath, fragment = ''] = target.split('#')
  const absolute = path.resolve(root, path.dirname(file), decodeURIComponent(urlPath || path.basename(file)))
  const relative = path.relative(root, absolute).replaceAll(path.sep, '/')
  assert(!relative.startsWith('../'), `${file}: link escapes repository: ${target}`)
  return `${relative}${fragment ? `#${decodeURIComponent(fragment)}` : ''}`
}

function comparableLink(file, target, code) {
  if (target.startsWith('#')) return target
  const resolved = resolveLink(file, target)
  const guide = guideFor(code)
  if (resolved === guide || resolved.startsWith(`${guide}#`)) {
    return '@user-guide' + resolved.slice(guide.length)
  }
  return resolved
}

function layout(text) {
  const body = withoutCode(text)
  return {
    headings: matches(body, /^(#{1,6})\s/gm),
    lists: matches(body, /^([ \t]*(?:\d+\.|-)[ \t])/gm),
    notices: matches(body, /^>\s*(\[![A-Z]+\])/gm),
    tables: body.split('\n').filter((line) => /^\|/.test(line))
      .map((line) => line.replace(/`[^`]+`/g, '').split('|').length),
  }
}

function sections(text) {
  return new Map([...text.matchAll(/<a id="([^"]+)"><\/a>\s*([\s\S]*?)(?=<a id="|<!-- LINK GROUP -->|$)/g)]
    .map(([, id, body]) => [id, withoutCode(body)]))
}

function verifyLinks(file, document, files, links) {
  const refs = referenceLinks(document)
  for (const ref of matches(withoutCode(document), /\[[^\]\n]*\]\[([^\]\n]+)\]/g)) {
    assert(refs.has(ref.toLowerCase()), `${file}: unresolved reference link [${ref}]`)
  }

  let checkedLinks = 0
  for (const target of links) {
    const resolved = resolveLink(file, target)
    if (/^[a-z][a-z\d+.-]*:/i.test(resolved)) continue
    const [destination, fragment] = resolved.split('#')
    const content = files.get(destination)
    assert(content !== undefined || existsSync(path.join(root, destination)), `${file}: broken local link ${target}`)
    if (fragment) {
      const linkedText = content ?? readFileSync(path.join(root, destination), 'utf8')
      assert(anchorIds(linkedText).includes(fragment), `${file}: broken section link ${target}`)
    }
    checkedLinks++
  }
  return checkedLinks
}

function verify(files, filenameFor) {
  const englishFile = filenameFor('en')
  const english = files.get(englishFile)
  assert(english, `${englishFile}: English reference is missing`)
  const englishAnchors = anchorIds(english)
  const englishSections = sections(english)
  const englishLinks = sorted(destinations(english).map((target) => comparableLink(englishFile, target, 'en')))
  const englishBlocks = codeBlocks(english)
  const englishInline = sorted(inlineCode(english))
  const englishLayout = layout(english)
  const englishPhrases = new Set(phraseSignatures(english))
  // Several locales translate both removal toggles alike, or one inside the other:
  // count distinct labels without overlap, longest first.
  const REMOVAL_LABELS = ['Mirror removals', 'Sync removals']
  const removalLabelCount = (text, labels) => {
    const distinct = [...new Set(labels)].sort((a, b) => b.length - a.length)
    const pattern = new RegExp(distinct.map((label) => label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g')
    return text.match(pattern)?.length ?? 0
  }
  const englishRemovalLabels = removalLabelCount(english, REMOVAL_LABELS)
  const longEnglishLines = new Set(translatableProse(english).split('\n')
    .filter((line) => line.length > 120 && !/^<|^\[|^<!--/.test(line)))
  let checkedLinks = 0

  for (const { code, label } of languages) {
    const file = filenameFor(code)
    const text = files.get(file)
    assert(text, `${file}: missing localized README`)
    assert(!/@@(?:DOC|LANGUAGE)|⟦|⟧|\b(?:TODO_TRANSLATE|TRANSLATION_PENDING|TBD|undefined)\b/.test(text), `${file}: untranslated placeholder`)
    assert.equal((text.match(/^```/gm) || []).length, englishBlocks.length * 2, `${file}: malformed code fences`)
    assert.deepEqual(codeBlocks(text), englishBlocks, `${file}: shell/configuration/code blocks differ from English`)
    assert.deepEqual(sorted(inlineCode(text)), englishInline, `${file}: command, option, or identifier differs from English`)
    assert.deepEqual(anchorIds(text), englishAnchors, `${file}: missing or reordered section anchors`)
    assert.equal(new Set(anchorIds(text)).size, englishAnchors.length, `${file}: duplicate anchor`)
    assert.deepEqual(layout(text), englishLayout, `${file}: heading, list, notice, or table structure differs from English`)
    for (const brand of brands) {
      assert.equal(text.split(brand).length, english.split(brand).length, `${file}: provider or project name changed: ${brand}`)
    }
    for (const line of withoutCode(text).split('\n')) {
      assert.equal((line.match(/\*\*/g) || []).length % 2, 0, `${file}: unbalanced bold markup`)
    }

    const navigation = text.match(/<!-- LANGUAGE NAVIGATION -->([\s\S]*?)<!-- \/LANGUAGE NAVIGATION -->/)?.[1]
    assert(navigation, `${file}: missing language navigation`)
    for (const language of languages) {
      const link = [...navigation.matchAll(/<a href="([^"]+)" lang="([^"]+)"[^>]*>([^<]+)<\/a>/g)]
        .find(([, , navCode]) => navCode === language.code)
      assert(link, `${file}: missing ${language.label} navigation`)
      assert.equal(link[3], language.label, `${file}: language name must use its native spelling`)
      assert.equal(resolveLink(file, link[1]), readmeFor(language.code), `${file}: wrong language destination`)
    }
    assert(text.includes(label), `${file}: native language name is missing`)

    const links = destinations(text)
    assert.deepEqual(sorted(links.map((target) => comparableLink(file, target, code))), englishLinks, `${file}: documentation links or asset destinations differ from English`)
    checkedLinks += verifyLinks(file, text, files, links)
    const localizedSections = sections(text)
    for (const [id, body] of englishSections) {
      const localized = localizedSections.get(id)
      assert(localized && localized.trim().length >= body.trim().length * 0.2, `${file}: section ${id} is missing or abbreviated`)
    }
    const catalog = JSON.parse(readFileSync(path.join(root, 'frontend/src/i18n/locales', `${code}.json`), 'utf8'))
    const languageGuide = localizedSections.get('app-language')
    const settingsPath = [catalog.Settings, catalog.General, catalog.Language].join(' → ')
    assert(languageGuide.includes(settingsPath), `${file}: Language setting path differs from the app`)
    assert(languageGuide.includes(catalog['Automatic (browser)']), `${file}: automatic language option differs from the app`)
    assert.equal(removalLabelCount(text, REMOVAL_LABELS.map((label) => catalog[label])), englishRemovalLabels, `${file}: deletion setting references must match the app`)
    if (code !== 'en') {
      for (const line of translatableProse(text).split('\n')) {
        assert(!longEnglishLines.has(line), `${file}: untranslated English paragraph: ${line.slice(0, 90)}`)
      }
      for (const phrase of phraseSignatures(text)) {
        assert(!englishPhrases.has(phrase), `${file}: untranslated English phrase: ${phrase}`)
      }
    }
    if (code === 'ar') assert(text.startsWith('<div lang="ar" dir="rtl">'), `${file}: Arabic reading direction is missing`)
  }
  return { documents: languages.length, checkedLinks }
}

const files = new Map(languages.flatMap(({ code }) => [readmeFor(code), guideFor(code)])
  .map((file) => [file, existsSync(path.join(root, file)) ? normalized(readFileSync(path.join(root, file), 'utf8')) : undefined]))
assert.deepEqual(
  sorted(readdirSync(path.join(root, 'docs/i18n')).filter((file) => /^(README|guide)\.[^.]+\.md$/.test(file))),
  sorted(languages.filter(({ code }) => code !== 'en').flatMap(({ code }) => [`README.${code}.md`, `guide.${code}.md`])),
  'Localized README and guide files must match the supported languages',
)
const overviewResult = verify(files, readmeFor)
const guideResult = verify(files, guideFor)

if (process.argv.includes('--self-test')) {
  const frenchReadme = readmeFor('fr')
  const frenchGuide = guideFor('fr')
  const checks = [
    ['broken overview link', readmeFor, (docs) => docs.set('README.md', docs.get('README.md') + '\n[Missing guide section](docs/user-guide.md#missing)\n')],
    ['missing translation', readmeFor, (docs) => docs.delete(frenchReadme)],
    ['changed command', readmeFor, (docs) => docs.set(frenchReadme, docs.get(frenchReadme).replace('docker compose up -d\n', 'docker compose down\n'))],
    ['broken language link', readmeFor, (docs) => docs.set(frenchReadme, docs.get(frenchReadme).replace('href="README.ar.md"', 'href="README.missing.md"'))],
    ['changed service link', readmeFor, (docs) => docs.set(frenchReadme, docs.get(frenchReadme).replace('https://open.spotify.com/', 'https://spotify.com/'))],
    ['guide in the wrong language', readmeFor, (docs) => docs.set(frenchReadme, docs.get(frenchReadme).replace('guide.fr.md#screenshots', 'guide.it.md#screenshots'))],
    ['English guide in a translation', readmeFor, (docs) => docs.set(frenchReadme, docs.get(frenchReadme).replace('guide.fr.md#screenshots', '../user-guide.md#screenshots'))],
    ['missing section', guideFor, (docs) => docs.set(frenchGuide, docs.get(frenchGuide).replace('<a id="safety-rails"></a>', ''))],
    ['untranslated placeholder', guideFor, (docs) => docs.set(frenchGuide, docs.get(frenchGuide) + '\n@@DOC123@@\n')],
    ['untranslated sentence', guideFor, (docs) => docs.set(frenchGuide, docs.get(frenchGuide) + '\nThe default source of truth is Spotify, but one-way mode is provider-agnostic.\n')],
    ['changed provider name', guideFor, (docs) => docs.set(frenchGuide, docs.get(frenchGuide).replace('Spotify, TIDAL', 'Spotifly, TIDAL'))],
  ]
  for (const [name, filenameFor, mutate] of checks) {
    const damaged = new Map(files)
    mutate(damaged)
    assert.throws(() => verify(damaged, filenameFor), undefined, `Negative control did not reject ${name}`)
  }
  console.log(`README checker negative controls passed (${checks.length})`)
}

console.log(`localized READMEs and guides verified: ${overviewResult.documents} languages, ${overviewResult.checkedLinks + guideResult.checkedLinks} local links`)
