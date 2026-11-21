import { t, useTranslation } from '@/i18n'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { ProfileShell } from './components/layout/ProfileShell'
import { BUTTON_BASE_CLASSES, BUTTON_SIZE_CLASSES, BUTTON_VARIANT_CLASSES } from './components/ui/buttonStyles'
import Accounts from './pages/Accounts'
import Dashboard from './pages/Dashboard'
import PlaylistCreation from './pages/PlaylistCreation'
import Playlists from './pages/Playlists'
import ResolveMappings from './pages/ResolveMappings'
import Settings from './pages/Settings'
import Sync from './pages/Sync'
import Transfers from './pages/Transfers'

export default function App() {
  useTranslation()
  return (
    <ProfileShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/playlists" element={<Playlists />} />
        <Route path="/sync" element={<Sync />} />
        <Route path="/transfers" element={<Transfers />} />
        <Route path="/playlists/create/*" element={<PlaylistCreation />} />
        <Route path="/imports" element={<Navigate to="/playlists/create/history" replace />} />
        <Route path="/create-playlist" element={<LegacyCreationRedirect />} />
        <Route path="/mappings" element={<ResolveMappings />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ProfileShell>
  )
}

function LegacyCreationRedirect() {
  const { search, hash } = useLocation()
  return <Navigate to={{ pathname: '/playlists/create', search, hash }} replace />
}

function NotFound() {
  useTranslation()
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-16 text-center">
      <p className="text-display text-xl text-text">{t("Page not found")}</p>
      <p className="text-sm text-text-3">{t("That page doesn't exist in SongMirror.")}</p>
      <Link to="/" className={`${BUTTON_BASE_CLASSES} ${BUTTON_SIZE_CLASSES.md} ${BUTTON_VARIANT_CLASSES.primary}`}>
        {t("Back to Dashboard")}
      </Link>
    </div>
  )
}
