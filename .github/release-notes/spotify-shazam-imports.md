# Better Shazam to Spotify playlist imports

Import your Shazam CSV into Spotify with a better chance of finding the recording you meant. SongMirror searches more of Spotify’s catalog and uses album and duration details to distinguish live performances. When two recordings look equally plausible, you can compare the candidates or paste the exact Spotify track link.

## What changed

- Spotify search tries more results and title variations while preserving checks for live, studio, and other recording versions.
- The import review shows album, duration, and availability when Spotify supplies them.
- An optional MusicBrainz lookup can recover a recording code for a difficult match. SongMirror checks that code against Spotify before using it.
