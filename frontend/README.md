# SongMirror frontend

React, TypeScript, and Vite power the browser app. The FastAPI backend serves the production bundle. Start the backend from the repository root with `uv run uvicorn songmirror.web:app --port 8080`, then run:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Vite proxies API, event-stream, and OAuth requests to port 8080. Set `OMNI_BACKEND` to use a different backend.

```bash
pnpm lint
pnpm i18n:check
pnpm build
pnpm test:e2e
```

The browser tests intercept backend requests and run against the production bundle. They do not connect to music services or modify real playlists. Install Chromium once with `pnpm exec playwright install chromium`.

## Translations

The app ships English, Arabic, Turkish, Spanish, Simplified Chinese, French, Portuguese, German, Japanese, Hindi, Bengali, Indonesian, Korean, Italian, and Vietnamese. The same languages have project documentation linked from the [main README](../README.md#app-language).

`src/i18n/languages.ts` defines language codes and native names. `src/i18n/index.ts` initializes i18next, detects browser preferences, loads the chosen JSON catalog, and updates the document's language and direction. English is bundled initially; other catalogs load on demand from the installation itself. There are no runtime translation services or font CDNs.

Settings → General → Language applies a browser-local preference immediately. Automatic (browser) matches browser languages, including regional variants such as `es-MX`, and falls back to English. Arabic sets `dir="rtl"`. Storage restrictions do not prevent an in-session selection. If a locale asset fails to load, English remains usable; explicit selection failures appear beside the picker and can be retried.

### Change app copy

Subscribe in every component that renders translated text. Use complete English sentences as keys so translators can reorder variables:

```tsx
import { t, useTranslation } from '@/i18n'

function Greeting({ name }: { name: string }) {
  useTranslation()
  return <p>{t('Hello, {{name}}', { name })}</p>
}
```

For counts, pass numeric `count` and provide the English plural defaults. Use `formatNumber` for display:

```tsx
t('{{formattedCount}} track', {
  count,
  formattedCount: formatNumber(count),
  defaultValue_one: '{{formattedCount}} track',
  defaultValue_other: '{{formattedCount}} tracks',
})
```

Each locale supplies its own CLDR categories (`_zero`, `_one`, `_two`, `_few`, `_many`, `_other` where applicable). Avoid English suffix concatenation. Rich sentences use the exported `Trans` component with an explicit `i18nKey` and named `components`; keep links and technical values in React components rather than translation-provided HTML. See the [react-i18next Trans documentation](https://react.i18next.com/latest/trans-component).

After changing copy, run `pnpm i18n:extract` from a complete repository checkout. This updates `src/i18n/locales/en.json` from literal `t()` calls, `Trans` keys, and the backend's static account-field labels and help text. Translate the corresponding entries in every other catalog, then run `pnpm i18n:check`. The check rejects missing messages, stale English defaults, invalid placeholders, changed rich components, and missing plural categories. It also checks localized README links and setup commands. Neither command contacts a translation service.

Keep user-provided playlist, track, artist, account, and folder names unchanged. API keys, provider identifiers, schedule values, file paths, and external diagnostics keep their original representation. Translate static account-field metadata at its rendering boundary. Compute translated metadata at render time; module-level translations and memoized text without language dependencies can otherwise retain an old language.

Use the locale-aware helpers in `src/lib/format.ts` for numbers, dates, times, and durations. Prefer logical CSS utilities (`ms-*`, `pe-*`, `text-start`, `start-*`) for directional layouts, and use `dir="ltr"` for editable code and paths where needed.

### Add a language

Register its code and native name, create a complete catalog from the English keys with the required plural categories, add a localized project README and language navigation, and extend the catalog and browser checks. Verify a narrow viewport, an account connection guide, a sync wizard, and switching while a form contains unsaved edits.
