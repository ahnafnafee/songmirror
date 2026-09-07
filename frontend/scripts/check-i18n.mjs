import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { collectMessages, frontendRoot, literal, localeDir, sourceFiles } from './extract-i18n.mjs'

const languagesSource = fs.readFileSync(path.join(frontendRoot, 'src/i18n/languages.ts'), 'utf8')
const languages = [...languagesSource.matchAll(/code: '([a-z]+)'/g)].map((match) => match[1])
const expectedLanguages = ['en', 'ar', 'tr', 'es', 'zh', 'fr', 'pt', 'de', 'ja', 'hi', 'bn', 'id', 'ko', 'it', 'vi']
assert.deepEqual([...languages].sort(), expectedLanguages.sort(), 'The app must ship the same 15 languages as Player 2')

function tokens(value) {
  return [...value.matchAll(/\{\{[^{}]+\}\}|<\/?[A-Za-z][A-Za-z0-9]*\s*\/?>/g)].map(([token]) => token).sort()
}

function validateMessage(key, value, source) {
  assert.equal(typeof value, 'string', `${key}: expected a string`)
  assert.ok(value.trim(), `${key}: empty translation`)
  assert.deepEqual(tokens(value), tokens(source), `${key}: interpolation or rich-text components changed`)
  assert.ok(!/\uFFFD|ZXPH\d+|\[\[\[\d+\]\]\]/.test(value), `${key}: invalid characters or translation markers`)
  const withoutAllowedTags = value.replace(/<\/?[A-Za-z][A-Za-z0-9]*\s*\/?>/g, '')
  assert.ok(!/<[^>]*>/.test(withoutAllowedTags), `${key}: unexpected HTML or attributes`)
  const stack = []
  for (const [tag, slash, name, selfClosing] of value.matchAll(/<(\/?)([A-Za-z][A-Za-z0-9]*)(\s*\/?)>/g)) {
    if (selfClosing.includes('/')) continue
    if (!slash) stack.push(name)
    else assert.equal(stack.pop(), name, `${key}: misnested component ${tag}`)
  }
  assert.equal(stack.length, 0, `${key}: unclosed components`)
}

// Positive controls ensure the checks reject failures instead of merely finding
// nothing in the current catalogs.
assert.throws(() => validateMessage('control', 'Hola {{wrong}}', 'Hello {{name}}'))
assert.throws(() => validateMessage('control', '<b>Hola</i>', '<b>Hello</b>'))
assert.throws(() => validateMessage('control', '', 'Hello'))
assert.throws(() => validateMessage('control', '<link href="https://example.com">Hola</link>', '<link>Hello</link>'))

function untranslatedCopy(filename, text) {
  const source = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const issues = []
  function visit(node) {
    let copy
    if (ts.isJsxText(node)) {
      const parentTag = ts.isJsxElement(node.parent) ? node.parent.openingElement.tagName.getText(source) : ''
      // Code/header examples and displayed provider URLs deliberately keep their
      // exact spelling; ordinary prose and accessible labels need translations.
      if (!['Code', 'code', 'pre', 'GuideLink'].includes(parentTag)) copy = node.text.trim()
    } else if (ts.isJsxAttribute(node) && /^(?:title|label|help|placeholder|description|aria-label|ariaLabel|alt|emptyTitle|emptyDescription|caption)$/.test(node.name.getText(source))) {
      copy = literal(node.initializer)
    }
    if (copy && /\p{L}{2}/u.test(copy) && copy !== 'SongMirror') {
      const line = source.getLineAndCharacterOfPosition(node.getStart()).line + 1
      issues.push(`${path.relative(frontendRoot, filename)}:${line}: ${copy.slice(0, 100)}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return issues
}

assert.equal(untranslatedCopy('control.tsx', '<p>Hello there</p>').length, 1)
assert.equal(untranslatedCopy('control.tsx', '<button aria-label="Close" />').length, 1)
assert.equal(untranslatedCopy('control.tsx', '<p>{t("Hello there")}</p>').length, 0)
assert.equal(untranslatedCopy('control.tsx', '<Code>client_id</Code>').length, 0)
for (const file of sourceFiles().filter((filename) => filename.endsWith('.tsx'))) {
  const issues = untranslatedCopy(file, fs.readFileSync(file, 'utf8'))
  assert.equal(issues.length, 0, `Untranslated UI copy:\n${issues.join('\n')}`)
}

const en = JSON.parse(fs.readFileSync(path.join(localeDir, 'en.json'), 'utf8'))
const { messages: extracted } = collectMessages()
for (const [key, value] of Object.entries(extracted)) {
  assert.equal(en[key], value, `English catalog is stale for ${key}: run pnpm i18n:extract`)
}
for (const key of Object.keys(en)) assert.ok(Object.hasOwn(extracted, key), `Obsolete English message ${key}: run pnpm i18n:extract`)
assert.ok(Object.keys(en).length > 100, 'Expected complete application strings, not only navigation')
const pluralBases = Object.keys(en).filter((key) => key.endsWith('_other')).map((key) => key.slice(0, -6))
for (const language of languages) {
  const catalog = JSON.parse(fs.readFileSync(path.join(localeDir, `${language}.json`), 'utf8'))
  for (const [key, value] of Object.entries(en)) {
    assert.ok(Object.hasOwn(catalog, key), `${language}: missing ${key}`)
    validateMessage(`${language}: ${key}`, catalog[key], value)
  }
  const extraKeys = new Set()
  for (const base of pluralBases) {
    for (const category of new Intl.PluralRules(language).resolvedOptions().pluralCategories) {
      const key = `${base}_${category}`
      extraKeys.add(key)
      assert.ok(Object.hasOwn(catalog, key), `${language}: missing plural ${key}`)
      validateMessage(`${language}: ${key}`, catalog[key], en[key] ?? en[`${base}_other`])
    }
  }
  for (const key of Object.keys(catalog)) assert.ok(Object.hasOwn(en, key) || extraKeys.has(key), `${language}: obsolete key ${key}`)
  if (language !== 'en') {
    // Technical labels may be identical. Entire English copies cannot pass.
    const changed = Object.keys(en).filter((key) => catalog[key] !== en[key]).length
    assert.ok(changed / Object.keys(en).length > 0.75, `${language}: catalog is predominantly untranslated`)
  }
}
assert.deepEqual(fs.readdirSync(localeDir).filter((file) => file.endsWith('.json')).sort(), languages.map((language) => `${language}.json`).sort())
console.log(`i18n catalogs verified: ${languages.length} languages, ${Object.keys(en).length} English messages; placeholders, components, plurals, and extraction match`)
