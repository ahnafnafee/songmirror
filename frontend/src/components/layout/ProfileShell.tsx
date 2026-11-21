import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import useSWR from 'swr'

import { api, ApiError } from '@/api'
import songmirrorMark from '@/assets/brand/songmirror-mark.png'
import { OwnerSignInContext } from '@/hooks/useOwnerSignIn'
import { t, useTranslation } from '@/i18n'
import { disableBrowserDataCache } from '@/lib/browserDataCache'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { TextField } from '../ui/TextField'
import { AppShell } from './AppShell'

async function loadSession() {
  const session = await api.profileSession()
  if (typeof session?.enabled !== 'boolean' || typeof session.authenticated !== 'boolean') {
    throw new Error('Invalid profile session response')
  }
  if (session.enabled) disableBrowserDataCache()
  return session
}

export function ProfileShell({ children }: { children: ReactNode }) {
  useTranslation()
  // Production marks the HTML when it already requires sign-in. Vite serves
  // its own HTML, so ask the proxied backend for the status in development.
  const [checkSession, setCheckSession] = useState(
    () => import.meta.env.DEV || !!document.querySelector('meta[name="songmirror-auth"][content="required"]'),
  )
  const { data: session, error, mutate } = useSWR('profile-session', loadSession, {
    shouldRetryOnError: false,
    revalidateOnMount: checkSession,
    revalidateOnFocus: checkSession,
    revalidateOnReconnect: checkSession,
    refreshInterval: (current) => current?.enabled && current.authenticated ? 60_000 : 0,
  })
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState(false)

  async function signOut() {
    setSigningOut(true)
    setSignOutError(false)
    try {
      await api.signOut()
      // Start with empty in-memory playlist, API, and event caches.
      window.location.reload()
    } catch {
      setSignOutError(true)
      setSigningOut(false)
    }
  }

  async function setup(username: string, password: string, setupCode: string) {
    try {
      await api.setupOwnerSignIn(username, password, setupCode)
    } catch (err) {
      // Another tab may have completed setup while this form was open.
      if (!(err instanceof ApiError) || err.status !== 409) throw err
    }
    try {
      await mutate(await loadSession(), { revalidate: false })
      setCheckSession(true)
    } catch {
      window.location.reload()
    }
  }

  if (checkSession && !session) {
    return (
      <ProfileFrame>
        {error ? (
          <>
            <p role="alert" className="text-sm text-danger">{t("Could not check your sign-in status.")}</p>
            <Button onClick={() => void mutate()}>{t("Retry")}</Button>
          </>
        ) : (
          <p role="status" className="flex items-center gap-2 text-sm text-text-2">
            <Spinner />
            {t("Loading SongMirror…")}
          </p>
        )}
      </ProfileFrame>
    )
  }

  const enabled = session?.enabled ?? false
  if (enabled && !session?.authenticated) return <SignIn />
  return (
    <OwnerSignInContext.Provider value={{ enabled, setup }}>
      <AppShell profile={enabled ? { signOut, signingOut } : undefined}>
        {signOutError && <p role="alert" className="mb-4 text-sm text-danger">{t("Could not sign out. Try again.")}</p>}
        {children}
      </AppShell>
    </OwnerSignInContext.Provider>
  )
}

function SignIn() {
  useTranslation()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<number | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    setError(null)
    setSubmitting(true)
    try {
      await api.signIn(String(fields.get('username')), String(fields.get('password')))
      if (!(await loadSession()).authenticated) throw new Error('Session cookie unavailable')
      window.location.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.status : 0)
      setSubmitting(false)
    }
  }

  return (
    <ProfileFrame>
      <h1 className="text-xl font-bold tracking-tight text-text">{t("Sign in")}</h1>
      <form method="post" onSubmit={submit} className="flex flex-col gap-4">
        <TextField label={t("Username")} name="username" autoComplete="username" required />
        <TextField label={t("Password")} name="password" type="password" autoComplete="current-password" required />
        {error !== null && (
          <p role="alert" className="text-sm text-danger">
            {error === 401 ? t("Incorrect username or password.")
              : error === 429 ? t("Too many sign-in attempts. Try again in a minute.")
              : t("Could not sign in. Try again.")}
          </p>
        )}
        <Button type="submit" size="lg" loading={submitting} className="mt-1 w-full">
          {t("Sign in")}
        </Button>
      </form>
    </ProfileFrame>
  )
}

function ProfileFrame({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-bg px-4 py-8">
      <div className="flex w-full max-w-sm flex-col gap-5 rounded-card border border-border bg-surface p-5 sm:p-7">
        <div className="flex items-center gap-2.5 text-[15px] font-extrabold tracking-tight text-text">
          <img src={songmirrorMark} alt="" className="h-7 w-auto" />
          SongMirror
        </div>
        {children}
      </div>
    </main>
  )
}
