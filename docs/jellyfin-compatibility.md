# Jellyfin connections and missing playlists

SongMirror supports Jellyfin 10.x and 12.x using the same `Authorization: MediaBrowser` header. Connection checks, playlist discovery, track counts, playlist inspection, and cover uploads all use this format. Existing server URLs, API keys, and optional user IDs continue to work; no version setting or replacement key is required for the upgrade.

Older SongMirror versions used `X-Emby-Token`. Jellyfin 12 disables legacy authorization by default, so those requests can receive HTTP 401 even when the key is valid. The old playlist browser also converted request failures into an empty list, which made this look like missing playlists. Update SongMirror, then refresh **Playlists**. You do not need to enable legacy authentication in Jellyfin.

If loading still fails, the playlist card now displays the error and offers **Retry**. Check the following settings in **Accounts → Jellyfin**:

1. The server URL must be reachable from SongMirror. With Docker, `localhost` refers to the SongMirror container; use the Jellyfin container name on a shared network, or the appropriate host address. Reverse-proxy base paths such as `/jellyfin` are retained, and pasted `/web/` or `/web/index.html` URLs are accepted.
2. The API key must still exist in Jellyfin's **Dashboard → API Keys**. A revoked key needs replacement; upgrading by itself does not require a new key.
3. If you entered a **User ID**, confirm it still identifies the intended Jellyfin user. It scopes playlist discovery and track counts to that user's access. Leave it empty for server-wide API-key browsing; playlist sync needs it.

Playlist discovery reads all result pages. A failed track-count request leaves that playlist visible with an unknown count, and a failed refresh preserves the previously saved list with an error notice. A successful response containing no playlists still shows the normal empty-library state. The local download mirror can also supply audio files and playlist covers.

## Playlist sync and transfers

Jellyfin can be the source or a destination of one-way syncs and transfers. First enter a **User ID** in **Accounts → Jellyfin**: Jellyfin assigns every playlist to a user, an API key has no user of its own, and the playlist API rejects reads without one. To find the ID, open **Dashboard → Users**, select the user, and copy `userId` from the address bar. Without a User ID the account still browses playlists, but the sync and transfer pickers do not offer it.

SongMirror matches incoming tracks against audio already in the server's library, using title, artist, duration, and recording version. Jellyfin does not expose ISRCs. SongMirror does not download or upload missing audio; unmatched songs stay in the missing results, where a Jellyfin item id can be saved as a manual match. New playlists are private unless the create flow asks for a public one, which Jellyfin shows to every user on the server. Jellyfin's playlist API has no description field, so descriptions are not copied.

Additions are appended in source order, one request per track. Jellyfin removes every copy of a song at once, so when one copy of a repeated song is removed, SongMirror inserts the remaining copies again at their original positions. For the same reason, date-added order repair is not available and transfers append in source order.

Playlists that Jellyfin reads from a playlist file, such as the download mirror's `.m3u8` files, are read-only to SongMirror. Jellyfin rewrites such a file on every change, and the download mirror regenerates its files on every pass. A sync whose playlist name matches only a file-backed playlist skips it with a warning. To sync that playlist into Jellyfin, rename one of the two, or use only the download mirror for it.

Open a Jellyfin playlist to inspect its tracks in SongMirror. The inspector reads metadata and ordered audio children through `/Items`, using the same server, API key, and optional User ID as the playlist browser. Tracks load progressively, and **Refresh** reads them again. Playlist edits and exports remain unavailable for Jellyfin; use **Open in Jellyfin** to manage the playlist on the server.

Compatibility is covered by protocol-level regression tests for the 10.8/10.11 and 12.0/12.1 authentication behavior, including legacy authentication disabled, plus the actual SongMirror connection and playlist API routes. These tests use mocked Jellyfin responses rather than live server installations. Playlist sync tests use a stateful fake of the playlist controller's add, insert, and remove behavior. On 2026-11-07 the same target was also checked against a live Jellyfin 12.2.0 server with a temporary playlist.

Upstream references: [Jellyfin 12 authorization handling](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Server.Implementations/Security/AuthorizationContext.cs), [Jellyfin 10.11 authorization handling](https://github.com/jellyfin/jellyfin/blob/v10.11.11/Jellyfin.Server.Implementations/Security/AuthorizationContext.cs), [the upgrade-related API-key report](https://github.com/jellyfin/jellyfin/issues/17245), and [the playlist controller](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/PlaylistsController.cs).
