# SoundCloud and Last.fm application credentials

The operator of a SongMirror deployment can configure one application per
provider. Each listener authorizes their own account in **Accounts**.
Application secrets stay on the server. Set the variables in the deployment
environment (or the optional `.env` file for Docker Compose), then restart
SongMirror to load them.

## SoundCloud

1. In SongMirror, open **Accounts → SoundCloud → Connect** and copy the
   callback URL. Set `SONGMIRROR_PUBLIC_URL` to the browser-visible base URL if
   SongMirror runs behind a reverse proxy.
2. [Register a SoundCloud API application](https://developers.soundcloud.com/docs/api/register-app)
   and set its redirect URI to the callback URL. The app owner needs Artist Pro
   to register it. Listeners can authorize their regular SoundCloud accounts.
3. Set `SOUNDCLOUD_CLIENT_ID` and `SOUNDCLOUD_CLIENT_SECRET` on the server.
4. In **Accounts**, connect the SoundCloud profile and approve access on
   SoundCloud. Connect each additional SoundCloud profile the same way.
5. Select playlists in **Playlists**, **Transfers**, or **Syncs**. Owned
   playlists can receive additions and removals. Liked playlists are available
   to read. To sync both directions, choose a bidirectional sync with owned
   playlists. Use the sync’s schedule to run it automatically.

SongMirror sends track and playlist metadata through the official API. It
cannot transfer audio through SoundCloud. SoundCloud does a whole-playlist
replacement for membership changes. SongMirror checks the live track count
before writing and preserves the order of retained tracks. Avoid editing the
same playlist in SoundCloud while a sync is applying changes, since the API
offers no documented conditional update for this operation.

## Last.fm

Starting December 1, 2026, Last.fm requires Pro on the account that owns the
API key. Listeners can keep using free accounts through a deployment whose
application key stays active. [Last.fm’s announcement](https://support.last.fm/t/api-keys-will-require-pro-from-1st-december/121030)

1. [Register a Last.fm API application](https://www.last.fm/api/account/create)
   using the operator’s account. Use the Last.fm callback URL shown in
   **Accounts → Last.fm → Connect** when registering the application.
2. Set `LASTFM_APP_API_KEY` and `LASTFM_APP_API_SECRET` on the server.
3. In **Accounts**, select **API authorization** and approve access on Last.fm
   to read private history and sync Loved Tracks. Select **Public history**
   and enter a username for read-only public history.

A profile with its own API key keeps using that key. To move it to the
deployment’s app, disconnect that profile and connect it again. Replacing the
deployment’s key also requires affected listeners to authorize again. Each
profile keeps its own username and authorization session.
