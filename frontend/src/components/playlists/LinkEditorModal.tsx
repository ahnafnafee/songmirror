import { useEffect, useMemo, useState } from 'react'

import { api, errorMessage } from '@/api'
import type { ProviderPlaylistsEntry } from '@/hooks/useProviderPlaylists'
import { serviceLogoId, tagText } from '@/lib/constants'
import type { Account, LinkDirection, LinkMembers, PlaylistLink } from '@/types'

import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { RadioCard } from '../ui/RadioCard'
import { SelectField } from '../ui/SelectField'
import { ServiceLogo } from '../ui/ServiceLogo'
import { TextField } from '../ui/TextField'
import { Toggle } from '../ui/Toggle'

// Sentinels for the per-provider <select>; translated to/from the real
// `members` shape (provider id -> playlist id | null) on save.
const OMIT = '__omit__' // provider is not part of this pairing
const CREATE = '__create__' // members[id] = null -> create a same-named playlist there
const KEEP = '__keep__' // provider isn't connected right now; preserve its existing mapping untouched

interface Props {
  open: boolean
  onClose: () => void
  /** null = creating a new pairing. */
  link: PlaylistLink | null
  /** Full account list (all states) — used both to list connected services
   * and to resolve display names for a member on a since-disconnected one. */
  accounts: Account[]
  playlistEntries: Record<string, ProviderPlaylistsEntry>
  onSaved: () => void
}

export function LinkEditorModal({ open, onClose, link, accounts, playlistEntries, onSaved }: Props) {
  const [name, setName] = useState('')
  const [direction, setDirection] = useState<LinkDirection>('oneway')
  const [source, setSource] = useState<string | null>(null)
  const [enabled, setEnabled] = useState(true)
  const [rowIds, setRowIds] = useState<string[]>([])
  const [memberChoices, setMemberChoices] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connectedIds = useMemo(() => new Set(accounts.filter((a) => a.state === 'connected').map((a) => a.id)), [accounts])

  // Fresh state whenever the editor (re)opens, so a previous attempt never
  // leaks into a new one. Rows cover every currently-connected service PLUS
  // — when editing — any provider already in the link's members even if
  // it's since been disconnected, so saving an edit can never silently drop
  // a member just because its service isn't connected right now (see the
  // KEEP sentinel below).
  useEffect(() => {
    if (!open) return
    const ids = new Set(connectedIds)
    if (link) for (const id of Object.keys(link.members)) ids.add(id)
    const ordered = Array.from(ids)
    setRowIds(ordered)

    const choices: Record<string, string> = {}
    for (const id of ordered) {
      const existing = link?.members[id]
      if (existing === undefined) choices[id] = OMIT
      else if (!connectedIds.has(id)) choices[id] = KEEP
      else choices[id] = existing === null ? CREATE : existing
    }
    setMemberChoices(choices)

    setName(link?.name ?? '')
    setDirection(link?.direction ?? 'oneway')
    setSource(link?.source ?? null)
    setEnabled(link?.enabled ?? true)
    setError(null)
    setSaving(false)
  }, [open, link, connectedIds])

  const includedIds = useMemo(
    () => rowIds.filter((id) => memberChoices[id] && memberChoices[id] !== OMIT),
    [rowIds, memberChoices],
  )

  function accountName(id: string): string {
    return accounts.find((a) => a.id === id)?.name ?? id
  }

  function setMemberChoice(id: string, value: string) {
    setMemberChoices((prev) => ({ ...prev, [id]: value }))
  }

  const nameValid = name.trim().length > 0
  const hasEnoughMembers = includedIds.length >= 2
  const sourceValid = direction !== 'oneway' || (source !== null && includedIds.includes(source))
  const formValid = nameValid && hasEnoughMembers && sourceValid

  async function handleSave() {
    if (!formValid) return
    setSaving(true)
    setError(null)
    try {
      const members: LinkMembers = {}
      for (const id of includedIds) {
        const choice = memberChoices[id]
        if (choice === CREATE) members[id] = null
        else if (choice === KEEP) members[id] = link?.members[id] ?? null
        else members[id] = choice
      }
      await api.upsertLink({
        id: link?.id,
        name: name.trim(),
        members,
        direction,
        source: direction === 'oneway' ? source : null,
        enabled,
      })
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={link ? `Edit "${link.name}"` : 'New pairing'}
      description="Link playlists across services that don't share a name, or limit a sync to only specific services."
      footer={
        <>
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="link-editor-form" loading={saving} disabled={!formValid}>
            {link ? 'Save changes' : 'Create pairing'}
          </Button>
        </>
      }
    >
      <form
        id="link-editor-form"
        className="flex flex-col gap-5 py-1"
        onSubmit={(e) => {
          e.preventDefault()
          void handleSave()
        }}
      >
        {error && <p className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        <TextField
          label="Pairing name"
          help="Used as the display name, and as the playlist name for any service where you choose “create new”."
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <div className="flex flex-col gap-3">
          <p className="text-[12.5px] font-semibold text-text-2">Services</p>
          {rowIds.length === 0 ? (
            <p className="text-sm text-text-3">Connect at least two services on the Accounts page to create a pairing.</p>
          ) : (
            rowIds.map((id) => {
              const connected = connectedIds.has(id)
              const currentRaw = link?.members[id]
              const options = connected
                ? [
                    { value: OMIT, label: 'Not included in this pairing' },
                    { value: CREATE, label: 'Create new (same name as pairing)' },
                    ...(playlistEntries[id]?.playlists.map((p) => ({ value: p.id, label: p.name })) ?? []),
                  ]
                : [
                    { value: OMIT, label: 'Not included in this pairing' },
                    { value: KEEP, label: `Keep current (${currentRaw === null ? 'create new' : currentRaw})` },
                  ]
              const logoId = serviceLogoId(id)
              return (
                <SelectField
                  key={id}
                  label={connected ? accountName(id) : `${accountName(id)} (not connected)`}
                  help={connected ? undefined : 'Reconnect this service on the Accounts page to change its playlist.'}
                  icon={logoId ? <ServiceLogo service={logoId} className={`size-4 ${tagText(id)}`} /> : undefined}
                  options={options}
                  value={memberChoices[id] ?? OMIT}
                  onChange={(e) => setMemberChoice(id, e.target.value)}
                />
              )
            })
          )}
          {rowIds.length > 0 && !hasEnoughMembers && (
            <p className="text-xs text-warning">Include at least 2 services to form a pairing.</p>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-[12.5px] font-semibold text-text-2">Sync direction</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <RadioCard
              name="link-direction"
              value="oneway"
              checked={direction === 'oneway'}
              onChange={() => setDirection('oneway')}
              title="One-way"
              description="One service is the source; the others follow it."
            />
            <RadioCard
              name="link-direction"
              value="nway"
              checked={direction === 'nway'}
              onChange={() => setDirection('nway')}
              title="Bidirectional (N-way)"
              description="A change on any included service propagates to the others."
            />
          </div>
        </div>

        {direction === 'oneway' && (
          <SelectField
            label="Source service"
            help="The service every other included service follows."
            error={includedIds.length > 0 && !sourceValid ? 'Pick which service is the source.' : undefined}
            options={[
              { value: '', label: includedIds.length ? 'Choose one…' : 'Include at least 2 services first' },
              ...includedIds.map((id) => ({ value: id, label: accountName(id) })),
            ]}
            value={source ?? ''}
            disabled={includedIds.length === 0}
            onChange={(e) => setSource(e.target.value || null)}
          />
        )}

        <Toggle
          checked={enabled}
          onChange={setEnabled}
          label="Enabled"
          description="Paused pairings are kept but skipped during sync passes."
        />
      </form>
    </Modal>
  )
}
