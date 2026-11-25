# Playlist service adapters

Add each connection on **Accounts** and use the account's supported operations in **Sync** and **Transfers**. The table describes the protocol capabilities checked against provider references and exercised with local fixtures. Disposable Emby, Mopidy, and Lyrion servers also passed ordered playlist clone, track removal, and cleanup checks with generated music.

| Provider | Read playlists and tracks | Create and append | Remove tracks |
| --- | --- | --- | --- |
| Emby | Audio playlists for the configured user | Yes | By playlist entry ID. [Playlist API](https://dev.emby.media/doc/restapi/Playlists.html), [user authentication](https://dev.emby.media/doc/restapi/User-Authentication.html) |
| Plex | Static and smart audio playlists | Static audio playlists | Static playlists, by playlist item ID. [Plex Media Server API](https://developer.plex.tv/pms/#tag/Library-Playlists) |
| Mopidy | Playlists exposed through the HTTP extension | Bundled M3U backend | Selected occurrences through the M3U playlist save operation. [Core API](https://docs.mopidy.com/latest/reference/core/), [M3U backend](https://docs.mopidy.com/latest/ext/m3u/) |
| Lyrion Music Server | Saved playlists | Local M3U with a configured playlist folder | Selected positions in local M3U playlists. [Saved-playlist commands](https://preview.lyrion.org/reference/cli/database/#playlists), [JSON-RPC](https://preview.lyrion.org/reference/cli/using-the-cli/#jsonrpcjs) |
| Anghami | Account playlists and playlist links through OAuth | Unavailable in the SDK | Unavailable in the SDK. [Playlist API](https://docs.sdk.anghami.com/playlists), [OpenAPI schema](https://docs.sdk.anghami.com/api/anghami-sdk.openapi.yaml) |
| QQ Music | Pasted playlist links for transfers and aggregate sync | Unverified | Unverified. [Tencent Music playlist detail API](https://github.com/tencentmusic/qqmusic-skills/blob/main/qqmusic/playlists.md) |

Mopidy and Lyrion expose the local library as a source when their write backend or playlist folder is unavailable. Plex smart playlists are source-only. Anghami can supply a one-way or aggregate sync. QQ Music's Skills API documents paginated playlist details by ID, so SongMirror uses links for transfers and aggregate sources. The separate QQ Music QPlay example includes a personal-directory request with its own credential and signing contract. [Tencent Music QPlay OpenAPI example](https://github.com/tencentmusic/QQMusic_Innovation_QPlay_OpenAPI_Demo/tree/partner)

Mopidy replaces the M3U playlist contents when saving, and Lyrion removes by position. SongMirror checks the selected entries against a fresh read before removing them. Those protocols do not provide an atomic revision check against simultaneous changes from another client.

Emby may omit the media type in an account's playlist directory. SongMirror checks those playlist entries before offering them as audio playlists. It sends track additions in batches and verifies the entries Emby reports adding against a fresh playlist read.

The disposable Emby, Mopidy, and Lyrion run passed 46 checks covering one-way and bidirectional sync, aggregate sync, removal propagation, catalog holds, and cleanup. On Plex Media Server 1.43.3, SongMirror listed, created, read, and cleaned up a blank audio playlist. Creating it required an explicit empty `uri`. Append and track removal passed protocol fixtures. The disposable Plex server stalled during music-library setup, so the populated clone check needs a working music library. Anghami and QQ Music passed fixture checks for opening playlist links through Transfers and reading paginated tracks. They need connected accounts for live verification.

## Providers pending a playlist API contract

| Provider | Evidence and blocker |
| --- | --- |
| LiveOne | The provider documents playlist creation, editing, and sharing in its client. A corresponding playlist API reference for SongMirror was not located. [LiveOne playlist help](https://support.liveone.com/hc/en-us/articles/4416720960027-Playlists) |
| NetEase Cloud Music | NetEase documents creation and appending through `ncm-cli`. The published CLI's local command list with synthetic credentials did not include the remote playlist commands. Listing the account's playlists, retrieving complete track lists, and removing individual tracks could not be verified from the available technical material. [NetEase music CLI guide](https://github.com/NetEase/skills/tree/master/netease-music-cli), [NetEase assistant examples](https://github.com/NetEase/skills/tree/master/netease-music-assistant), [published CLI](https://www.npmjs.com/package/@music163/ncm-cli) |
| JioSaavn | The available playlist wrapper identifies itself as unofficial. A provider reference for authenticated playlist reads or mutations was not located. [Wrapper repository](https://github.com/cyberboysumanjay/JioSaavnAPI) |
| Gaana | The company's feature bulletin shows a playlist importer inside the mobile app. A developer reference for reading, appending, or removing playlist tracks was not located. [Gaana playlist import bulletin](https://bsmedia.business-standard.com/_media/bs/data/announcements/bse/06112025/eb5cce8d-bac6-4ea4-9d65-d005cce78ba5.pdf) |
