<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**플레이리스트를 언제나 동기화하세요.**<br>
직접 운영하는 서버에서 예약 동기화를 실행하거나, 플레이리스트를 한 번 복사하거나, Jellyfin용 로컬 음악 사본을 유지할 수 있습니다. 무료 오픈 소스입니다.

[![Docker로 실행][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Ko-fi에서 후원하기][kofi-badge]][kofi-link]

[설치 마법사](#guided-install) · [지원 서비스](#supported-services) · [특징](#features) · [스크린샷](guide.ko.md#screenshots) · [SongMirror 후원하기](#support) · [웹사이트][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.ko.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — 대시보드 · 재생목록" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![GitHub에서 별표 누르기][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 빠른 시작

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

**http://localhost:8888** 을 열고 **계정**에서 사용하는 서비스를 연결하세요. 한 번 복사하려면 **전송**, 일정에 따라 업데이트하려면 **동기화**를 선택하세요.

<a id="guided-install"></a>

### 설치 마법사

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [사용자 가이드](guide.ko.md#guided-install)

<a id="app-language"></a>

### 앱 언어

**설정 → 일반 → 언어**에서 언어를 변경하세요. 브라우저 언어를 따르려면 **자동 (브라우저)**을 선택하세요.

<a id="supported-services"></a>

## 지원 서비스

**계정 → 계정 추가**를 열고 서비스를 검색하세요.

| 서비스 | 동기화 및 전송 지원 |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | 플레이리스트 및 즐겨찾기 |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | 플레이리스트 |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | 서버 플레이리스트 |
| [Last.fm](https://www.last.fm/) | 좋아하는 곡, 자주 듣는 곡, 재생 기록. 좋아하는 곡을 변경하려면 계정 인증이 필요합니다. |
| [ListenBrainz](https://listenbrainz.org/) | 플레이리스트 및 좋아하는 녹음. 사용자 토큰이 있으면 수정할 수 있습니다. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | 공개 재생목록 링크나 로그인한 계정의 보관함을 소스로 사용하세요. |

[각 서비스 연결](guide.ko.md#connecting-each-service) · [재생목록 어댑터 가이드](../music-service-adapters.md)

<a id="features"></a>

## ✨ 특징

- [단방향, 양방향 및 다중 소스 동기화](guide.ko.md#how-it-works)
- [일회성 재생목록 전송](guide.ko.md#features) · [기록 및 복구](../transfer-history.md)
- [재생목록 메타데이터 백업](guide.ko.md#playlist-metadata-backups) · [저장한 앨범 전송](../saved-albums.md) · [로컬 다운로드 미러(Jellyfin)](guide.ko.md#local-download-mirror-jellyfin)

[사용자 가이드](guide.ko.md)

<a id="support"></a>

## SongMirror 후원하기

후원금은 여러 음악 서비스의 연동을 유지하고 테스트하는 데 도움이 됩니다.

[![Ko-fi에서 후원하기][kofi-badge]][kofi-link]
[![GitHub에서 후원하기][sponsor-badge]][sponsor-link]

[GitHub에서 별표 누르기][stars-link] · [맨 위로](#readme-top)

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
