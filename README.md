<div align="center"><a name="readme-top"></a>

<img src="./.github/assets/mark.png" alt="" height="72">

# SongMirror

**Keep your playlists in sync.**<br>
Self-host scheduled syncs, copy a playlist once, or keep a local music mirror for Jellyfin. Free and open source.

[![Run with Docker][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Support on Ko-fi][kofi-badge]][kofi-link]

[Guided installs](#guided-install) · [Supported services](#supported-services) · [Features](#features) · [Screenshots](docs/user-guide.md#screenshots) · [Support SongMirror](#support) · [Website][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="./README.md" lang="en">English</a> · <a href="docs/i18n/README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="docs/i18n/README.tr.md" lang="tr">Türkçe</a> · <a href="docs/i18n/README.es.md" lang="es">Español</a> · <a href="docs/i18n/README.zh.md" lang="zh">简体中文</a> · <a href="docs/i18n/README.fr.md" lang="fr">Français</a> · <a href="docs/i18n/README.pt.md" lang="pt">Português</a> · <a href="docs/i18n/README.de.md" lang="de">Deutsch</a> · <a href="docs/i18n/README.ja.md" lang="ja">日本語</a> · <a href="docs/i18n/README.hi.md" lang="hi">हिन्दी</a> · <a href="docs/i18n/README.bn.md" lang="bn">বাংলা</a> · <a href="docs/i18n/README.id.md" lang="id">Bahasa Indonesia</a> · <a href="docs/i18n/README.ko.md" lang="ko">한국어</a> · <a href="docs/i18n/README.it.md" lang="it">Italiano</a> · <a href="docs/i18n/README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="docs/user-guide.md#screenshots"><img src="./.github/assets/songmirror-preview.webp" alt="SongMirror — Dashboard · Playlists" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](./LICENSE)
[![Star on GitHub][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Quick Start

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Open **http://localhost:8888**. In **Accounts**, connect the services you use. Choose **Transfers** for a one-time copy, or **Sync** to keep playlists updated on a schedule.

<a id="guided-install"></a>

### Guided installs

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [User guide](docs/user-guide.md#guided-install)

<a id="app-language"></a>

### App language

Change the language in **Settings → General → Language**. Choose **Automatic (browser)** to follow your browser.

<a id="supported-services"></a>

## Supported services

Open **Accounts → Add account** and search for a service.

| Service | Sync and transfer support |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Playlists and favorites |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Playlists |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Server playlists |
| [Last.fm](https://www.last.fm/) | Loved tracks, top tracks, and scrobbles. Authorize writes to loved tracks. |
| [ListenBrainz](https://listenbrainz.org/) | Playlists and loved recordings. A user token enables writes. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Use public playlist links or the signed-in library as a source. |

[Connecting each service](docs/user-guide.md#connecting-each-service) · [playlist adapter guide](docs/music-service-adapters.md)

<a id="features"></a>

## ✨ Features

- [One-way, bidirectional, and multi-source sync](docs/user-guide.md#how-it-works)
- [One-time playlist transfers](docs/user-guide.md#features) · [History and recovery](docs/transfer-history.md)
- [Playlist metadata backups](docs/user-guide.md#playlist-metadata-backups) · [Saved album transfers](docs/saved-albums.md) · [Local download mirror (Jellyfin)](docs/user-guide.md#local-download-mirror-jellyfin)

[User guide](docs/user-guide.md)

<a id="support"></a>

## Support SongMirror

Your support helps fund maintenance and testing across music services.

[![Support on Ko-fi][kofi-badge]][kofi-link]
[![Sponsor on GitHub][sponsor-badge]][sponsor-link]

[Star on GitHub][stars-link] · [Back to top](#readme-top)

<!-- LINK GROUP -->

[docker-start-badge]: https://img.shields.io/badge/Docker-CE4512?logo=docker&logoColor=white&style=for-the-badge
[registry-badge]: https://img.shields.io/badge/GHCR-27221F?logo=github&logoColor=white&style=for-the-badge
[registry-link]: https://github.com/ahnafnafee/songmirror/pkgs/container/songmirror
[kofi-badge]: https://img.shields.io/badge/Ko--fi-8F3B25?logo=ko-fi&logoColor=white&style=for-the-badge
[kofi-link]: https://ko-fi.com/ahnafnafee
[sponsor-badge]: https://img.shields.io/badge/GitHub_Sponsors-27221F?logo=githubsponsors&logoColor=white&style=for-the-badge
[sponsor-link]: https://github.com/sponsors/ahnafnafee
[ci-shield]: https://img.shields.io/github/actions/workflow/status/ahnafnafee/songmirror/ci.yml?branch=main&label=CI&style=flat-square
[ci-link]: https://github.com/ahnafnafee/songmirror/actions/workflows/ci.yml
[license-shield]: https://img.shields.io/badge/license-MIT-CE4512?style=flat-square
[stars-shield]: https://img.shields.io/github/stars/ahnafnafee/songmirror?style=flat-square
[stars-link]: https://github.com/ahnafnafee/songmirror/stargazers
[website-link]: https://songmirror.ahnafnafee.dev/
