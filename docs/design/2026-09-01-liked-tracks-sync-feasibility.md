# Liked, favorite, and library tracks sync feasibility

Date: 2026-09-01
Issue: [#35 — Sync Spotify Liked Songs with TIDAL Favorites](https://github.com/ahnafnafee/songmirror/issues/35)
Repository baseline: [`cf167408`](https://github.com/ahnafnafee/songmirror/tree/cf16740878f6144545d61b4641f4e61b0574ca28)

## Verdict

The feature is technically feasible, including the original Spotify-to-TIDAL request, but it is not uniformly supportable as a public, fully bidirectional feature across all seven providers.

Spotify and TIDAL expose complete saved/favorite-track CRUD. Qobuz and Deezer expose the necessary operations through the same first-party web APIs SongMirror already uses, but those are private contracts. Amazon offers complete saved-library CRUD, while its public *liked-track* API has no documented neutral/unlike operation; its first-party web client does. Apple exposes public favorite addition but reserves removal for Apple clients; the first-party web client nevertheless performs both operations. YouTube's public API can manage all liked **videos**, not the exact music-only **Liked Music** view, so exact behavior requires the private `youtubei` path.

There are also hard distribution constraints. TIDAL prohibits transferring data to another service without written approval, and Amazon prohibits integrating Amazon Music with another music service. Therefore:

- **Personal/self-hosted implementation:** feasible, with private-API fragility clearly disclosed.
- **Policy-compliant public release:** feasible only for the providers that approve the use case; TIDAL and Amazon are blocked without provider approval.
- **One capability promise for every provider:** not feasible. SongMirror must expose per-provider read/add/remove capabilities and never silently substitute “dislike” or “remove from library” for “unfavorite.”

## Provider capability matrix

| Provider | SongMirror collection | Read | Add | Remove | Authentication and limits | Assessment |
|---|---|---:|---:|---:|---|---|
| Spotify | Saved Tracks / Liked Songs | Yes | Yes | Yes | OAuth uses `user-library-read` and `user-library-modify`; `GET /me/tracks` pages at 50 tracks and generic `PUT`/`DELETE /me/library` accepts at most 40 URIs. SongMirror's default `sp_dc` mode instead uses the web player's private `fetchLibraryTracks`, `addToLibrary`, and `removeFromLibrary` operations so it never enters the first-party token's `api.spotify.com` penalty bucket. | The OAuth contract is public and well supported. The default web-session path works without a developer app but remains private and subject to web-player changes. Existing OAuth users must reconnect for the added library scopes. |
| TIDAL | Favorite Tracks | Yes | Yes | Yes | OAuth authorization-code + PKCE with `collection.read` and `collection.write`. Cursor pagination; default order is descending `addedAt`; add/remove accepts 1–50 IDs. | Technically excellent, including optional `addedAt` on additions, but public distribution needs written TIDAL approval. |
| Qobuz | Favorite Tracks | Yes | Yes | Yes | Private v0.2 web session (`X-App-Id` and `X-User-Auth-Token`). Offset/limit read; response carries `favorited_at`; create/delete accepts `track_ids`. No documented batch ceiling. | Fits the current adapter, but the contract and copied first-party credentials are unsupported. Historical favorite timestamps cannot be restored. |
| Deezer | Favorite Tracks | Yes | Yes | Yes | Private Pipe GraphQL. `userFavorites.tracks(first, after)` is cursor-paginated and edges carry `favoritedAt`; add/remove mutations accept one track ID. Read scopes include `favorite-track-read`; mutations say they require “specific access.” | Straightforward on the existing web-session client, but write access is private/restricted and must be proven with an authenticated spike. |
| Amazon Music | Saved Library Tracks | Yes | Yes | Yes | Closed-beta Web API: cursor pagination, at most 100 per page; `PUT`/`DELETE /me/library/tracks/{id}` is one item per request. Scopes are `music::profile:read` for the documented read and `music::library` for writes. | Technically complete but high-risk: closed beta, partner enablement, and policy forbids third-party music-service integration. |
| Amazon Music | Liked Tracks | Yes | Yes | Private only | Public `GET /me/tracks` uses `music::favorites:read`, max 100/page; `PUT /me/tracks/{id}` uses `music::favorites`, but documents only `LIKE` and `DISLIKE`. The first-party bundle also defines `NEUTRAL`. | Do not map removal to `DISLIKE`. Use saved-library tracks as the supported semantic fallback, or gate exact likes behind the private web backend. |
| Apple Music | Favorite Songs | Yes | Yes | Private only | Developer token plus Music User Token; there are no granular OAuth scopes. Public `POST /v1/me/favorites` accepts favorites. Apple's first-party web client identifies the system playlist by a `favorited` tag and uses `POST`/`DELETE /v1/me/favorites`. | Exact membership is technically available with SongMirror's captured web tokens, but Apple explicitly says third-party apps cannot remove favorites. Public mode must be read/add-only. |
| YouTube Music | Liked Music | Private only | Private only | Private only | Exact collection is a music-filtered first-party view. The public YouTube Data API instead exposes the account's Liked Videos playlist: reads max 50/page; `videos.rate` sets `like` or `none`, one video per call, at a cost of 50 quota units. OAuth scope `youtube.force-ssl` suffices. | Exact behavior fits the existing authenticated `youtubei` backend, but is unsupported. Public API mode is full CRUD only for the broader Liked Videos set and must not be labeled Liked Music. |

### Primary-source evidence

- **Spotify.** The official [Saved Tracks endpoint](https://developer.spotify.com/documentation/web-api/reference/get-users-saved-tracks) documents `user-library-read`, 50-item pages, and `added_at`. The generic [save](https://developer.spotify.com/documentation/web-api/reference/save-library-items) and [remove](https://developer.spotify.com/documentation/web-api/reference/remove-library-items) endpoints require `user-library-modify` and cap requests at 40 URIs. Spotify's [February 2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide) makes those generic endpoints the current OAuth contract and limits new development-mode apps to five users. The separate `sp_dc` implementation was verified against the current web-player bundle and is intentionally documented as private rather than presented as part of that public contract. Spotify's [Developer Policy](https://developer.spotify.com/policy) permits transfer when it enables a user to transfer their personal data or playlist metadata.

- **TIDAL.** The official [OpenAPI document](https://tidal-music.github.io/tidal-api-reference/tidal-api-oas.json) defines `GET /userCollectionTracks/me` and `GET`/`POST`/`DELETE /userCollectionTracks/me/relationships/items`, the collection scopes, cursor and sort behavior, the 50-item mutation ceiling, and relationship metadata containing `addedAt`. TIDAL's [authorization guide](https://developer.tidal.com/documentation/api-sdk/api-sdk-authorization) specifies authorization code with PKCE. Its [Developer Guidelines](https://developer.tidal.com/documentation/guidelines/guidelines-developer-guidelines) list transfer of data to another service as prohibited without express written approval.

- **Qobuz.** The current first-party [Qobuz web-player bundle](https://play.qobuz.com/resources/8.2.0-b034/bundle.js) calls `favorite/getUserFavorites`, `favorite/create`, and `favorite/delete`, passes `track_ids`, and maps `favorited_at`. Qobuz officially supports whole-library transfer through Soundiiz, including favorite tracks, in its [transfer help article](https://help.qobuz.com/en/articles/58315-how-to-transfer-your-music-library-for-free-with-soundiiz). That establishes product precedent, not authorization for SongMirror's private API use.

- **Deezer.** Introspection of Deezer's first-party [Pipe GraphQL endpoint](https://pipe.deezer.com/api) on the assessment date exposed `PrivateUser.userFavorites.tracks(first: 10, after)`, `PrivateUserFavoriteTrackEdge.favoritedAt`, and the single-ID `addTrackToFavorite` and `removeTrackFromFavorite` mutations. The schema labels those mutations as restricted to applications granted specific access.

- **Amazon Music.** The official [Tracks API](https://www.developer.amazon.com/docs/music/API_web_track.html) documents library add/delete and liked-track get/update, including the absence of a neutral value from its public like enum. The [User API](https://developer.amazon.com/docs/music/API_web_user.html) documents library reads and 100-item cursor pages. The current first-party [Dragonfly web bundle](https://d5fx445wy2wpk.cloudfront.net/release/web-platform/dragonfly.0fb788e3cadd84c31cbd.js) defines `LIKE`, `DISLIKE`, and `NEUTRAL` and an `updateTrackLikeState` mutation. The API is a closed beta, and the [Amazon Music Program Requirements](https://www.developer.amazon.com/docs/music/requ_AM-Program-Requirements.html) prohibit integrating Amazon Music or its content with a third-party music service.

- **Apple Music.** Apple's public [Add resource to favorites](https://developer.apple.com/documentation/applemusicapi/add-resource-to-favorites) endpoint uses `POST /v1/me/favorites`. The current first-party [Apple Music web bundle](https://music.apple.com/assets/index~3eb8a0d364.js) identifies a favorite playlist through `attributes.tags` containing `favorited` and its `UpdateFavoritesIntent` chooses `POST` or `DELETE /v1/me/favorites`. Apple's [MusicKit authentication guide](https://developer.apple.com/documentation/applemusicapi/user-authentication-for-musickit) requires a Music User Token for personal data. Apple Support states that connected third-party apps and websites can add favorites but [cannot remove them](https://support.apple.com/en-euro/111118).

- **YouTube Music.** YouTube Music Help documents the music-only [Liked Music behavior](https://support.google.com/youtubemusic/answer/6313542?hl=en), including that unliking does not remove a song from the broader library. The official YouTube API exposes a channel's [Liked Videos playlist](https://developers.google.com/youtube/v3/docs/channels#contentDetails.relatedPlaylists.likes); [playlist item reads](https://developers.google.com/youtube/v3/docs/playlistItems/list) are paginated at 50, and [`videos.rate`](https://developers.google.com/youtube/v3/docs/videos/rate) supports `like`, `dislike`, and `none` with a 50-unit cost. These sources do not expose a music-only API filter.

## Fit with SongMirror

This is a collection problem, not a playlist-discovery bug. Every current target implements the playlist-shaped [`MirrorTarget`](https://github.com/ahnafnafee/songmirror/blob/cf16740878f6144545d61b4641f4e61b0574ca28/songmirror/engine/targets/base.py#L46), and provider `list_playlists()` methods only enumerate playlists. That is why Spotify Liked Songs and TIDAL Favorites are absent.

The reconciliation core is already a good fit. It canonicalizes physical entries into unique membership, merges per-provider set deltas, guards destructive reads, and uses `added_at` when available for deterministic addition order. Favorite collections are naturally unique sets, so they avoid playlist duplicate-occurrence complexity.

The smallest coherent design is a non-creatable **virtual track collection** backed by a stable sentinel ID:

1. Add a collection kind/capability record (`playlist` versus `saved_tracks`) with `can_read`, `can_add`, `can_remove`, and `can_create=false`.
2. Expose one provider-specific row—Liked Songs, Favorite Tracks, Library Tracks, or Liked Music—but give all rows the same internal logical key, for example `saved-tracks`.
3. Route `tracks`, `add`, and `remove` on that sentinel to the provider endpoints above. Keep provider display names out of pairing logic because they are localized and semantically different.
4. Reuse `reconcile()` for membership and deletion baselines. Normalize provider timestamps to `added_at`, but promise membership preservation rather than historical ordering where a provider cannot set an old timestamp.
5. Hide or disable destructive sync when a backend lacks `can_remove`. Never implement Amazon unlike as `DISLIKE`, Apple public unlike through an undocumented endpoint, or YouTube Music unliking as library deletion.

One runner change is necessary for bidirectional use. One-way sync already supports explicit provider-ID links, but N-way reconciliation currently pairs only same-named rows and ignores those links. The virtual collection must therefore be paired by its stable logical key (or N-way must gain explicit-link support); relying on “Liked Songs” versus “Tracks” versus “Favorite Songs” will not work.

## Recommended delivery sequence

1. Build the collection abstraction and capability gating, with read-only previews and the existing two-clean-snapshot deletion safeguards.
2. Implement Spotify Saved Tracks through both the public OAuth contract and the default web-session library operations; require existing OAuth users to reconnect for the two library scopes.
3. Implement TIDAL Favorite Tracks technically, but do not ship it publicly until TIDAL approves cross-service transfer.
4. Add Qobuz and Deezer as explicitly experimental web-session backends.
5. Treat Apple exact removal, Amazon exact likes, and YouTube Music exact Liked Music as private-backend features. Keep their public fallbacks visibly asymmetric or semantically renamed.
6. Test empty collections, libraries larger than one page, unavailable tracks, revoked scopes, partial writes, read collapse, and removals made concurrently on multiple providers. Large migrations can drain over repeated passes under SongMirror's existing default 200-add cap.

In short: issue #35 is implementable without replacing the sync engine. The real work is adding a first-class, non-playlist collection contract, capability-aware UI and pairing, and provider-policy gates.
