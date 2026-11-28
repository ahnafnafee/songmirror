<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**Mantenha suas playlists sincronizadas.**<br>
Hospede sincronizações agendadas, copie uma playlist uma única vez ou mantenha uma cópia local da música para o Jellyfin. Gratuito e de código aberto.

[![Executar com Docker][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Apoiar no Ko-fi][kofi-badge]][kofi-link]

[Instalação guiada](#guided-install) · [Serviços compatíveis](#supported-services) · [Recursos](#features) · [Capturas de tela](guide.pt.md#screenshots) · [Apoie o SongMirror](#support) · [Site][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.pt.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — Painel · Playlists" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![Dar uma estrela no GitHub][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Início rápido

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Abra **http://localhost:8888**. Em **Contas**, conecte seus serviços. Escolha **Transferências** para copiar uma vez ou **Sincronização** para atualizar listas em horários definidos.

<a id="guided-install"></a>

### Instalação guiada

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [Guia do usuário](guide.pt.md#guided-install)

<a id="app-language"></a>

### Idioma do aplicativo

Altere o idioma em **Configurações → Geral → Idioma**. Escolha **Automático (navegador)** para seguir o idioma do navegador.

<a id="supported-services"></a>

## Serviços compatíveis

Abra **Contas → Adicionar conta** e procure um serviço.

| Serviço | Suporte a sincronização e transferência |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Playlists e favoritos |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Playlists |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Playlists do servidor |
| [Last.fm](https://www.last.fm/) | Faixas favoritas, mais ouvidas e histórico. Autorize a edição dos favoritos. |
| [ListenBrainz](https://listenbrainz.org/) | Playlists e gravações favoritas. Um token de usuário permite alterações. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Use links de playlists públicas ou a biblioteca da conta conectada como fonte. |

[Conectando cada serviço](guide.pt.md#connecting-each-service) · [guia dos adaptadores de playlists](../music-service-adapters.md)

<a id="features"></a>

## ✨ Recursos

- [Sincronização unidirecional, bidirecional e de várias fontes](guide.pt.md#how-it-works)
- [Transferências únicas de playlists](guide.pt.md#features) · [Histórico e recuperação](../transfer-history.md)
- [Backups de metadados de listas de reprodução](guide.pt.md#playlist-metadata-backups) · [Transferência de álbuns salvos](../saved-albums.md) · [Espelho de download local (Jellyfin)](guide.pt.md#local-download-mirror-jellyfin)

[Guia do usuário](guide.pt.md)

<a id="support"></a>

## Apoie o SongMirror

Seu apoio ajuda a financiar a manutenção e os testes nos serviços de música.

[![Apoiar no Ko-fi][kofi-badge]][kofi-link]
[![Patrocinar no GitHub][sponsor-badge]][sponsor-link]

[Dar uma estrela no GitHub][stars-link] · [Voltar ao topo](#readme-top)

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
