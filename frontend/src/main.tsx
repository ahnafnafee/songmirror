import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

// Bundled fonts (no runtime CDN). Archivo is a single variable file spanning
// both the weight (100-900) and width (62-125%) axes it needs — normal-weight
// UI text through the "display voice" (heavy + stretched + uppercase, see
// the .text-display utility in index.css) all come from this one face.
// Space Mono covers counts/codes/timestamps; there is no separate serif.
import '@fontsource-variable/archivo/standard.css'
import '@fontsource/space-mono/400.css'
import '@fontsource/space-mono/700.css'

import App from './App.tsx'
import { initializeI18n } from './i18n'
import './index.css'

void initializeI18n().then(() => createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
))
