# SongMirror

Self-host playlist sync across music services. Copy playlists between accounts, keep them in sync on a schedule, or build a local music mirror for Jellyfin.

[Website](https://songmirror.ahnafnafee.dev/) · [User guide](docs/user-guide.md) · [Container image](https://github.com/ahnafnafee/songmirror/pkgs/container/songmirror)

<a id="quick-start"></a>

## Quick start

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Open [localhost:8888](http://localhost:8888) and connect your services under **Accounts**. Use **Transfers** for a one-time copy or **Sync** for scheduled updates. Compose stores your settings in `./data` and downloaded music in `./downloads`.

See the [Docker guide](docs/docker-image.md) for upgrades and storage, the [user guide](docs/user-guide.md#guided-install) for [Render](https://render.com/), [CapRover](https://caprover.com/), and [Portainer](https://www.portainer.io/) setup, or the [CLI instructions](docs/user-guide.md#headless-cli) for headless installs.

## Supported services

| What SongMirror can sync or transfer | Service websites |
| --- | --- |
| Playlists and favorites | [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) |
| Playlists | [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) |
| Playlists on your media server | [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) |
| Playlists and loved recordings | [ListenBrainz](https://listenbrainz.org/) |
| Loved tracks, top tracks, and scrobbles | [Last.fm](https://www.last.fm/) |
| Playlist sources | [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) |

The **Add account** wizard walks you through sign-in. See the [connection guide](docs/user-guide.md#connecting-each-service) and [playlist adapter notes](docs/music-service-adapters.md) for setup requirements and write support.

## What you can do

- Mirror one source, sync changes both ways, or merge several playlists into one. Playlist removals are opt-in.
- Copy a playlist once, review unmatched tracks, and see previous runs in [transfer history](docs/transfer-history.md).
- [Back up playlist metadata](docs/user-guide.md#playlist-metadata-backups), [transfer saved albums](docs/saved-albums.md), or [keep a local music mirror](docs/user-guide.md#local-download-mirror-jellyfin).

[![SongMirror dashboard and playlist browser](.github/assets/songmirror-preview.webp)](docs/user-guide.md#screenshots)

<a id="app-language"></a>

## Languages

Change the app language in **Settings → General → Language**.

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="./README.md" lang="en">English</a> · <a href="docs/i18n/README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="docs/i18n/README.tr.md" lang="tr">Türkçe</a> · <a href="docs/i18n/README.es.md" lang="es">Español</a> · <a href="docs/i18n/README.zh.md" lang="zh">简体中文</a> · <a href="docs/i18n/README.fr.md" lang="fr">Français</a> · <a href="docs/i18n/README.pt.md" lang="pt">Português</a> · <a href="docs/i18n/README.de.md" lang="de">Deutsch</a> · <a href="docs/i18n/README.ja.md" lang="ja">日本語</a> · <a href="docs/i18n/README.hi.md" lang="hi">हिन्दी</a> · <a href="docs/i18n/README.bn.md" lang="bn">বাংলা</a> · <a href="docs/i18n/README.id.md" lang="id">Bahasa Indonesia</a> · <a href="docs/i18n/README.ko.md" lang="ko">한국어</a> · <a href="docs/i18n/README.it.md" lang="it">Italiano</a> · <a href="docs/i18n/README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

[MIT License](LICENSE) · [Support SongMirror](https://ko-fi.com/ahnafnafee)
