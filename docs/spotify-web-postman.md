# Spotify first-party (sp_dc) API — Postman / curl reference

Reverse-engineered calls the cookie write backend uses. Everything authenticates as
Spotify's own web client via an `sp_dc` cookie — no dev app, no dev-mode gate.

> ⚠️ **`/tracks` is in an account-scoped rate-limit penalty box right now.** Any call to
> it (any IP, any machine) returns `429` **and resets the multi-hour drain clock**. The
> mint + pathfinder + client-token calls below are on other hosts and are safe to test
> anytime — but **leave `/tracks` alone until the box drains.**

## Collection variables

| var | value |
|---|---|
| `sp_dc` | your `sp_dc` cookie value |
| `bearer` | auto-filled by the token mint (§1) |
| `appver` | `1.2.95.312.gda5d7e47` |

A common `User-Agent` is required on every call (Spotify's edge 403s the default
`python-requests`/bare-curl UA):

```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0
```

---

## 1. Mint the Bearer token (TOTP handshake)

Minting is a two-step handshake: fetch server time, then call `/api/token` with two
time-based TOTP codes computed from a rotating secret. In Postman, request **1b** needs
a **pre-request script** to compute the code.

### 1a. Server time (no auth)

```bash
curl 'https://open.spotify.com/api/server-time' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0' \
  -H 'Cookie: sp_dc={{sp_dc}}'
# -> {"serverTime": 1721000000}
```

### 1b. Token

```bash
curl 'https://open.spotify.com/api/token?reason=init&productType=web-player&totp={{totp}}&totpServer={{totp}}&totpVer=61' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0' \
  -H 'Cookie: sp_dc={{sp_dc}}'
# -> {"accessToken":"BQ...","accessTokenExpirationTimestampMs":...,"isAnonymous":false}
```

**Pre-request Script** (computes `{{totp}}` — the whole trick):

```javascript
// Spotify TOTP, secret version 61 (newest)
const secret = ',7/*F("rLJ2oxaKL^f+E1xvP@N';
let keyStr = "";
for (let i = 0; i < secret.length; i++) keyStr += (secret.charCodeAt(i) ^ (i % 33 + 9)).toString();

const counter = Math.floor(Math.floor(Date.now() / 1000) / 30);
const counterHex = counter.toString(16).padStart(16, '0');
const hmacHex = CryptoJS.HmacSHA1(CryptoJS.enc.Hex.parse(counterHex),
                                  CryptoJS.enc.Utf8.parse(keyStr)).toString(CryptoJS.enc.Hex);
const offset = parseInt(hmacHex.slice(-1), 16);
const code = parseInt(hmacHex.substr(offset * 2, 8), 16) & 0x7fffffff;
pm.collectionVariables.set("totp", (code % 1000000).toString().padStart(6, '0'));
```

**Tests Script** (auto-saves the token to `{{bearer}}`):

```javascript
pm.collectionVariables.set("bearer", pm.response.json().accessToken);
```

Notes:
- Using local time for both `totp` and `totpServer` works while your clock is within
  ~15s of real time. For strictness, run 1a first and compute `totpServer` from its
  `serverTime` with the same function.
- Secret 61 is current. If you ever get `{"error":"totpVerExpired"}`, it rotated — the
  fallback secrets (try newest-first) are:
  - ver 60: `OmE{ZA.J^":0FG\Uz?[@WW`
  - ver 59: `{iOFn;4}<1PFYKPV?5{%u14]M>/V0hDH`
- Token lives ~1h.

---

## 2. `/tracks` — ISRC lookup (`.external_ids.isrc`)

ISRC lives **only** here (confirmed absent from pathfinder incl. `getTrack`, spclient
metadata, and the track HTML). **The recommended token is a client-credentials app
token from an EXTENDED-QUOTA app** — no cookie, no TOTP, and it reads on a rate bucket
separate from the user account (so it never hits the cookie penalty box).

```bash
# 2a. mint an app token (no cookie/TOTP) — use an EXTENDED-QUOTA app's creds
curl -s -X POST 'https://accounts.spotify.com/api/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials&client_id=CLIENT_ID&client_secret=CLIENT_SECRET'
# -> {"access_token":"BQ...","expires_in":3600}

# 2b. BATCH, up to 50 ids in ONE call (needs an extended-quota app; a dev-mode app 403s here)
curl 'https://api.spotify.com/v1/tracks?ids=6pHtgTMzsmP6ccN2ocv7XN,72Q62UFNdzIQj04Y4bwKv3' \
  -H 'Authorization: Bearer APP_TOKEN'

# single track (works on dev-mode apps too, but caps ~300 calls/24h)
curl 'https://api.spotify.com/v1/tracks/6pHtgTMzsmP6ccN2ocv7XN' -H 'Authorization: Bearer APP_TOKEN'
```

Response classification (which token you used):
- **`200`** + `external_ids.isrc` → extended-quota app on batch, or any app on single. ✅
- **`403 Forbidden`** → dev-mode app on the batch endpoint, OR an OAuth user token (both gated).
- **`429 "API rate limit exceeded"`** + `Retry-After` → rate-limited. On an **app** token it's a
  short/quota limit; on the **cookie** token it's per-account and can escalate into an
  hours-long penalty box — which is why the cookie token is used for writes, not ISRC.

---

## 3. Pathfinder — read playlist contents (safe host)

`api-partner.spotify.com` was never rate-limited. This is the read path; note it carries
**no ISRC**. Track `uid` (needed for removals) comes from here.

```bash
curl 'https://api-partner.spotify.com/pathfinder/v2/query' -X POST \
  -H 'Authorization: Bearer {{bearer}}' \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -H 'app-platform: WebPlayer' \
  -H 'spotify-app-version: {{appver}}' \
  -H 'Origin: https://open.spotify.com' \
  -H 'Referer: https://open.spotify.com/' \
  -H 'Accept: application/json' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0' \
  --data-raw '{"variables":{"uri":"spotify:playlist:PLAYLIST_ID","offset":0,"limit":100},"operationName":"fetchPlaylistContents","extensions":{"persistedQuery":{"version":1,"sha256Hash":"a65e12194ed5fc443a1cdebed5fabe33ca5b07b987185d63c72483867ad13cb4"}}}'
```

---

## 4. Pathfinder — add / remove

Same headers as §3; only `--data-raw` changes.

```bash
# ADD one track at the bottom
--data-raw '{"variables":{"playlistUri":"spotify:playlist:PID","playlistItemUris":["spotify:track:TID"],"newPosition":{"moveType":"BOTTOM_OF_PLAYLIST","fromUid":null}},"operationName":"addToPlaylist","extensions":{"persistedQuery":{"version":1,"sha256Hash":"47b2a1234b17748d332dd0431534f22450e9ecbb3d5ddcdacbd83368636a0990"}}}'
```

```bash
# REMOVE by item uid (uid from §3)
--data-raw '{"variables":{"playlistUri":"spotify:playlist:PID","uids":["ITEM_UID"]},"operationName":"removeFromPlaylist","extensions":{"persistedQuery":{"version":1,"sha256Hash":"47b2a1234b17748d332dd0431534f22450e9ecbb3d5ddcdacbd83368636a0990"}}}'
```

`moveType` also accepts `TOP_OF_PLAYLIST`, `AFTER_UID`, `BEFORE_UID`.

---

## 5. Client-token (only for spclient / create)

```bash
curl 'https://clienttoken.spotify.com/v1/clienttoken' -X POST \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0' \
  --data-raw '{"client_data":{"client_version":"{{appver}}","client_id":"d8a5ed958d274c2e8ee717e6a4b0971d","js_sdk_data":{"device_brand":"unknown","device_model":"unknown","os":"windows","os_version":"NT 10.0","device_id":"00000000000000000000000000000000","device_type":"computer"}}}'
# -> .granted_token.token   (send as the `client-token:` header on spclient calls)
```

---

## 6. Create a playlist (spclient)

Two steps: create (orphaned), then file it into the library rootlist so it shows up.

```bash
# 6a. create — returns {"uri":"spotify:playlist:NEW"}
curl 'https://spclient.wg.spotify.com/playlist/v2/playlist' -X POST \
  -H 'Authorization: Bearer {{bearer}}' \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -H 'Accept: application/json' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0' \
  --data-raw '{"ops":[{"kind":6,"updateListAttributes":{"newAttributes":{"values":{"name":"My New Playlist","formatAttributes":[],"pictureSize":[]},"noValue":[]}}}]}'
```

```bash
# 6b. get the rootlist revision (need it for 6c)
curl 'https://spclient.wg.spotify.com/playlist/v2/user/USER_ID/rootlist' \
  -H 'Authorization: Bearer {{bearer}}' \
  -H 'Accept: application/json' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0'
```

```bash
# 6c. file the new playlist into the library (addFirst)
curl 'https://spclient.wg.spotify.com/playlist/v2/user/USER_ID/rootlist/changes' -X POST \
  -H 'Authorization: Bearer {{bearer}}' \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -H 'Accept: application/json' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0' \
  --data-raw '{"baseRevision":"REVISION_FROM_6b","deltas":[{"ops":[{"kind":2,"add":{"items":[{"uri":"spotify:playlist:NEW"}],"addFirst":true}}]}],"wantResultingRevisions":false,"wantSyncResult":false,"nonces":[]}'
```

`USER_ID` is your cookie account's user id (pathfinder `profileAttributes`, or the
official `/v1/me` when not rate-limited).

---

## Gotchas

- **Pathfinder `sha256Hash` values rotate** on web-player releases. A rotated hash returns
  `{"errors":[{"message":"PersistedQueryNotFound"}]}` — the app re-scrapes them from the
  live bundle automatically; for manual testing, grab the current one from a browser
  DevTools network capture.
- **Hosts that were never rate-limited:** `open.spotify.com` (mint), `api-partner.spotify.com`
  (pathfinder), `clienttoken.spotify.com`, `spclient.wg.spotify.com`. Only
  `api.spotify.com` (the `/tracks` REST host) is penalty-boxed.
- **`client-token` is not needed for pathfinder** (Bearer-only) — only for spclient routes
  that ask for it.
