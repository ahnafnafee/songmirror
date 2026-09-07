import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

export const frontendRoot = fileURLToPath(new URL('../', import.meta.url))
export const localeDir = path.join(frontendRoot, 'src/i18n/locales')

export function sourceFiles(directory = path.join(frontendRoot, 'src')) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(filename) : /\.tsx?$/.test(entry.name) ? [filename] : []
  })
}

export function literal(node) {
  if (!node) return undefined
  if (ts.isStringLiteralLike(node)) return node.text
  if (ts.isJsxExpression(node)) return literal(node.expression)
  return undefined
}

function properties(node) {
  if (!node || !ts.isObjectLiteralExpression(node)) return {}
  return Object.fromEntries(node.properties.filter(ts.isPropertyAssignment).map((property) => [property.name.getText().replace(/^['"]|['"]$/g, ''), property.initializer]))
}

// Read only literal UI metadata from the backend connector definitions. This
// neither imports Python modules nor reads any saved account configuration.
export function accountFieldMessages() {
  const directory = path.resolve(frontendRoot, '../songmirror/services/accounts')
  const result = new Set()
  for (const entry of fs.readdirSync(directory).filter((name) => name.endsWith('.py'))) {
    const source = fs.readFileSync(path.join(directory, entry), 'utf8')
    const starts = [...source.matchAll(/\bField\(/g)]
    for (const start of starts) {
      let depth = 1
      let quote = ''
      let escaped = false
      let argument = ''
      const args = []
      for (let i = start.index + start[0].length; i < source.length; i++) {
        const char = source[i]
        if (quote) {
          argument += char
          if (escaped) escaped = false
          else if (char === '\\') escaped = true
          else if (char === quote) quote = ''
        } else if (char === '"' || char === "'") {
          quote = char
          argument += char
        } else if (char === '(') {
          depth++
          argument += char
        } else if (char === ')') {
          depth--
          if (depth === 0) { args.push(argument); break }
          argument += char
        } else if (char === ',' && depth === 1) {
          args.push(argument)
          argument = ''
        } else argument += char
      }
      for (const value of [args[1], ...args.filter((arg) => /^\s*(?:label|help)\s*=/.test(arg))]) {
        if (!value) continue
        const strings = [...value.matchAll(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g)].map(([raw]) =>
          raw.slice(1, -1).replace(/\\([\\'"nrt])/g, (_, char) => ({ n: '\n', r: '\r', t: '\t' })[char] ?? char),
        )
        if (strings.length) result.add(strings.join(''))
      }
    }
  }
  return [...result]
}

export function collectMessages() {
  const messages = new Map()
  const locations = new Map()
  function add(key, value, filename, node) {
    if (!key?.trim()) return
    if (messages.has(key) && messages.get(key) !== value) throw new Error(`Conflicting defaults for ${key}`)
    messages.set(key, value)
    if (filename && node) {
      const line = node.getSourceFile().getLineAndCharacterOfPosition(node.getStart()).line + 1
      locations.set(key, `${path.relative(frontendRoot, filename)}:${line}`)
    }
  }
  for (const filename of sourceFiles()) {
    const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true)
    function visit(node) {
      if (ts.isCallExpression(node) && (node.expression.getText(source) === 't' || node.expression.getText(source) === 'i18n.t')) {
        const key = literal(node.arguments[0])
        if (key) {
          const options = properties(node.arguments[1])
          add(key, literal(options.defaultValue) ?? key, filename, node)
          for (const [name, value] of Object.entries(options)) {
            if (/^defaultValue_(zero|one|two|few|many|other)$/.test(name)) {
              add(`${key}_${name.slice('defaultValue_'.length)}`, literal(value) ?? key, filename, node)
            }
          }
        }
      }
      if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && node.tagName.getText(source) === 'Trans') {
        const attrs = Object.fromEntries(node.attributes.properties.filter(ts.isJsxAttribute).map((attr) => [attr.name.getText(), attr.initializer]))
        const key = literal(attrs.i18nKey)
        if (key) add(key, literal(attrs.defaults) ?? key, filename, node)
      }
      ts.forEachChild(node, visit)
    }
    visit(source)
  }
  for (const text of accountFieldMessages()) add(text, text)
  return { messages: Object.fromEntries([...messages].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)), locations }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { messages } = collectMessages()
  fs.mkdirSync(localeDir, { recursive: true })
  fs.writeFileSync(path.join(localeDir, 'en.json'), `${JSON.stringify(messages, null, 2)}\n`)
  console.log(`Extracted ${Object.keys(messages).length} English messages`)
}
