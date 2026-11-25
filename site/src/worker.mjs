const trailerPath = '/assets/songmirror-demo.mp4'

function selectBytes(range, size) {
  const match = /^bytes=(\d*)-(\d*)$/.exec(range)
  if (!match || (!match[1] && !match[2])) return null
  const start = match[1] ? Number(match[1]) : Math.max(0, size - Number(match[2]))
  const end = match[1] && match[2] ? Math.min(size - 1, Number(match[2])) : size - 1
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end || start >= size) return null
  return { start, end }
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname !== trailerPath) return env.ASSETS.fetch(request)

    const requestedRange = request.headers.get('range')
    const ifRange = request.headers.get('if-range')
    const assetHeaders = new Headers(request.headers)
    assetHeaders.delete('range')
    assetHeaders.delete('if-range')
    assetHeaders.set('accept-encoding', 'identity')
    const asset = await env.ASSETS.fetch(new Request(request, { headers: assetHeaders }))
    if (!asset.ok) return asset

    const headers = new Headers(asset.headers)
    headers.set('accept-ranges', 'bytes')
    const matchesAsset = !ifRange || [headers.get('etag'), headers.get('last-modified')].includes(ifRange)
    if (!requestedRange || !matchesAsset || request.method !== 'GET') {
      return new Response(asset.body, { status: asset.status, headers })
    }

    // Only this small MP4 uses the worker. The asset binding can omit
    // Content-Length, so use the actual bytes for the range calculation.
    const fullVideo = await asset.arrayBuffer()
    const size = fullVideo.byteLength
    const bytes = selectBytes(requestedRange, size)
    if (!bytes) {
      headers.set('content-range', `bytes */${size}`)
      headers.delete('content-length')
      return new Response(null, { status: 416, headers })
    }

    const { start, end } = bytes
    headers.set('content-range', `bytes ${start}-${end}/${size}`)
    headers.set('content-length', String(end - start + 1))
    return new Response(fullVideo.slice(start, end + 1), { status: 206, headers })
  },
}
