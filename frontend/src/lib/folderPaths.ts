import type { FolderPickerConfig } from '@/types'

export function displayFolderPath(path: string, config?: FolderPickerConfig) {
  const mount = [...(config?.mounts ?? [])].sort((a, b) => b.server.length - a.server.length)
    .find((item) => path === item.server || path.startsWith(`${item.server}/`))
  if (!mount) return path
  const suffix = path.slice(mount.server.length)
  return mount.host.replace(/[\\/]$/, '') + (mount.host.includes('\\') ? suffix.replaceAll('/', '\\') : suffix)
}
