# Create Playlist Feature

Adds a "Create Playlist" feature that allows creating playlists from various sources — not just syncing existing ones.

## Features

- **File Import** with drag & drop (CSV, TXT, TSV, M3U)
- **Text Import** (copy-paste: `Artist - Title`)
- **URL Import** (Spotify, Apple Music, YouTube Music, etc.)
- **Auto-matching** with confidence scores and candidate picker for review
- **Append mode** to extend existing playlists (no duplicates)
- **Configurable default source** in settings
- **Imports list** with resume/delete functionality

## Technical

- 61+ tests
- 15 languages localized
- Crash recovery for interrupted imports
- Server-side limits (10MB upload, 10k tracks)
- Compatible with upstream `main`
