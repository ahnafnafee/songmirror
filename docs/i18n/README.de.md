<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**Halte deine Playlists synchron.**<br>
Führe geplante Synchronisierungen auf deinem eigenen Server aus, kopiere eine Playlist einmalig oder behalte eine lokale Musikkopie für Jellyfin. Kostenlos und quelloffen.

[![Mit Docker starten][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Auf Ko-fi unterstützen][kofi-badge]][kofi-link]

[Geführte Installation](#guided-install) · [Unterstützte Dienste](#supported-services) · [Funktionen](#features) · [Screenshots](guide.de.md#screenshots) · [SongMirror unterstützen](#support) · [Website][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.de.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — Übersicht · Wiedergabelisten" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![Stern auf GitHub geben][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Schnellstart

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Öffne **http://localhost:8888**. Verbinde unter **Konten** deine Dienste. Wähle **Übertragungen** für eine einmalige Kopie oder **Synchronisierung** für regelmäßige Aktualisierungen.

<a id="guided-install"></a>

### Geführte Installation

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [Benutzerhandbuch](guide.de.md#guided-install)

<a id="app-language"></a>

### App-Sprache

Ändere die Sprache unter **Einstellungen → Allgemein → Sprache**. Wähle **Automatisch (Browser)**, um die Browsersprache zu übernehmen.

<a id="supported-services"></a>

## Unterstützte Dienste

Öffne **Konten → Konto hinzufügen** und suche nach einem Dienst.

| Dienst | Synchronisierung und Übertragung |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Playlists und Favoriten |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Playlists |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Server-Playlists |
| [Last.fm](https://www.last.fm/) | Lieblingstitel, meistgehörte Titel und Hörverlauf. Das Bearbeiten von Lieblingstiteln braucht eine Autorisierung. |
| [ListenBrainz](https://listenbrainz.org/) | Playlists und Lieblingsaufnahmen. Ein Benutzertoken erlaubt Änderungen. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Nutze öffentliche Playlist-Links oder deine angemeldete Bibliothek als Quelle. |

[Jeden Dienst verbinden](guide.de.md#connecting-each-service) · [Anleitung zu den Playlist-Adaptern](../music-service-adapters.md)

<a id="features"></a>

## ✨ Funktionen

- [Einseitige, bidirektionale und Mehrquellen-Synchronisierung](guide.de.md#how-it-works)
- [Einmalige Playlist-Übertragungen](guide.de.md#features) · [Verlauf und Wiederherstellung](../transfer-history.md)
- [Sicherungen der Playlist-Metadaten](guide.de.md#playlist-metadata-backups) · [Gespeicherte Alben übertragen](../saved-albums.md) · [Lokaler Download-Spiegel (Jellyfin)](guide.de.md#local-download-mirror-jellyfin)

[Benutzerhandbuch](guide.de.md)

<a id="support"></a>

## SongMirror unterstützen

Deine Unterstützung hilft, Wartung und Tests für die Musikdienste zu finanzieren.

[![Auf Ko-fi unterstützen][kofi-badge]][kofi-link]
[![Auf GitHub sponsern][sponsor-badge]][sponsor-link]

[Stern auf GitHub geben][stars-link] · [Nach oben](#readme-top)

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
