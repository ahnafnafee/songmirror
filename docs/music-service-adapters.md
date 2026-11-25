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
| Audiomack | Public links and the signed-in web playlist library | With a signed-in account. Creates private playlists. | By track ID on playlists owned by the connected account. A single duplicate occurrence cannot be addressed. [Audiomack Data API](https://audiomack.com/data-api/docs#playlists) |
| Gaana | Public links and the signed-in web playlist library | With a signed-in account. Creates private playlists. | By track ID. A single duplicate occurrence cannot be addressed. [Trackhop web client](https://github.com/xlollx/Trackhop/blob/93f72ef901468daf9cb79214669e37d837662422/android/bridge/src/main/java/com/xlollx/songport/ytmbridge/GaanaWebClient.kt) |
| JioSaavn | Public featured and shared links, plus the signed-in web playlist library | The web player exposes `playlist.create` and `playlist.add`. Signed-in writes are unverified. | The web player exposes `playlist.save` for replacing membership. A playlist deletion and clone cleanup flow remains unverified. [First-party playlist library](https://www.jiosaavn.com/my-music/playlists) |
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

Private playlist reads are scoped to playlists listed by the connected account. Signed-in Audiomack and Gaana profiles also work as destinations. In the local confidence run, an isolated SongMirror instance ran eight one-way syncs against private provider fixtures and copied all 40 tracks in order to a disposable Mopidy server. A combined aggregate sync copied the eight-track union and removed a track after it disappeared from all applicable sources. Every fixture playlist was cleaned up. An authenticated provider test needs a connected account with a private playlist.

The live Gaana clone test found five of five catalog tracks by metadata, created a private playlist, appended three matched tracks in order, removed the middle track, and confirmed deletion of the scratch playlist. An aggregate job copied three tracks between two additional temporary playlists, did nothing on a second pass, and propagated a source-track removal. Both playlists were cleaned up. SongMirror verifies account membership before each edit and checks the resulting track order after changes.

Audiomack's signed-in web player returned HTTP 200 for `/v1/user` and `/v1/user/playlists/page/1`. The directory included a private playlist and its track count, with no tracks in that response. Setup uses the Network request filtered by `v1/user/playlists` and the `osecret` cookie from the Audiomack site. The browser session stores only the token and signing cookie. Audiomack's web player signs both the directory request and the `/v1/playlist/{id}/` track request. SongMirror checks a track read during setup when the account has a nonempty playlist. [Audiomack playlist library](https://audiomack.com/my-library/playlists)

Audiomack's signed-in player returned HTTP 201 for private playlist creation and ordered track addition and HTTP 204 for track removal and scratch playlist deletion. The working track route was `DELETE /v1/playlist/{id}/track/{music_id}`. The shorter track route in the Data API reference returned HTTP 422 in the browser. SongMirror compares the playlist owner with the signed-in identity before editing and reads back the track order after changes. An aggregate sync between two temporary private playlists copied three tracks in order, made no changes on a second pass, and propagated one source removal. Both playlists were deleted after verification. [Audiomack playlist library](https://audiomack.com/my-library/playlists)

A Chromium capture of `https://play.anghami.com/playlists` returned HTTP 406 for the initial document. The capture contained one network request, so the browser made no playlist API calls. The separate player gateway returned HTTP 406 for a signed-out playlist read. The browser transport needs a successful authorized playlist read before it can be offered as a connection option. [Anghami web player](https://play.anghami.com/playlists), [Trackhop's Anghami web transport](https://github.com/xlollx/Trackhop/blob/d07e51fc80c206b4ba4077fdb31feed160972fce/android/bridge/src/main/java/com/xlollx/songport/ytmbridge/AnghamiWebClient.kt)

## Playlist writes exposed by public web-player code

The web-player bundles establish the requests below. A signed-in playlist clone and its cleanup have yet to be verified for these three services.

| Provider | First-party write calls | Observed read |
| --- | --- | --- |
| LINE MUSIC | The player creates a playlist with `POST /api2/user/me/myAlbum.v1`. It adds tracks with `POST` and removes them with `PUT` on `/api2/user/me/myAlbum/{id}/tracks.v1`. [LINE MUSIC player bundle](https://linemusic-webapp.landpress.line.me/assets/index-uvw4j5sK.js) | A public playlist request returned HTTP 200. The signed-in library endpoint returned HTTP 401 without a session. |
| QQ Music | The player calls `PlaylistBaseWrite.AddPlaylist` and `PlaylistBaseWrite.DelPlaylist` for creation and deletion, and `PlaylistDetailWrite.AddSonglist` and `PlaylistDetailWrite.DelSonglist` for tracks. [QQ Music player bundle](https://y.qq.com/ryqq/js/common.chunk.80d50705ce8f47a01eb5.js) | Two public web playlists returned complete lists of 42 and 76 tracks. The signed-in directory call returned application code `80030` without a session. |
| Yandex Music | The player posts to `users/{userId}/playlists/create` and `users/{userId}/playlists/{kind}/change-relative`. Track edits send a `diff` with a playlist `revision`. [Yandex Music player bundle](https://yastatic-net.ru/s3/music-frontend-static/music/v4.1745.1/_next/static/chunks/12957.35703fbdaf73fdf1.js) | The playlist page HTML loaded. The playlist data request returned HTTP 451 from the test environment. |

## Providers pending a playlist API contract

| Provider | Evidence and blocker |
| --- | --- |
| LiveOne | The signed-out web capture showed stations and guest authentication. The playlist help documents editing in the player. Trackhop's web implementation describes presets, so an authenticated playlist read and clone are still needed. [LiveOne playlist help](https://support.liveone.com/hc/en-us/articles/4416720960027-Playlists), [Trackhop LiveOne notes](https://trackhop.org/guide/docker#liveone-unofficial) |
| MOOV | The web player and a public `app.moov.hk` share both returned HTTP 403. Neither response supplied playlist data. [MOOV playlist help](https://helpcentre.moov-music.com/en/knowledge-base/my-collection-my-download/), [tested share link](https://app.moov.hk/xIeFa) |
| Yandex Music | The public playlist widget's network request returned HTTP 451. Two UUID playlist pages returned an HTML shell, and their playlist API requests also returned HTTP 451. The successful page loads supplied no track lists. [Tested public widget](https://music.yandex.ru/iframe/playlist/yamusic-top/1076), [tested UUID page](https://music.yandex.ru/playlists/cc4ece5f-2c41-0b27-96a5-b6a620d1df18) |
