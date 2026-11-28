<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**让你的播放列表始终保持同步。**<br>
自行托管定时同步、一次性复制播放列表，或为 Jellyfin 保留本地音乐镜像。免费且开源。

[![使用 Docker 运行][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![在 Ko-fi 上支持][kofi-badge]][kofi-link]

[引导式安装](#guided-install) · [支持的服务](#supported-services) · [特点](#features) · [截图](guide.zh.md#screenshots) · [支持 SongMirror](#support) · [网站][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.zh.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — 概览 · 播放列表" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![在 GitHub 上加星][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 快速入门

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

打开 **http://localhost:8888**，在**账户**中连接你使用的服务。选择**迁移**进行一次性复制，或选择**同步**按计划更新播放列表。

<a id="guided-install"></a>

### 引导式安装

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [用户指南](guide.zh.md#guided-install)

<a id="app-language"></a>

### 应用语言

在**设置 → 常规 → 语言**中更改语言。选择**自动（浏览器）**可跟随浏览器语言。

<a id="supported-services"></a>

## 支持的服务

打开 **账户 → 添加账户** 并搜索服务。

| 服务 | 同步和转移支持 |
| --- | --- |
| [Spotify](https://open.spotify.com/)、[TIDAL](https://tidal.com/)、[Qobuz](https://play.qobuz.com/)、[Deezer](https://www.deezer.com/)、[Amazon Music](https://music.amazon.com/)、[Apple Music](https://music.apple.com/)、[YouTube Music](https://music.youtube.com/)、[Navidrome](https://www.navidrome.org/)、[Subsonic](https://www.subsonic.org/) | 播放列表和收藏 |
| [SoundCloud](https://soundcloud.com/)、[Anghami](https://play.anghami.com/)、[Audiomack](https://audiomack.com/)、[Gaana](https://gaana.com/)、[JioSaavn](https://www.jiosaavn.com/) | 播放列表 |
| [Jellyfin](https://jellyfin.org/)、[Emby](https://emby.media/)、[Plex](https://www.plex.tv/media-server-downloads/)、[Mopidy](https://mopidy.com/)、[Lyrion Music Server](https://lyrion.org/) | 服务器播放列表 |
| [Last.fm](https://www.last.fm/) | 喜爱歌曲、热门歌曲和播放记录。授权后可修改喜爱歌曲。 |
| [ListenBrainz](https://listenbrainz.org/) | 播放列表和喜爱录音。用户令牌可启用写入。 |
| [QQ Music](https://y.qq.com/)、[LINE MUSIC](https://music.line.me/)、[Pandora](https://www.pandora.com/)、[Naver Vibe](https://vibe.naver.com/)、[NetEase Cloud Music](https://music.163.com/) | 可将公开歌单链接或已登录账号的音乐库用作来源。 |

[连接各个服务](guide.zh.md#connecting-each-service) · [歌单适配器指南](../music-service-adapters.md)

<a id="features"></a>

## ✨ 特点

- [单向、双向和多源同步](guide.zh.md#how-it-works)
- [一次性迁移播放列表](guide.zh.md#features) · [历史与恢复](../transfer-history.md)
- [播放列表元数据备份](guide.zh.md#playlist-metadata-backups) · [迁移已保存的专辑](../saved-albums.md) · [本地下载镜像(Jellyfin)](guide.zh.md#local-download-mirror-jellyfin)

[用户指南](guide.zh.md)

<a id="support"></a>

## 支持 SongMirror

你的支持有助于支付维护和跨音乐服务测试的费用。

[![在 Ko-fi 上支持][kofi-badge]][kofi-link]
[![在 GitHub 上赞助][sponsor-badge]][sponsor-link]

[在 GitHub 上加星][stars-link] · [返回顶部](#readme-top)

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
