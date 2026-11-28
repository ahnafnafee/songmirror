<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**Mantén tus listas de reproducción sincronizadas.**<br>
Aloja sincronizaciones programadas, copia una lista una sola vez o conserva una copia local de la música para Jellyfin. Gratis y de código abierto.

[![Ejecutar con Docker][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Apoyar en Ko-fi][kofi-badge]][kofi-link]

[Instalación guiada](#guided-install) · [Servicios compatibles](#supported-services) · [Características](#features) · [Capturas de pantalla](guide.es.md#screenshots) · [Apoya SongMirror](#support) · [Sitio web][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.es.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — Panel · Listas de reproducción" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![Dar una estrella en GitHub][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Inicio rápido

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Abre **http://localhost:8888**. En **Cuentas**, conecta los servicios que utilizas. Elige **Transferencias** para una copia puntual o **Sincronización** para actualizar listas según un horario.

<a id="guided-install"></a>

### Instalación guiada

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [Guía de usuario](guide.es.md#guided-install)

<a id="app-language"></a>

### Idioma de la aplicación

Cambia el idioma en **Ajustes → General → Idioma**. Elige **Automático (navegador)** para seguir el idioma del navegador.

<a id="supported-services"></a>

## Servicios compatibles

Abre **Cuentas → Añadir cuenta** y busca un servicio.

| Servicio | Compatibilidad de sincronización y transferencia |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Listas de reproducción y favoritos |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Listas de reproducción |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Listas del servidor |
| [Last.fm](https://www.last.fm/) | Temas favoritos, temas más escuchados e historial. Autoriza la edición de favoritos. |
| [ListenBrainz](https://listenbrainz.org/) | Listas de reproducción y grabaciones favoritas. El token de usuario permite escribir. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Usa enlaces de listas públicas o la biblioteca de tu cuenta como origen. |

[Conectando cada servicio](guide.es.md#connecting-each-service) · [guía de adaptadores de listas](../music-service-adapters.md)

<a id="features"></a>

## ✨ Características

- [Sincronización unidireccional, bidireccional y desde varias fuentes](guide.es.md#how-it-works)
- [Transferencias puntuales de listas](guide.es.md#features) · [Historial y recuperación](../transfer-history.md)
- [Copias de seguridad de metadatos de listas de reproducción](guide.es.md#playlist-metadata-backups) · [Transferencia de álbumes guardados](../saved-albums.md) · [Espejo de descarga local (Jellyfin)](guide.es.md#local-download-mirror-jellyfin)

[Guía de usuario](guide.es.md)

<a id="support"></a>

## Apoya SongMirror

Tu apoyo ayuda a financiar el mantenimiento y las pruebas con los servicios de música.

[![Apoyar en Ko-fi][kofi-badge]][kofi-link]
[![Patrocinar en GitHub][sponsor-badge]][sponsor-link]

[Dar una estrella en GitHub][stars-link] · [Volver arriba](#readme-top)

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
