const TYPE_LABELS = ['bug', 'enhancement', 'documentation', 'question']
const SECURITY = /\b(?:vulnerabilit(?:y|ies)|security (?:report|issue|bypass)|CVE-\d{4}|credential (?:leak|exposure))\b/i
const PROVIDERS = [
  ['Spotify', /\bspotify\b/i], ['Apple Music', /\bapple music\b/i],
  ['YouTube Music', /\byoutube(?: music)?\b/i], ['TIDAL', /\btidal\b/i],
  ['Deezer', /\bdeezer\b/i], ['Qobuz', /\bqobuz\b/i], ['Amazon Music', /\bamazon music\b/i],
  ['SoundCloud', /\bsoundcloud\b/i], ['Last.fm', /\blast[. ]fm\b/i],
  ['ListenBrainz', /\blistenbrainz\b/i], ['Navidrome / Subsonic', /\b(?:navidrome|subsonic)\b/i],
  ['Jellyfin', /\bjellyfin\b/i],
]
const AREAS = [
  ['deployment', /\b(?:docker|compose|portainer|caprover|container|render deploy)\b/i],
  ['transfers', /\b(?:transfers?|playlist copy|copy (?:a )?playlist)\b/i],
  ['sync', /\b(?:sync(?:ing|s)?|bidirectional|one-way)\b/i],
  ['playlist backups', /\b(?:playlist backups?|playlist (?:import|export))\b/i],
  ['local mirror', /\b(?:spotdl|ffmpeg|local mirror|offline downloads?)\b/i],
]
const LABEL_DETAILS = {
  bug: { color: 'd73a4a', description: 'Something is not working' },
  enhancement: { color: 'a2eeef', description: 'New feature or request' },
  documentation: { color: '0075ca', description: 'Documentation changes and corrections' },
  question: { color: 'd876e3', description: 'A question about the project' },
  security: { color: 'b60205', description: 'Potential security issue for a maintainer to review' },
  'needs-triage': { color: 'fbca04', description: 'Issue awaiting an initial maintainer review' },
}
const REPLY_MARKER = '<!-- songmirror-triage:diagnostics -->'

function fieldsIn(body) {
  const fields = new Map()
  for (const match of body.matchAll(/^#{2,6}[ \t]+([^\n]+)\n([\s\S]*?)(?=^#{2,6}[ \t]+|(?![\s\S]))/gm)) {
    const key = match[1].toLowerCase().replace(/\s*[:?]$/, '').trim()
    const value = match[2].trim()
    if (value && !/^(?:_?no response_?|none|n\/?a|not sure|unknown)$/i.test(value)) fields.set(key, value)
  }
  return fields
}

function classify(title, fields, labels) {
  const chosen = labels.find(label => TYPE_LABELS.includes(label))
  if (chosen) return chosen
  if (/^\s*(?:\[(?:bug|regression)\]|(?:bug|regression):)/i.test(title) ||
      (fields.has('steps to reproduce') && fields.has('what happened'))) return 'bug'
  if (/^\s*(?:\[(?:feature|enhancement)\]|(?:feature request|enhancement):)/i.test(title)) return 'enhancement'
  if (/^\s*(?:\[docs?\]|docs?:)|\b(?:typo|documentation|readme)\b/i.test(title)) return 'documentation'
  if (/^\s*(?:\[question\]|question:|how (?:do|can|to)\b)/i.test(title)) return 'question'
  if (/\b(?:fails?|crash(?:es)?|error|broken|unable|does not|no longer|cannot|frozen|stuck)\b/i.test(title)) return 'bug'
  return ''
}

function neededDetails(title, body, fields) {
  const requests = []
  const displayedVersion = fields.get('songmirror version or image tag') || fields.get('version')
  if (!displayedVersion && !/\b(?:v?\d+\.\d+\.\d+|sha-[\da-f]{7,}|sha256:[\da-f]{12,})\b/i.test(body)) {
    requests.push('The SongMirror version, Docker image tag, or image digest.')
  }
  const deployment = fields.get('installation method') || fields.get('environment')
  if (!deployment && !/\b(?:docker|compose|portainer|caprover|render blueprint|pip|uvicorn|native install)\b/i.test(title + '\n' + body)) {
    requests.push('How you installed SongMirror, such as Docker Compose, Portainer, or a Python install.')
  }
  const steps = fields.get('steps to reproduce') || fields.get('reproduction steps')
  if (!steps && !/^\s*(?:1[.)][ \t]|[-*][ \t]+(?:open|click|choose|select|run|connect)\b)/im.test(body)) {
    requests.push('The steps to reproduce the problem, including what you expected and what happened.')
  }
  return requests
}

function planIssue(issue) {
  const known = (issue.labels ?? []).map(label => (typeof label === 'string' ? label : label.name).toLowerCase())
  if (issue.state === 'closed' || issue.locked || issue.pull_request || issue.user?.type === 'Bot' ||
      known.some(label => ['duplicate', 'invalid', 'wontfix'].includes(label))) return { labels: [], requests: [] }
  const title = issue.title ?? ''
  const body = (issue.body ?? '').replace(/<!--[\s\S]*?-->/g, '')
  if (known.includes('security') || SECURITY.test(title) || SECURITY.test(body)) {
    return { labels: known.includes('security') ? [] : ['security'], requests: [] }
  }
  const fields = fieldsIn(body)
  const type = classify(title, fields, known)
  const service = fields.get('affected music services') || fields.get('affected service') || ''
  const areas = title + '\n' + (fields.get('affected area') || '')
  const labels = [
    type || 'needs-triage',
    ...PROVIDERS.filter(([, pattern]) => pattern.test(title + '\n' + service)).slice(0, 3).map(([name]) => 'provider: ' + name),
    ...AREAS.filter(([, pattern]) => pattern.test(areas)).slice(0, 2).map(([name]) => 'area: ' + name),
  ].filter(name => !known.includes(name.toLowerCase()))
  return { labels, requests: type === 'bug' ? neededDetails(title, body, fields) : [] }
}

async function ensureLabel(issues, repo, name) {
  try {
    await issues.getLabel({ ...repo, name })
    return
  } catch (error) {
    if (error.status !== 404) throw error
  }
  const detail = LABEL_DETAILS[name] ?? (
    name.startsWith('provider:')
      ? { color: 'd4c5f9', description: 'Reports involving ' + name.slice('provider: '.length) }
      : { color: 'bfd4f2', description: 'SongMirror ' + name.slice('area: '.length) }
  )
  try {
    await issues.createLabel({ ...repo, name, ...detail })
  } catch (error) {
    // A different issue job may have created the shared label first.
    if (error.status !== 422) throw error
    await issues.getLabel({ ...repo, name })
  }
}

async function handle({ github, context, core }) {
  const manual = context.eventName === 'workflow_dispatch'
  const issueNumber = Number(manual ? context.payload.inputs?.issue_number : context.payload.issue?.number)
  if (!Number.isSafeInteger(issueNumber) || issueNumber < 1) throw new Error('Expected a positive issue number')
  const issueParams = { ...context.repo, issue_number: issueNumber }
  const issues = github.rest.issues
  const { data: issue } = await issues.get(issueParams)
  const { labels, requests } = planIssue(issue)
  if (manual && context.payload.inputs?.dry_run !== 'false') {
    core.info(JSON.stringify({ issue: issueNumber, labels, requests }, null, 2))
    return
  }
  if (labels.length) {
    for (const name of labels) await ensureLabel(issues, context.repo, name)
    await issues.addLabels({ ...issueParams, labels })
  }
  if (context.payload.action !== 'opened' || !requests.length) return
  const existingReply = await github.paginate(issues.listComments, { ...issueParams, per_page: 100 })
  if (existingReply.some(comment => comment.user?.login === 'github-actions[bot]' && comment.body?.includes(REPLY_MARKER))) return
  await issues.createComment({
    ...issueParams,
    body: [
      'Thanks for reporting this. Could you add the following details so the issue can be reproduced?',
      '', ...requests.map(request => '- ' + request), '',
      'If you include logs, remove passwords, tokens, and cookies first.',
      '', REPLY_MARKER,
    ].join('\n'),
  })
}

module.exports = { planIssue, handle }
