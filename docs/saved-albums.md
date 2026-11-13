# Sync saved albums across services

Saved albums are separate from playlists and liked tracks. SongMirror can import them once or keep adding newly saved albums on a schedule. Every connected provider can participate as a source or destination, using its native album collection where the connection supports it and portable album groups otherwise.

1. Connect the source and destination accounts on **Accounts**.
2. Open **Sync → New sync**, name the job, and choose **One-way** with the source account you want to copy from.
3. On **Services**, include the source and one or more destination accounts.
4. On **Playlists**, enable **Saved albums**. This creates an album-only job and includes every saved album in the source collection.
5. For a one-time import, turn **Active** off on **Schedule**. For ongoing additions, leave it active and choose an interval. Scheduled execution also requires the global auto-sync switch to be on.
6. Set **Max additions / pass**, save, and run **Preview**. Review missing or ambiguous albums in the feed, then use **Sync now** to apply the additions.

Each pass skips albums already saved at the destination. Large libraries continue over successive passes according to the additions cap. This cap counts albums rather than individual tracks. Preview performs reads and matching but never changes either library. Pause and stop take effect between albums.

## Where albums go

| Connection | Album collection |
| --- | --- |
| Spotify, TIDAL, Apple Music, Qobuz, Deezer | Native saved/favorite albums |
| YouTube Music browser mode | Native saved albums |
| Navidrome / Subsonic | Starred albums already present on the server |
| Jellyfin | Favorite albums already present on the server |
| Amazon Music, ListenBrainz, YouTube Data API mode | One private playlist per album |
| Last.fm | All album tracks added to Loved Tracks, with the album grouping retained by SongMirror |

Connections without native album-library access can supply album groups previously imported by SongMirror. Arbitrary playlists or loved songs are not automatically reinterpreted as complete saved albums. For YouTube Music's existing native album library, use the browser connection rather than Data API OAuth. Local music servers match only music already present on that server; this feature does not download audio.

Portable groups preserve album metadata and track order in `saved_albums.json` in SongMirror's persistent data directory. Keep that file with the rest of your SongMirror data when moving or restoring the installation. A group can subsequently move from a playlist or Loved Tracks into another provider's native album library. If a portable playlist is removed or edited so it no longer contains the complete album, or an album track is unliked, that group is no longer treated as a complete saved album source.

## Matching and recovery

UPC/EAN barcodes identify album releases; track ISRCs do not. SongMirror uses a matching barcode when the source exposes one. Otherwise it requires a matching title, primary artist, release year, and track count, and skips ambiguous results. Deluxe, live, and remaster qualifiers are retained. Spotify's web-session metadata does not expose UPC, so that connection uses conservative metadata matching.

Playlist and liked-track destinations resolve every album track before writing. A missing recording prevents an incomplete album from being created. Interrupted playlist copies retain the destination playlist id and resume missing tracks on retry. Saved albums and portable groups are additive: the job never unsaves albums, deletes playlists, unlikes tracks, or changes the source. A failed library read or matching request stops the pass before additions begin.

Saved-album jobs do not include ordinary playlist sync, liked-track sync, or downloads. Keep those in separate jobs. Existing service permissions still apply: TIDAL needs user-collection access, Apple needs CloudLibrary access, and Last.fm needs an authorized write session to receive loves.
