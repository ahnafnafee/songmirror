<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**Gardez vos playlists synchronisées.**<br>
Hébergez vos synchronisations planifiées, copiez une playlist une seule fois ou conservez une copie locale de votre musique pour Jellyfin. Gratuit et open source.

[![Lancer avec Docker][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Soutenir sur Ko-fi][kofi-badge]][kofi-link]

[Installation guidée](#guided-install) · [Services compatibles](#supported-services) · [Caractéristiques](#features) · [Captures d'écran](guide.fr.md#screenshots) · [Soutenir SongMirror](#support) · [Site web][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.fr.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — Tableau de bord · Listes de lecture" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![Ajouter une étoile sur GitHub][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Démarrage rapide

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Ouvrez **http://localhost:8888**. Dans **Comptes**, connectez vos services. Choisissez **Transferts** pour une copie ponctuelle ou **Synchronisation** pour maintenir les listes à jour selon un calendrier.

<a id="guided-install"></a>

### Installation guidée

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [Guide d’utilisation](guide.fr.md#guided-install)

<a id="app-language"></a>

### Langue de l'application

Changez la langue dans **Paramètres → Général → Langue**. Choisissez **Automatique (navigateur)** pour utiliser la langue du navigateur.

<a id="supported-services"></a>

## Services compatibles

Ouvrez **Comptes → Ajouter un compte** et recherchez un service.

| Service | Synchronisation et transfert |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Playlists et favoris |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Playlists |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Playlists du serveur |
| [Last.fm](https://www.last.fm/) | Titres aimés, titres les plus écoutés et historique. Autorisez la modification des titres aimés. |
| [ListenBrainz](https://listenbrainz.org/) | Playlists et enregistrements aimés. Un jeton utilisateur permet les modifications. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Utilisez un lien public ou la bibliothèque de votre compte connecté comme source. |

[Connexion de chaque service](guide.fr.md#connecting-each-service) · [guide des adaptateurs de playlists](../music-service-adapters.md)

<a id="features"></a>

## ✨ Caractéristiques

- [Synchronisation à sens unique, bidirectionnelle ou depuis plusieurs sources](guide.fr.md#how-it-works)
- [Transferts ponctuels de playlists](guide.fr.md#features) · [Historique et récupération](../transfer-history.md)
- [Sauvegardes des métadonnées de la playlist](guide.fr.md#playlist-metadata-backups) · [Transfert des albums enregistrés](../saved-albums.md) · [Miroir de téléchargement local (Jellyfin)](guide.fr.md#local-download-mirror-jellyfin)

[Guide d’utilisation](guide.fr.md)

<a id="support"></a>

## Soutenir SongMirror

Votre soutien aide à financer la maintenance et les tests sur les services de musique.

[![Soutenir sur Ko-fi][kofi-badge]][kofi-link]
[![Parrainer sur GitHub][sponsor-badge]][sponsor-link]

[Ajouter une étoile sur GitHub][stars-link] · [Retour en haut](#readme-top)

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
