import { api } from '../api'
import { usePersistedResource } from '../lib/persistedResource'
import type { SyncJob } from '../types'

function isSyncJobArray(value: unknown): value is SyncJob[] {
  return (
    Array.isArray(value) &&
    value.every(
      (job) =>
        job !== null &&
        typeof job === 'object' &&
        typeof job.id === 'string' &&
        typeof job.name === 'string' &&
        typeof job.enabled === 'boolean' &&
        (job.mode === 'oneway' || job.mode === 'group' || job.mode === 'nway' || job.mode === 'merge') &&
        ('authorities' in job ? typeof job.authorities === 'string' : true),
    )
  )
}

/** The list of named sync jobs (GET /api/syncs) — the Sync page's primary
 * data source. A persisted snapshot keeps route changes instant while the
 * local backend copy is revalidated in the background. */
export function useSyncs() {
  const { data: syncs, loading, refreshing, error, refresh } = usePersistedResource(
    'syncs',
    api.getSyncs,
    isSyncJobArray,
  )

  return { syncs, loading, refreshing, error, refresh }
}
