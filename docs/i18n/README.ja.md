<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**プレイリストをいつでも同期。**<br>
自分のサーバーで定期同期を実行したり、プレイリストを一度だけコピーしたり、Jellyfin 用に音楽をローカルへ保存したりできます。無料のオープンソースです。

[![Docker で起動][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Ko-fi で支援する][kofi-badge]][kofi-link]

[ガイド付きインストール](#guided-install) · [対応サービス](#supported-services) · [特徴](#features) · [スクリーンショット](guide.ja.md#screenshots) · [SongMirror を支援](#support) · [ウェブサイト][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.ja.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — ダッシュボード · プレイリスト" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![GitHub でスターを付ける][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 クイックスタート

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

**http://localhost:8888** を開き、**アカウント**で利用するサービスを接続します。一度だけコピーする場合は**転送**、定期的に更新する場合は**同期**を選びます。

<a id="guided-install"></a>

### ガイド付きインストール

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [ユーザーガイド](guide.ja.md#guided-install)

<a id="app-language"></a>

### アプリ言語

言語は **設定 → 一般 → 言語** で変更できます。ブラウザーの言語に合わせるには **自動（ブラウザー）** を選びます。

<a id="supported-services"></a>

## 対応サービス

**アカウント → アカウントを追加** を開いてサービスを検索します。

| サービス | 同期と転送の対象 |
| --- | --- |
| [Spotify](https://open.spotify.com/)、[TIDAL](https://tidal.com/)、[Qobuz](https://play.qobuz.com/)、[Deezer](https://www.deezer.com/)、[Amazon Music](https://music.amazon.com/)、[Apple Music](https://music.apple.com/)、[YouTube Music](https://music.youtube.com/)、[Navidrome](https://www.navidrome.org/)、[Subsonic](https://www.subsonic.org/) | プレイリストとお気に入り |
| [SoundCloud](https://soundcloud.com/)、[Anghami](https://play.anghami.com/)、[Audiomack](https://audiomack.com/)、[Gaana](https://gaana.com/)、[JioSaavn](https://www.jiosaavn.com/) | プレイリスト |
| [Jellyfin](https://jellyfin.org/)、[Emby](https://emby.media/)、[Plex](https://www.plex.tv/media-server-downloads/)、[Mopidy](https://mopidy.com/)、[Lyrion Music Server](https://lyrion.org/) | サーバーのプレイリスト |
| [Last.fm](https://www.last.fm/) | お気に入り、再生上位曲、再生履歴。お気に入りの変更には認証が必要です。 |
| [ListenBrainz](https://listenbrainz.org/) | プレイリストとお気に入りの録音。変更にはユーザートークンが必要です。 |
| [QQ Music](https://y.qq.com/)、[LINE MUSIC](https://music.line.me/)、[Pandora](https://www.pandora.com/)、[Naver Vibe](https://vibe.naver.com/)、[NetEase Cloud Music](https://music.163.com/) | 公開プレイリストのリンクやログイン済みアカウントのライブラリをソースとして使えます。 |

[各サービスを接続する](guide.ja.md#connecting-each-service) · [プレイリストアダプターガイド](../music-service-adapters.md)

<a id="features"></a>

## ✨ 特徴

- [一方向・双方向・複数ソースの同期](guide.ja.md#how-it-works)
- [プレイリストの一回限りの転送](guide.ja.md#features) · [履歴と復旧](../transfer-history.md)
- [プレイリストのメタデータのバックアップ](guide.ja.md#playlist-metadata-backups) · [保存済みアルバムの転送](../saved-albums.md) · [ローカル ダウンロード ミラー (Jellyfin)](guide.ja.md#local-download-mirror-jellyfin)

[ユーザーガイド](guide.ja.md)

<a id="support"></a>

## SongMirror を支援

ご支援は、音楽サービスとの連携を維持し、動作をテストするために役立ちます。

[![Ko-fi で支援する][kofi-badge]][kofi-link]
[![GitHub でスポンサーになる][sponsor-badge]][sponsor-link]

[GitHub でスターを付ける][stars-link] · [先頭へ戻る](#readme-top)

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
