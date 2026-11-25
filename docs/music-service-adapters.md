# Playlist service adapters

Add each connection on **Accounts** and use the account's supported operations in **Sync** and **Transfers**. The table describes the protocol capabilities checked against provider references and exercised with local fixtures. Disposable Emby, Mopidy, and Lyrion servers also passed ordered playlist clone, track removal, and cleanup checks with generated music.

| Provider | Read playlists and tracks | Create and append | Remove tracks |
| --- | --- | --- | --- |
| Emby | Audio playlists for the configured user | Yes | By playlist entry ID. [Playlist API](https://dev.emby.media/doc/restapi/Playlists.html), [user authentication](https://dev.emby.media/doc/restapi/User-Authentication.html) |
| Plex | Static and smart audio playlists | Static audio playlists | Static playlists, by playlist item ID. [Plex Media Server API](https://developer.plex.tv/pms/#tag/Library-Playlists) |
| Mopidy | Playlists exposed through the HTTP extension | Bundled M3U backend | Selected occurrences through the M3U playlist save operation. [Core API](https://docs.mopidy.com/latest/reference/core/), [M3U backend](https://docs.mopidy.com/latest/ext/m3u/) |
| Lyrion Music Server | Saved playlists | Local M3U with a configured playlist folder | Selected positions in local M3U playlists. [Saved-playlist commands](https://preview.lyrion.org/reference/cli/database/#playlists), [JSON-RPC](https://preview.lyrion.org/reference/cli/using-the-cli/#jsonrpcjs) |
| Anghami | Account playlists and playlist links through OAuth | Unavailable in the SDK | Unavailable in the SDK. [Playlist API](https://docs.sdk.anghami.com/playlists), [OpenAPI schema](https://docs.sdk.anghami.com/api/anghami-sdk.openapi.yaml) |
| QQ Music | Public links through Skills or the web player, plus the signed-in web playlist library | Unverified | Unverified. [Tencent Music playlist detail API](https://github.com/tencentmusic/qqmusic-skills/blob/main/qqmusic/playlists.md) |
| Audiomack | Public playlist links through the web player's playlist payload | Documented separately in the OAuth Data API | Documented separately in the OAuth Data API. The web adapter exposes reads. [Public playlist](https://audiomack.com/audiomack-africa/playlist/verified-afrobeats), [Audiomack Data API](https://audiomack.com/data-api/docs#playlists) |
| Gaana | Public links and the signed-in web playlist library | Needs an authenticated clone test | Needs an authenticated clone test. [Trackhop web client](https://github.com/xlollx/Trackhop/blob/93f72ef901468daf9cb79214669e37d837662422/android/bridge/src/main/java/com/xlollx/songport/ytmbridge/GaanaWebClient.kt) |
| JioSaavn | Public featured and shared links, plus the signed-in web playlist library | Unverified | Unverified. [First-party playlist library](https://www.jiosaavn.com/my-music/playlists) |
| LINE MUSIC | Public links and the signed-in web playlist library | Unverified | Unverified. [First-party playlist library](https://music.line.me/webapp/library/playlists) |
| NetEase Cloud Music | Public links and the signed-in web playlist library | Documented separately for the NetEase CLI | Unverified. The web adapter exposes reads. [Public chart](https://music.163.com/#/playlist?id=3778678), [NetEase CLI guide](https://github.com/NetEase/skills/tree/master/netease-music-cli) |
| Pandora | Full public playlist URLs through an anonymous session, plus a signed-in collection | Unverified | Unverified. [Pandora collection](https://www.pandora.com/collection/playlists) |
| Naver Vibe | Public links and the signed-in web playlist library | Unverified | Unverified. [First-party playlist library](https://vibe.naver.com/library/playlists) |

Mopidy and Lyrion expose the local library as a source when their write backend or playlist folder is unavailable. Plex smart playlists are source-only. Anghami can supply a one-way or aggregate sync. QQ Music's Skills API documents paginated playlist details by ID. The signed-in web mode also supports selection from the user's playlist library.

Mopidy replaces the M3U playlist contents when saving, and Lyrion removes by position. SongMirror checks the selected entries against a fresh read before removing them. Those protocols do not provide an atomic revision check against simultaneous changes from another client.

Emby may omit the media type in an account's playlist directory. SongMirror checks those playlist entries before offering them as audio playlists. It sends track additions in batches and verifies the entries Emby reports adding against a fresh playlist read.

The disposable Emby, Mopidy, and Lyrion run passed 46 checks covering one-way and bidirectional sync, aggregate sync, removal propagation, catalog holds, and cleanup. On Plex Media Server 1.43.3, SongMirror created a blank audio playlist with an explicit empty `uri`, cloned eight indexed synthetic tracks in order, removed one entry by playlist item ID, and verified cleanup. The Anghami and QQ Music SDK transports passed fixture checks for opening playlist links through Transfers and reading paginated tracks. Authenticated live checks for those transports require connected accounts.

The QQ Music web transport read all 42 and 76 entries from two public playlists without an account or developer key. The web connection requires a public link during setup so SongMirror can verify the playlist identity. The four self-hosted adapters connect directly to their servers' web APIs using the settings described in Accounts.

Audiomack, Gaana, JioSaavn, LINE MUSIC, NetEase Cloud Music, Pandora, and Naver Vibe accept public playlist links as sources in Transfers and aggregate sync. Their Accounts setup verifies a link without asking for credentials. Paste the full playlist URL from the browser address bar if the service gives you a shortened share link. The live reads included 100 and 54 Audiomack tracks, 50 and 25 Gaana tracks, 40 and 316 JioSaavn tracks, 43 and 456 LINE MUSIC tracks, 200 and 43 NetEase tracks, 17 and 387 Pandora music tracks, and 50 and 75 Vibe tracks. Pandora's music-track view leaves out spoken introductions. Gaana's public chart response can supply fewer track IDs than the editorial total. SongMirror uses the ordered IDs actually exposed by the web player and checks that every exposed ID has a matching track.

The transfer API copied eight live public playlists to a disposable Mopidy library seeded with synthetic audio. The resulting copies matched all 284 source tracks in order. Each copy passed track removal and cleanup checks. A separate aggregate sync copied the 10-track NetEase playlist to the same disposable library.

## Signed-in web playlists

Under **Accounts → Connect → Sign in for private playlists**, sign in at the provider's web player and copy the playlist-library request named in the guide. SongMirror stores the session values it uses in the selected account profile. The request URL, body, and unrelated headers are discarded. Choose the connected library in Transfers, one-way sync, or aggregate sync. Removing the stored browser session preserves any public-link or Skills configuration associated with the profile.

| Provider | Read operation used to verify the session |
| --- | --- |
| Gaana | `user.php` with `type=myplaylists`. A signed-out request returned `Login Needed!`. |
| JioSaavn | `library.getAll`. The signed-out response returned `LOGIN_REQUIRED`. The first-party `playlist.getDetails` call returned all 316 entries for a public test playlist. |
| LINE MUSIC | `api2/user/me/libraries.v1`. Signed-out requests returned HTTP 401. The player bundle selects owned playlists using `isMine`. |
| NetEase Cloud Music | `api/nuser/account/get` establishes the viewer ID, then `api/user/playlist` lists that account's library. The signed-out identity response had no account. |
| Pandora | `api/v6/collections/getSortedPlaylists` identifies the current collection. The anonymous response contained zero collection entries. Private track details must name the same listener as the collection response. |
| QQ Music | `GetPlaylistByUin` from the web player. The signed-out call returned application code `80030`. |
| Naver Vibe | `vibe/v2/library/PLAYLIST/libraries`. The signed-out response returned HTTP 401. The player bundle reads owned lists through `myMusic/myAlbums` and its track endpoint. |

Private playlist reads are scoped to playlists listed by the connected account. The seven new signed-in modes are source-only. In the local confidence run, an isolated SongMirror instance ran seven one-way syncs against private provider fixtures and copied all 35 tracks in order to a real disposable Mopidy server. A combined aggregate sync copied the eight-track union and removed a track after it disappeared from all applicable sources. Every test playlist was cleaned up. An authenticated provider test needs a connected account with a private playlist.

Audiomack's website calls an OAuth-signed Data API for the account library. A reusable website-session connection for that API still needs verification. [Audiomack authentication reference](https://audiomack.com/data-api/docs)

Anghami's web player gateway returned HTTP 406 for signed-out playlist reads. The installed Chromium capture also returned 406 on the playlist page. The browser transport needs a successful authorized playlist read before it can be offered as a connection option. [Trackhop's Anghami web transport](https://github.com/xlollx/Trackhop/blob/d07e51fc80c206b4ba4077fdb31feed160972fce/android/bridge/src/main/java/com/xlollx/songport/ytmbridge/AnghamiWebClient.kt)

## Providers pending a playlist API contract

| Provider | Evidence and blocker |
| --- | --- |
| LiveOne | The signed-out web capture showed stations and guest authentication. The playlist help documents editing in the player. Trackhop's web implementation describes presets, so an authenticated playlist read and clone are still needed. [LiveOne playlist help](https://support.liveone.com/hc/en-us/articles/4416720960027-Playlists), [Trackhop LiveOne notes](https://trackhop.org/guide/docker#liveone-unofficial) |
| MOOV | The web player and a public `app.moov.hk` share both returned HTTP 403. Neither response supplied playlist data. [MOOV playlist help](https://helpcentre.moov-music.com/en/knowledge-base/my-collection-my-download/), [tested share link](https://app.moov.hk/xIeFa) |
| Yandex Music | The public playlist widget's network request returned HTTP 451. Two UUID playlist pages returned an HTML shell, and their playlist API requests also returned HTTP 451. The successful page loads supplied no track lists. [Tested public widget](https://music.yandex.ru/iframe/playlist/yamusic-top/1076), [tested UUID page](https://music.yandex.ru/playlists/cc4ece5f-2c41-0b27-96a5-b6a620d1df18) |
