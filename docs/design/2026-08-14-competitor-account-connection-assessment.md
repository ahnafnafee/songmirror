# Competitor account-connection assessment

- **Date:** 2026-08-14
- **Scope:** TuneMyMusic and Soundiiz connection flows for Spotify, Apple Music,
  YouTube Music, Deezer, TIDAL, Amazon Music, and Qobuz
- **Status:** Research only; no implementation changes

## Answer

TuneMyMusic and Soundiiz do offer a no-extension, no-managed-browser experience,
but they are not extracting cookies or DevTools traffic from an iframe. For the
services in scope, their public flows use provider-owned OAuth/authorization pages
and partner-issued application identities. Apple Music uses Apple's MusicKit web
authorization model.

That distinction matters for SongMirror: a popup is only sufficient when the music
service cooperates by redirecting an authorization result to SongMirror. A popup or
iframe cannot turn SongMirror's current private-web-session connectors into OAuth.
Reproducing the competitors' experience therefore requires the same provider app or
partner approval, not a different browser trick.

## Evidence and methodology

The findings below come from first-party pages, current public redirect endpoints,
and the JavaScript currently served by the products. No account was used, no login
was completed, and no credentials were submitted.

TuneMyMusic publicly says that it connects through official APIs for nearly all
supported platforms and specifically identifies Pandora and Yandex Music as the
exceptions ([TuneMyMusic FAQ](https://www.tunemymusic.com/en)). Its current transfer
page also describes account connection as an official OAuth login
([TuneMyMusic transfer](https://www.tunemymusic.com/features/transfer)). A fresh
anonymous TuneMyMusic session returned provider login URLs from its own user-data
bootstrap endpoint. The current frontend classifies Spotify, YouTube Music, TIDAL,
and Amazon as `partner`, and Apple and Deezer as `officialApi`; its direct
username/password flag is set for services such as Yandex and Pandora, not for any
of the seven services in this assessment
([current TuneMyMusic platform bundle](https://www.tunemymusic.com/_next/static/chunks/2ch3brt-221gz.js)).

Soundiiz says it uses provider-hosted OAuth whenever available: the provider sends
Soundiiz an access token after authorization. It says that, for a service without
OAuth, Soundiiz may host a credential form and immediately exchange the credentials
for a token, retaining the token rather than the password
([Soundiiz security explanation](https://support.soundiiz.com/hc/en-us/articles/360009868074-Is-Soundiiz-safe-What-type-of-security-Soundiiz-is-using)).
The latter is a general fallback, but the live routes for the providers in scope use
authorization redirects rather than that fallback. Soundiiz's connection guide also
describes a popup followed by provider authorization
([Soundiiz connection guide](https://support.soundiiz.com/hc/en-us/articles/360024694393-How-to-connect-your-music-accounts-to-Soundiiz)).

## Provider-by-provider observations

| Provider | TuneMyMusic, verified live behavior | Soundiiz, verified live behavior | What SongMirror would need |
|---|---|---|---|
| Spotify | Redirects to `accounts.spotify.com/authorize` using authorization code, PKCE, and playlist/library scopes. Its bundle labels the integration `partner`. | [`/connect/spotify`](https://soundiiz.com/connect/spotify) redirects to Spotify authorization-code consent with Soundiiz's registered client and playlist/library scopes. | The existing Spotify OAuth integration is already the equivalent mechanism. |
| TIDAL | Redirects to `login.tidal.com/authorize` with TuneMyMusic's client ID, PKCE, and collection/playlist scopes; bundle label: `partner`. | [`/connect/tidal`](https://soundiiz.com/connect/tidal) redirects to the same TIDAL authorization endpoint with Soundiiz's client ID, PKCE, and playlist scopes. | This is reproducible with a registered TIDAL app and the required scopes. TIDAL documents app creation and OAuth authorization-code/refresh-token flows ([app management](https://developer.tidal.com/documentation/api-sdk/api-sdk-manage-apps), [authorization](https://developer.tidal.com/documentation/api-sdk/api-sdk-authorization)). |
| Deezer | Redirects to `connect.deezer.com/oauth/auth.php` with TuneMyMusic's existing app ID and library-management permissions; bundle label: `officialApi`. | [`/connect/deezer`](https://soundiiz.com/connect/deezer) redirects to Deezer OAuth with Soundiiz's existing app ID and library/offline scopes. | An accepted Deezer application. The competitors' existing app IDs do not create an authorization path for an unregistered SongMirror app. |
| Amazon Music | Redirects to Login with Amazon at `amazon.com/ap/oa`, requesting `profile` and `music::playlists`; bundle label: `partner`. | [`/connect/amazonmusic`](https://soundiiz.com/connect/amazonmusic) redirects to Login with Amazon with the same Music playlist scope. Soundiiz explicitly says Amazon controls the flow and Soundiiz does not receive Amazon credentials ([Soundiiz Amazon announcement](https://soundiiz.com/blog/import-your-playlists-to-amazon-music/)); its support page calls this the official Amazon API ([Amazon connection support](https://support.soundiiz.com/hc/en-us/articles/17006781766034-I-can-t-connect-my-Amazon-Music-account-to-Soundiiz)). | Amazon Music partner approval. Amazon currently says the API is a closed beta limited to already approved developers and requires an enabled security profile in addition to Login with Amazon ([Amazon Music Web API overview](https://www.developer.amazon.com/docs/music/API_web_overview.html)). |
| Qobuz | Redirects to Qobuz's `signin/oauth` endpoint with a TuneMyMusic `ext_app_id` and a TuneMyMusic callback. | [`/connect/qobuz`](https://soundiiz.com/connect/qobuz) redirects to the same Qobuz OAuth surface with a Soundiiz `ext_app_id` and callback. Soundiiz describes this as a popup that closes after Qobuz login ([Qobuz connection support](https://support.soundiiz.com/hc/en-us/articles/360012086699-Can-t-connect-or-change-a-Qobuz-account-to-Soundiiz)). | A Qobuz-issued external application identity. This is a partner OAuth facility, not something SongMirror can substitute with Qobuz web-player cookies. Qobuz's API terms require credentials issued by Qobuz ([Qobuz API terms](https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf)). |
| YouTube Music | Redirects to Google OAuth with offline access and both YouTube and `auth/music` scopes; the URL explicitly sets `disallow_webview=true`. The bundle labels YouTube Music `partner`. | [`/connect/ytmusic`](https://soundiiz.com/connect/ytmusic) redirects to Google OAuth with offline access and the YouTube plus `auth/music` scopes. Soundiiz says it uses the official Google API, while separately noting that Google offers no public YouTube Music API ([Google connection support](https://support.soundiiz.com/hc/en-us/articles/10555980158610-Can-t-connect-Google-or-YouTube-YouTube-Music), [YouTube Music explanation](https://support.soundiiz.com/hc/en-us/articles/360009550574-What-about-YouTube-Music)). | Ordinary YouTube Data API OAuth can cover shared YouTube playlists. Matching the competitors' Music-specific partner behavior may require Google's non-public Music scope/access. |
| Apple Music | Uses Apple's hosted MusicKit JS v3 SDK. The current bundle configures MusicKit with a developer token, calls `authorize()`, and sends the resulting Music User Token and storefront to TuneMyMusic's backend; bundle label: `officialApi` ([current Apple authorization bundle](https://www.tunemymusic.com/_next/static/chunks/3t146e6woujf3.js)). | Soundiiz's public support material identifies the flow as Apple Music API authentication and directs users to complete it in a normal browser ([Apple Music connection support](https://support.soundiiz.com/hc/en-us/articles/360009609854-I-can-t-connect-my-Apple-Music-account)). The exact frontend implementation is not exposed on the unauthenticated login page, so MusicKit JS is a strong inference rather than directly verified code. | This is the most realistic additional web-only improvement: register MusicKit, provide a developer token, and let MusicKit obtain/manage the user token. Apple documents informed-consent authorization and automatic Music User Token handling for web apps ([MusicKit](https://developer.apple.com/documentation/musickit), [user authentication](https://developer.apple.com/documentation/applemusicapi/user-authentication-for-musickit)). |

## What is and is not demonstrated

### Verified

- Both products open provider-owned authorization surfaces for Spotify, TIDAL,
  Deezer, Amazon Music, Qobuz, and Google/YouTube Music.
- TuneMyMusic uses MusicKit JS for Apple Music.
- Their server receives authorization codes/tokens through registered callbacks;
  the parent page does not inspect a provider iframe's cookies or network traffic.
- Neither product requires an extension or a locally automated browser for these
  connection flows.
- Their app IDs, callback registrations, scopes, and partner status are the enabling
  capabilities.

### Inference or not observable publicly

- Public client IDs and redirect URLs establish the authorization mechanism but do
  not reveal either company's private contracts, token encryption implementation,
  refresh scheduling, or internal API clients.
- TuneMyMusic's `partner` and `officialApi` labels are its own frontend metadata;
  `partner` does not disclose the commercial terms of the relationship.
- Soundiiz likely uses MusicKit on the web for Apple Music, but its unauthenticated
  bundle and support material do not prove the exact SDK call sequence.

### No evidence found

- Cross-origin iframe cookie extraction
- Browser-extension collection
- Playwright/CDP or a desktop helper
- Cookie-jar or copied-request import for any of the seven providers
- A TuneMyMusic or Soundiiz form that receives the user's normal password for any of
  these seven providers

## Consequence for SongMirror

There are web-only improvements available, but not one universal replacement for
manual session capture:

1. Keep Spotify OAuth.
2. Implement TIDAL authorization code + PKCE using a SongMirror TIDAL app, then verify
   that the issued scopes support every playlist operation SongMirror needs.
3. Implement Apple MusicKit authorization if the project can provision an Apple
   Music developer token.
4. Use standard Google/YouTube OAuth for the operations covered by the public YouTube
   API; do not assume that the partner `auth/music` capability will be granted.
5. Apply for Deezer, Qobuz, and Amazon Music app/partner access. If accepted, replace
   their compatibility connectors with the same popup/callback pattern used by the
   competitors.
6. Until that access exists, private web-player sessions still require manual import
   or a privileged local collector such as an extension or managed browser. A normal
   popup cannot return a token unless the provider has registered SongMirror as a
   client.

Public-playlist URLs, exported files, and user-uploaded backups can provide a fully
web-only read/import experience without account authorization. They cannot enumerate
private libraries, run durable bidirectional sync, or write playlists back to an
account.

## Bottom line

The competitor experience is real, but the missing ingredient is provider approval,
not an undocumented iframe technique. SongMirror can offer the same clean Connect
button immediately for Spotify, potentially TIDAL and Apple Music, and for the other
services only after obtaining the corresponding app or partner credentials. Without
that cooperation, manual paste, an extension, or a locally managed browser are the
only general ways to bootstrap SongMirror's current private-web-session connectors.
