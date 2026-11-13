# Copy a YouTube playlist to another account

Use **Transfers** to copy a playlist from an old Google account into a new one. Select **YouTube Music** for YouTube and YouTube Music playlist links; the adapter uses their shared playlist and video IDs, so a copy keeps the original videos without searching for replacements.

Browser-connected accounts include regular YouTube video playlists in **Your library**, even when YouTube Music does not show them. Transfers read both the source and destination through regular YouTube so non-music videos retain their IDs and a retry skips videos already copied. Music sync keeps its existing music-only reads.

Playlists in your Music library appear first under **YouTube Music playlists**. The remaining lists are grouped under **YouTube videos** in playlist pickers and Browse. Sorting applies within each group; source pickers still distinguish playlists you created from those you follow, and destination pickers include only playlists you own.

## Public or unlisted source playlist

1. Connect your new Google account under **Accounts → YouTube Music**.
2. In **Transfers**, select **Paste a link** and choose the new account under **Open with account**.
3. Paste the old playlist's YouTube or YouTube Music URL and click **Open link**. The playlist does not need to be saved in the new account's library.
4. Select the new account as the destination, then choose **Create new** or an existing playlist you own.
5. Review the destination and click **Copy playlist**.

Only the destination account needs to be connected. The old playlist must be readable by that account.

## Private source playlist

Add two YouTube Music accounts on **Accounts**, label them so you can distinguish the old and new accounts, and connect each to its corresponding Google account. Under **Transfers → Your library**, choose the old account and its playlist, then select the new account as the destination.

## YouTube asks to create a channel

If YouTube requests channel setup when creating the destination playlist, open YouTube with the **destination** Google account and complete **Create a channel**, then return to SongMirror and retry the copy. Follow [YouTube's channel setup instructions](https://support.google.com/youtube/answer/1646861?hl=en). If that account already has a channel, reconnect it under **Accounts** using the correct YouTube channel. SongMirror leaves channel creation to you and keeps the playlist visibility you selected.

## Long playlists

Transfers read the full playlist, including all continuation pages, and are not truncated by the per-pass sync add cap. Videos already present in the destination are skipped by their video IDs; distinct videos with the same title and artist are retained. A repeated copy therefore adds only missing videos and keeps the destination's existing content.

YouTube may explicitly hide private or deleted videos. These appear in the transfer's unavailable count and are skipped; a failed or incomplete page instead stops the copy with an error.

Reading and matching finish before the copy writes videos. During **Copying tracks…**, the progress bar and added count advance only after YouTube confirms each video. Long copies can take several minutes. **Pause** and **Stop** take effect between videos, and resuming skips entries already copied.

The OAuth connection uses the YouTube Data API and can exhaust its daily write quota during a long copy. For large migrations, connect the destination using the **No-quota mode** browser-header option in the YouTube Music connection dialog. If a copy fails after writing some videos, start another copy into that existing destination playlist to continue with the missing videos. Browser sessions can expire and may need fresh headers.

## No-quota connection fails in Docker

Copy request headers from a signed-in `POST` request to `music.youtube.com/youtubei/v1/browse`. In Firefox, select **Copy → Copy Request Headers** in the Network tab. Include the full `Cookie`, `Authorization`, and `X-Goog-AuthUser` headers for the Google account you want to connect.

Google can reject browser cookies when SongMirror's server and the browser use different public IPs, even with freshly copied headers. Check whether Docker, the server, or the browser uses a VPN or proxy. Use the same public egress IP for both, or capture the headers from a browser running on the server, then paste a fresh copy. Reinstalling Firefox does not fix a routing mismatch. See the [upstream headless-auth report](https://github.com/sigma67/ytmusicapi/issues/962#issuecomment-5073561939).

SongMirror checks library access first because the account-menu endpoint can return a guest menu even for a working library session. An empty library still requires account confirmation; a signed-out empty response is never accepted as a successful connection. If both endpoints fail, no-quota mode cannot be enabled and the previous saved session is kept.
