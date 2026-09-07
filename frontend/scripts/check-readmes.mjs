import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const languageSource = readFileSync(new URL('../src/i18n/languages.ts', import.meta.url), 'utf8')
const languages = [...languageSource.matchAll(/\{\s*code:\s*['"]([^'"]+)['"],\s*label:\s*['"]([^'"]+)['"]\s*\}/g)]
  .map(([, code, label]) => ({ code, label }))
assert.equal(languages.length, 15, 'Expected the complete supported-language registry')

const filenameFor = (code) => code === 'en' ? 'README.md' : `docs/i18n/README.${code}.md`
const normalized = (text) => text.replace(/\r\n/g, '\n')
const matches = (text, regex, group = 1) => [...text.matchAll(regex)].map((match) => match[group])
const sorted = (values) => [...values].sort()
const codeBlocks = (text) => matches(text, /^(```[^\n]*\n[\s\S]*?^```)[ \t]*$/gm)
const withoutCode = (text) => text.replace(/^```[^\n]*\n[\s\S]*?^```[ \t]*$/gm, '')
const inlineCode = (text) => matches(withoutCode(text), /`([^`\n]+)`/g)
const anchorIds = (text) => matches(withoutCode(text), /<a\s+(?:id|name)="([^"]+)"[^>]*>/g)
const referenceLinks = (text) => new Map([...withoutCode(text).matchAll(/^\[([^\]]+)\]:\s*(\S+)/gm)]
  .map(([, label, target]) => [label.toLowerCase(), target]))
const brands = ['SongMirror', 'Spotify', 'TIDAL', 'Qobuz', 'Deezer', 'Amazon Music', 'Apple Music', 'YouTube Music', 'Jellyfin', 'Soundiiz', 'TuneMyMusic', 'FreeYourMusic', 'RapidFuzz', 'anyascii']

function phraseSignatures(text) {
  const prose = withoutCode(text).replace(/`[^`\n]*`/g, '')
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

const comparableLink = (file, target) => target.startsWith('#') ? target : resolveLink(file, target)

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

function verify(files) {
  const english = files.get('README.md')
  assert(english, 'English README is missing')
  const englishAnchors = anchorIds(english)
  const englishSections = sections(english)
  const englishLinks = sorted(destinations(english).map((target) => comparableLink('README.md', target)))
  const englishBlocks = codeBlocks(english)
  const englishInline = sorted(inlineCode(english))
  const englishLayout = layout(english)
  const englishPhrases = new Set(phraseSignatures(english))
  const englishRemovalLabels = english.split('Mirror removals').length - 1
  const longEnglishLines = new Set(withoutCode(english).split('\n')
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
      assert.equal(resolveLink(file, link[1]), filenameFor(language.code), `${file}: wrong language destination`)
    }
    assert(text.includes(label), `${file}: native language name is missing`)

    const refs = referenceLinks(text)
    for (const ref of matches(withoutCode(text), /\[[^\]\n]*\]\[([^\]\n]+)\]/g)) {
      assert(refs.has(ref.toLowerCase()), `${file}: unresolved reference link [${ref}]`)
    }
    const links = destinations(text)
    assert.deepEqual(sorted(links.map((target) => comparableLink(file, target))), englishLinks, `${file}: documentation links or asset destinations differ from English`)
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
    assert.equal(text.split(catalog['Mirror removals']).length - 1, englishRemovalLabels, `${file}: deletion setting references must match the app`)
    if (code !== 'en') {
      for (const line of withoutCode(text).split('\n')) {
        assert(!longEnglishLines.has(line), `${file}: untranslated English paragraph: ${line.slice(0, 90)}`)
      }
      for (const phrase of phraseSignatures(text)) {
        assert(!englishPhrases.has(phrase), `${file}: untranslated English phrase: ${phrase}`)
      }
    }
    if (code === 'ar') assert(text.startsWith('<div lang="ar" dir="rtl">'), `${file}: Arabic reading direction is missing`)
  }
  return { documents: languages.length, translations: languages.length - 1, sections: englishSections.size, codeBlocks: englishBlocks.length, checkedLinks }
}

const files = new Map(languages.map(({ code }) => {
  const file = filenameFor(code)
  return [file, existsSync(path.join(root, file)) ? normalized(readFileSync(path.join(root, file), 'utf8')) : undefined]
}))
assert.deepEqual(
  sorted(readdirSync(path.join(root, 'docs/i18n')).filter((file) => /^README\.[^.]+\.md$/.test(file))),
  sorted(languages.filter(({ code }) => code !== 'en').map(({ code }) => `README.${code}.md`)),
  'Localized README files must match the supported languages',
)
const result = verify(files)

if (process.argv.includes('--self-test')) {
  const checks = [
    ['missing translation', (docs) => docs.delete('docs/i18n/README.fr.md')],
    ['changed command', (docs) => docs.set('docs/i18n/README.fr.md', docs.get('docs/i18n/README.fr.md').replace('docker compose up -d\n', 'docker compose down\n'))],
    ['broken language link', (docs) => docs.set('docs/i18n/README.fr.md', docs.get('docs/i18n/README.fr.md').replace('href="README.ar.md"', 'href="README.missing.md"'))],
    ['missing section', (docs) => docs.set('docs/i18n/README.fr.md', docs.get('docs/i18n/README.fr.md').replace('<a id="safety-rails"></a>', ''))],
    ['untranslated placeholder', (docs) => docs.set('docs/i18n/README.fr.md', docs.get('docs/i18n/README.fr.md') + '\n@@DOC123@@\n')],
    ['untranslated sentence', (docs) => docs.set('docs/i18n/README.fr.md', docs.get('docs/i18n/README.fr.md') + '\nThe default source of truth is Spotify, but one-way mode is provider-agnostic.\n')],
    ['changed provider name', (docs) => docs.set('docs/i18n/README.fr.md', docs.get('docs/i18n/README.fr.md').replace('Spotify, TIDAL', 'Spotifly, TIDAL'))],
  ]
  for (const [name, mutate] of checks) {
    const damaged = new Map(files)
    mutate(damaged)
    assert.throws(() => verify(damaged), undefined, `Negative control did not reject ${name}`)
  }
  console.log(`README checker negative controls passed (${checks.length})`)
}

console.log(`localized READMEs verified: ${result.documents} languages (${result.translations} translations), ${result.sections} sections and ${result.codeBlocks} unchanged code blocks each, ${result.checkedLinks} local links`)
