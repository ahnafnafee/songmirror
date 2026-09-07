<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music 및 YouTube Music에 대한 자체 호스팅 상시 재생 목록 동기화 — 추가로 로컬 오디오 미러 지원 Jellyfin.<br/>
귀하가 소유하고 운영하는 Soundiiz, TuneMyMusic 및 FreeYourMusic에 대한 무료 오픈 소스 자체 호스팅 대안입니다.

**단방향, 다중 소스 병합, 신뢰할 수 있는 그룹 또는 전체 양방향(N방향) 동기화 · 일회성 재생 목록 전송 · ISRC까지 정확한 일치 · 브라우저에서 모두 가능**

[빠른 시작](#quick-start) · [특징](#features) · [스크린샷](#screenshots) · [항상 실행 중: Docker](#always-running-docker) · [작동 원리](#how-it-works) · [문제 신고][github-issues-link] · [기능 제안][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**이 프로젝트를 공유하세요**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>한 번 설정하면 귀하가 관리하는 모든 재생목록이 날짜가 추가된 순서대로 모든 서비스에 미러링됩니다.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror 데모 — 로고 공개, 대시보드, 단방향 및 양방향 동기화 설정, 라이브 재생 목록 전송 및 7개 음악 서비스 전반에 걸친 ISRC의 정확한 매칭" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">1080p 버전 보기</a></sup>

</div>

> [!NOTE]
> 그래픽 인터페이스 CLI가 없는 웹 앱 + 엔진 1개. 브라우저 UI를 클릭하여 서비스를 연결하고, 동기화를 구축하고, 재생 목록을 전송하거나 `.env` + 크론 스타일로 실행하세요. 둘 다 동일한 동기화 코어를 구동합니다.

<details>
<summary><kbd>목차</kbd></summary>

#### 목차

- [✨ 특징](#features)
- [📸 스크린샷](#screenshots)
- [🚀 빠른 시작](#quick-start)
  - [앱 언어](#app-language)
- [🐳 항상 실행 중: Docker](#always-running-docker)
- [⚙️ 작동 원리](#how-it-works)
  - [매칭](#matching)
  - [다중 소스 병합 동기화](#multi-source-merge-sync)
  - [권위 있는 그룹](#authoritative-groups)
  - [양방향(N방향) 동기화](#bidirectional-n-way-sync)
- [📦 재생목록 메타데이터 백업](#playlist-metadata-backups)
- [💿 로컬 다운로드 미러(Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 각 서비스 연결](#connecting-each-service)
  - [자격증명 갱신](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ 그래픽 인터페이스 CLI 없이](#headless-cli)
- [🛡️ 안전 보호 장치](#safety-rails)
- [🗃️ 캐싱 및 노래 보관](#caching-song-archive)
  - [매핑 해결](#resolve-mappings)
- [🧱 프로젝트 레이아웃](#project-layout)
- [🩺 문제 해결](#troubleshooting)
- [📄 라이센스](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ 특징

SongMirror 수동으로 다시 추가하거나 하나씩 복사하거나 라이브러리를 유지하는 유료 클라우드 서비스 없이 재생 목록을 어디서나 동일하게 유지합니다. 크로스 플랫폼, 자체 호스팅 및 오픈 소스입니다.

- 🔁 **추가 전용이 아닌 진정한 미러링** - 추가 및 제거. 진실의 출처(기본적으로 Spotify)를 선택하면 다른 사람들도 이를 따릅니다.
- ⇆ **신뢰할 수 있는 그룹** — 두 개 이상의 서비스(예: Spotify + Apple Music)를 신뢰하고 선택한 다른 모든 서비스는 대상 전용 미러로 유지됩니다.
- ⇄ **양방향 N-way 동기화** — 연결된 서비스의 추가 또는 제거는 제거 가드 뒤에서 에코 없이 다른 모든 서비스에 전파됩니다.
- ⇉ **다중 소스 병합 동기화** — 공개 목록을 저장하거나 따르지 않고 라이브러리 재생 목록과 공개 재생 목록 URL의 중복 제거된 통합을 하나의 대상으로 예약합니다.
- ♥ **좋아요 및 즐겨찾는 트랙** — 7개 음악 제공업체 전체에서 각 서비스에 내장된 좋아요 컬렉션을 대상의 즐겨찾기 또는 새로운 이름의 재생목록에 동기화합니다.
- 🎯 **ISRC에 의한 정확한 일치** — 가능한 경우 정확한 녹화 ID, 대략적인 Unicode 호환 제목/아티스트/길이 대체(추천 아티스트 크레딧의 차이, "- 2015 리마스터" 접미사, 비라틴어 스크립트, 비디오 전용 업로드 — 모두 처리됨).
- 🎛️ **여러 개의 이름이 지정된 동기화** — 각각 고유한 서비스, 재생 목록, 일정 및 안전 제한이 있는 독립적인 동기화를 원하는 만큼 많이 설정하세요.
- ↪️ **일회성 전송** — 실시간 진행률 표시줄을 사용하여 한 서비스에서 다른 서비스로 재생 목록을 복사합니다. 복사 도중 일시 중지, 재개 또는 중지하고 일치하지 않는 트랙을 수동으로 해결합니다.
- 🕒 트랙을 추가하거나 트랙 순서를 유지합니다. 기본적으로 대상의 끝에 복사가 빠르고 추가됩니다. 최근 추가된 항목 유지 순서를 켜서 가장 오래된 새 트랙 이후에 트랙을 다시 작성하여 날짜 추가 순서가 소스와 일치하도록 합니다.
- 🔗 **링크에서 전송** - 연결된 서비스의 공개 재생목록 URL을 붙여넣고 바로 복사하세요. 먼저 저장하거나 따라갈 필요가 없습니다.
- 🌐 **팔로우한 재생목록** — 내가 만든 재생목록뿐만 아니라 팔로우하지만 소유하지 않은 재생목록도 동기화하고 전송할 수 있습니다.
- 📦 **예약된 메타데이터 백업** — JSON/XML, 보존 제한 및 가시적인 성공/실패 내역을 포함하여 영구 앱 데이터에서 자체 일정에 따라 계정의 전체 재생 목록 라이브러리를 보관합니다. 일회성 다운로드 및 가져오기 가능 Soundiiz JSON도 계속 사용할 수 있습니다.
- 💿 **로컬 다운로드 미러** — Jellyfin의 `AlbumArtist/Album` 레이아웃에 재생 목록당 하나의 폴더, 표지 및 자동 업데이트 `.m3u8`가 포함된 오프라인 오디오를 유지합니다.
- 🛡️ **안전 보호** — 기본적으로 시뮬레이션, 패스별 추가/제거 한도, 순 손실 보호, 빈 스냅샷 보호, 토큰 만료 시 쓰기 없이 중단.
- 🗃️ **점점 늘어나는 노래 아카이브** — 이제까지 본 모든 트랙은 로컬 SQLite 데이터베이스(이름, 아티스트, 앨범, ISRC, 원시 메타데이터, 처음/마지막으로 본)에 기록됩니다.
- 🧭 **편집 가능한 일치 기록** — 영원히 일치하지 않는 "일치 없음" 결과를 포함하여 매핑 페이지에서 서비스별로 캐시된 모든 트랙 일치를 검색, 수정 및 삭제합니다.
- 🐳 어디서나 실행됩니다. 브라우저 앱용 `docker compose up -d` 또는 일반 CLI + cron / Task Scheduler 중 하나입니다.

> [!IMPORTANT]
> 자체 호스팅 및 비공개 설계. 귀하의 청취 데이터와 자격 증명은 귀하의 컴퓨터를 떠나지 않습니다. 웹 UI에는 인증이 없습니다. 이를 LAN에 바인딩하고 인터넷으로 포트 포워딩하지 마세요.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 스크린샷

<div align="center">

**모든 라이브러리에 대한 단일 대시보드 — 동기화 상태, 작업, 실시간 활동 및 서비스 상태**

<img src="../../.github/assets/dashboard.png" alt="SongMirror 대시보드에는 Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music에 대한 동기화 상태, 구성된 작업, 실시간 활동 및 상태가 표시됩니다. YouTube Music 및 Jellyfin" width="82%">

**짧은 마법사로 단방향, 다중 소스 병합, 권한 있는 그룹 또는 양방향 등 원하는 수의 동기화를 설정하세요.**

<img src="../../.github/assets/sync-wizard.png" alt="Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music 및 YouTube Music 간의 양방향 동기화를 위한 서비스를 선택하는 SongMirror 설정 마법사" width="82%">

**브라우저의 모든 서비스 연결 - 원클릭 OAuth, 안내식 토큰 붙여넣기 또는 API 키**

<img src="../../.github/assets/accounts.png" alt="Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music 및 Jellyfin 연결을 위한 계정 페이지" width="82%">

**여러 서비스에서 재생 목록을 찾아보고 페어링하세요.**

<img src="../../.github/assets/playlists.png" alt="커버 아트 및 트랙 수를 사용하여 연결된 서비스 전반에서 재생 목록 탐색" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 빠른 시작

가장 빠른 실행 방법은 Docker입니다. Compose는 게시된 이미지를 가져오고 웹 UI를 제공하며 일정에 따라 동기화를 실행합니다.

자동 재시작을 통한 영구 설치의 경우:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

또는 저장소를 복제하지 않고 직접 공개 GHCR 이미지를 사용해 보세요.

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

그런 다음 `http://localhost:8888`를 열고 브라우저에서 서비스를 연결하세요. Compose 설정을 시작하려면 `.env`가 필요하지 않습니다. 모든 것이 UI에서 구성되고 `./data` 아래에 저장됩니다.

직접 `docker run` 옵션은 일회용입니다. `docker stop songmirror`는 컨테이너와 해당 구성을 제거합니다. 영구 자격 증명, 캐시 및 다운로드가 포함된 내구성 있는 설치를 위해 Compose를 사용하거나 태그 및 다이제스트 고정을 위해 [컨테이너 이미지 가이드](../docker-image.md)를 참조하세요.

Docker 없이 실행하는 것을 선호하시나요?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> [`uv`](https://docs.astral.sh/uv/)(Python 3.13+)가 필요합니다. 로컬 다운로드 미러의 경우 `uv tool install spotdl`도 있고 PATH에는 `ffmpeg`가 있습니다.

<a id="app-language"></a>

### 앱 언어

SongMirror는 영어, 아랍어, 터키어, 스페인어, 중국어 간체, 프랑스어, 포르투갈어, 독일어, 일본어, 힌디어, 벵골어, 인도네시아어, 한국어, 이탈리아어, 베트남어를 지원합니다. 처음 실행할 때 지역별 변형을 포함한 브라우저 언어 기본 설정을 순서대로 확인하고, 처음으로 지원되는 언어를 사용합니다. 지원되는 언어가 없으면 영어를 사용합니다. **설정 → 일반 → 언어**에서 언어를 바꿀 수 있습니다. 선택은 이 브라우저에 저장되며 페이지를 새로고침해도 유지됩니다. **자동 (브라우저)**을 선택하면 다시 브라우저 기본 설정을 따릅니다. 아랍어 화면은 오른쪽에서 왼쪽으로 표시됩니다. 재생 목록, 아티스트와 서비스의 이름, 인증 정보 및 진단 로그는 원래 값을 유지합니다.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 항상 실행 중: Docker

Docker 컨테이너는 권장되는 배포입니다. 웹 UI를 제공하고 일정에 따라 동기화를 실행하며 호스트에서 다시 시작됩니다. Compose는 `ghcr.io/ahnafnafee/songmirror:latest`를 가져와 `songmirror`로 실행하고 `./data`에 모든 인증 + 캐시를 유지합니다.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

업데이트하려면 `docker compose up -d --pull always`를 실행하세요. 대신 현재 체크아웃을 빌드하려면 `docker compose up -d --build`를 실행하세요. 태그, 다이제스트 고정, 직접 가져오기, 확인, 업데이트 및 롤백에 대해서는 [컨테이너 이미지 가이드](../docker-image.md)를 참조하세요.

시작하려면 `.env`이 필요하지 않습니다. 모든 것이 브라우저에서 구성되고 `./data`에 저장됩니다. OAuth, 파트너 토큰 및 API-키 설정은 모두 계정 페이지에 있습니다. 각 마법사는 서비스별 전제 조건과 정확한 콜백 URI를 설명합니다. 그런 다음 동기화 페이지에서 동기화를 구축하세요.

다른 컴퓨터에서 SongMirror을 열면 `http://<server>:8888`에서 작동합니다. 기본 Spotify 연결은 붙여넣은 `sp_dc` 웹 세션을 사용하므로 개발자 앱이나 콜백 URL이 필요하지 않습니다. 의도적으로 Docker 뒤의 기존 개발자 앱 OAuth 대체 또는 역방향 프록시를 사용하는 경우 `.env`에서 브라우저에 표시되는 기본 URL을 설정하세요.

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

그러면 SongMirror이 `https://music.example.com/oauth/spotify/callback`를 광고합니다. Spotify 앱 대시보드에 정확한 URI를 등록하고 `docker compose up -d --force-recreate`를 사용하여 컨테이너를 다시 만듭니다. 역방향 프록시 기본 경로도 지원됩니다(예: `https://example.com/songmirror`). 모든 비루프백 리디렉션의 경우 [Spotify에는 HTTPS이 필요합니다.](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) 일반 HTTP은 `127.0.0.1`와 같은 리터럴 루프백 주소에만 허용되며 LAN IP 또는 `localhost`에는 허용되지 않습니다.

| | |
| --- | --- |
| 이미지 | `ghcr.io/ahnafnafee/songmirror:latest`는 AMD64 및 ARM64을 지원합니다. 각 빌드는 커밋별 `sha-...` 태그와 함께 게시됩니다. `v1.2.3`와 같은 Git 태그는 `1.2.3`, `1.2` 및 `1`를 추가로 게시합니다. 불변 다이제스트를 고정하려면 [컨테이너 이미지 가이드](../docker-image.md)를 사용하세요. |
| 포트 | UI는 호스트 8888에 게시됩니다(`docker-compose.yml`의 `8888:8080` 매핑, 충돌하는 경우 호스트 측 변경). LAN 전용 — 인터넷으로 포트 포워딩하지 마세요. UI에는 아직 인증이 없습니다. |
| 지속성 | `./data`에는 `playlist_backups/` 아래에 자격 증명, 토큰, 캐시, 노래 아카이브 및 예약된 재생 목록 스냅샷이 보관되어 있습니다. 재구축 시 설정과 아카이브를 유지하려면 백업하세요. |
| 다운로드 | `DOWNLOAD_DIR`(`.env` 또는 쉘에서)를 호스트 음악 디렉토리(예: `F:\Torrent\Music`)로 설정합니다. compose는 이를 `/music`에 바인드 마운트합니다. Docker에서 `JELLYFIN_URL`를 `http://host.docker.internal:8096`로 설정하세요. |
| 만료된 세션 | 갱신 가능한 세션은 다음 예약 또는 수동 전달에서 복구됩니다. TIDAL 웹 플레이어 세션은 캡처된 새로 고침 토큰에서 갱신됩니다. Qobuz 및 Apple Music 토큰은 거부되면 다시 붙여넣어야 합니다. 다시 시작할 필요가 없습니다. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ 작동 원리

소스에 존재하는 선택된 각 재생 목록 이름에 대한 모든 패스:

1. 소스 재생목록(트랙, ISRC, 추가 날짜)의 스냅샷을 찍습니다.
2. 해당 서비스의 계정 승인 재생 목록 API을 통해 선택되고 연결된 모든 대상에서 동일한 이름의 재생 목록을 동시에 조정합니다.
3. 누락된 트랙이 해결되고(캐시된 링크 → ISRC → 점수가 매겨진 검색) 가장 오래된 것부터 추가됩니다. 소스에서 사라진 트랙은 가드 뒤에서 제거됩니다.
4. 선택적으로 [spotDL](https://github.com/spotDL/spotify-downloader)는 재생목록별로 로컬 오디오 폴더를 동기화합니다.

기본 진실 소스는 Spotify이지만 단방향 모드는 공급자에 구애받지 않습니다. 대신 연결된 모든 재생 목록 피어가 소스가 될 수 있습니다.

<a id="matching"></a>

### 매칭

교차 서비스 도구가 사용하는 것과 동일한 계층 구조([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): 정확한 식별자 → 검색 → 퍼지 점수.

1. 캐시된 링크 — 소스 트랙이 대상의 카탈로그 ID/비디오 ID와 일치하면 해당 링크가 저장되고 재사용됩니다(제목 드리프트에 영향을 받지 않음).
2. ISRC — 서비스가 노출하는 정확한 녹음 ID입니다.
3. 점수가 매겨진 검색 — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, 원시 및 로마자 표기([anyascii](https://github.com/anyascii/anyascii)) 제목과 아티스트에 대해 기간별로 고정됩니다. 하드코딩 없이 다음을 처리합니다.
   - 다중 아티스트 크레딧 — 한 서비스에는 모든 기능이 나열되고, 다른 서비스에는 기본 기능이 나열됩니다(`Arijit Singh, Ved Sharma, …` ← `Arijit Singh`).
   - 제목 장식 — `(feat. …)`, `- 2015 Remaster`, `(From "…")`, 추가 "공식 뮤직 비디오" 접미사.
   - 음역 — 키릴 문자/벵골어/그리스어/아랍어(`Камин` ← `Kamin`, `নেশার বোঝা` ← `Neshar Bojha`).
   - 동영상 전용 트랙 — YouTube 검색은 YT에 업로드로만 게시되는 인디/OST 트랙에 대해 `videos` 필터로 대체됩니다.

기간 앵커는 느슨한 제목 일치를 잠금 해제하므로 길이가 일치하지 않는 경우 다른 버전(`Runaway - Piano Version`) 또는 잘못된 아티스트 표지는 허용되지 않습니다. 확실한 일치가 없는 트랙은 보고되고 건너뜁니다.

<a id="multi-source-merge-sync"></a>

### 다중 소스 병합 동기화

소스 병합 작업은 하나 이상의 명시적 재생 목록을 선택한 하나의 대상으로 결합합니다. 각 소스는 연결된 계정의 라이브러리 또는 붙여넣은 공개 공급자 URL에서 가져올 수 있습니다. 후자는 공급자 및 재생 목록 ID로 한 번 확인되므로 재생 목록을 저장하거나 따를 필요가 없으며 예약된 실행은 임의 URL을 재생하지 않습니다.

- 하나의 멤버십 조합 — 대상이 조정되기 전에 모든 구성 요소를 읽습니다. 공유 ISRC는 하나의 녹음입니다. ISRC이 없으면 정확한/보수적인 제목, 아티스트, 버전 및 기간 증거가 중복되지 않습니다.
- 결정적 순서 — 소스 설명자 우선순위가 먼저이고 그 다음에는 각 소스 재생 목록에서 반환된 순서입니다. 첫 번째 항목은 대상 위치와 표시 메타데이터를 소유합니다. 이후 복사본은 누락된 ID 메타데이터만 보강합니다.
- Union-safe 제거 — 대상 트랙은 전체 패스에서 모든 구성 소스에 해당 트랙이 없음을 확인한 경우에만 제거할 수 있습니다. 실패했거나, 잘렸거나, 형식이 잘못되었거나, 사용할 수 없거나 알 수 없을 정도로 비어 있는 소스는 해당 패스에 대한 모든 제거를 비활성화하는 반면, 읽을 수 있는 소스에서 안전한 추가는 계속될 수 있습니다.
- 기본적으로 추가 전용 — 모든 대상 전용 트랙을 유지하려면 모든 소스에 없는 트랙 제거를 꺼진 상태로 둡니다. 이 기능을 켜면 전체 읽기 가드가 통과한 후 일반적인 패스별 제거 캡이 선택됩니다.

병합 작업은 현재 하나의 공급자 재생 목록을 대상으로 합니다. 별도의 Spotify 주도 로컬 다운로드/Jellyfin 미러는 집계 작업에 사용할 수 없습니다.

<a id="authoritative-groups"></a>

### 권위 있는 그룹

두 개 이상의 서비스에서 동일한 논리적 재생 목록을 적극적으로 선별하지만 선택된 다른 모든 서비스가 이를 따르도록 하려는 경우 신뢰할 수 있는 그룹을 사용합니다. 일반적인 설정은 권한으로 Spotify + Apple Music, 미러로 TIDAL, Qobuz, Deezer, Amazon Music 및 YouTube Music을 사용하는 것입니다.

- 멤버십은 기관에서만 제공됩니다. Spotify 또는 Apple Music에 추가된 트랙은 다른 기관과 모든 미러에 전파됩니다. 미러에만 추가된 트랙은 드리프트입니다. 그것은 결코 당국으로 다시 수입되지 않습니다.
- 단일 주문 권한 - 재생 목록 이름과 추가 순서를 제공하는 권한을 선택합니다. 다른 당국은 여전히 ​​회원 변경에 기여하고 있습니다.
- 확인된 제거는 어느 기관에서나 전파됩니다. 부재는 두 번의 연속적인 전체 읽기에 나타나야 항목을 삭제할 수 있습니다. 동시에 권위 측 추가가 제거보다 승리합니다.
- 미러는 투표를 하지 않습니다. 미러에서 트랙을 삭제하면 해당 미러가 복구됩니다. Spotify 또는 Apple Music의 트랙은 삭제되지 않습니다.
- 안전한 첫 번째 통과 - 모든 권한 세트에는 자체 기준이 있습니다. 첫 번째 성공적인 패스에서는 누락된 트랙이 추가될 수 있지만 이후 패스에서 기준선이 안정적이라는 것이 입증될 때까지 모든 제거가 유지됩니다.
- 실패 시 폐쇄 - 권한이 연결 해제되었거나 읽을 수 없거나 해당 재생 목록을 열거나 생성할 수 없는 경우 자동으로 더 적은 권한으로 돌아가는 대신 해당 논리 재생 목록을 건너뜁니다.

삭제는 명시적으로 활성화해야 하며 삭제 건수에도 상한이 적용됩니다. 미러의 불필요한 곡을 삭제해 기준 소스의 곡 목록과 맞추려면 작업에서 **곡 삭제 동기화**를 켜거나, 그래픽 인터페이스 없이 실행할 때 `MAX_REMOVALS`를 설정하세요.

<a id="bidirectional-n-way-sync"></a>

### 양방향(N방향) 동기화

기본적으로 하나의 공급자가 진실의 소스이며 편집 흐름은 단방향입니다. N-way 모드에서는 선택된 모든 제공자가 피어입니다. 어느 하나에서 트랙을 추가하거나 제거하면 변경 사항이 다른 제공자에게 전파됩니다.

양방향 동기화는 상태 비저장이 불가능하므로 각 논리 재생 목록의 정식 멤버십은 모든 정리 패스 후에 스냅샷이 생성됩니다. 각 패스는 모든 공급자를 해당 스냅샷과 비교하고, 변경 사항을 통합하고, 모든 사람을 결과에 맞게 조정합니다.

- 에코 없음 — 전파된 추가는 스냅샷의 일부가 되므로 다시 되돌아오지 않습니다.
- 충돌 시 추가 승리 - 노래를 잃는 것은 추가 노래를 유지하는 것보다 더 나쁩니다.
- 읽기 축소 보호 — 공급자가 갑자기 기준보다 훨씬 적은 수의 트랙을 읽는 경우(일시적인 API 딸꾹질) 해당 패스를 건너뛰므로 잘못된 읽기 하나가 연속적으로 대량 삭제될 수 없습니다.
- 단방향과 동일한 보호 장치(패스당 `MAX_ADDS` / `MAX_REMOVALS` 한도 및 순 손실 보호가 모든 쓰기 측면에서 유지됩니다.)
- **삭제는 직접 활성화해야 합니다** — `MAX_REMOVALS`의 기본값은 0입니다. 한 서비스에서 곡을 삭제하거나 라이선스 문제로 곡이 내려가더라도 다른 서비스에는 보관되며 변경 내용은 로그에만 기록됩니다. 삭제를 다른 서비스에 반영하려면 상한을 설정하거나 화면의 **곡 삭제 동기화**를 켜세요.

> 항상 시뮬레이션이 먼저입니다. `--execute` 없이 실행하고(또는 UI에서 미리보기 사용) 계획을 읽어보세요. 모든 제안된 추가/제거가 작성되기 전에 모든 공급자에 대해 인쇄됩니다.

<a id="liked-and-favorite-tracks"></a>

### 좋아요 및 즐겨찾는 트랙

동기화의 재생 목록 단계에서 소스 서비스에 내장된 좋아요 컬렉션을 선택하세요. SongMirror 그런 다음 선택한 모든 대상의 위치를 ​​묻습니다. 해당 서비스의 좋아요/즐겨찾기 컬렉션으로 직접 이동하거나 제안된 이름을 편집할 수 있는 새 재생 목록으로 이동합니다. 새로운 선택 항목은 좋아요 전용입니다. 또한 모든 일반 재생목록을 동기화하거나 개별 재생목록을 선택하여 두 가지를 모두 포함하도록 설정하세요.

이 기능은 Spotify 좋아요 노래, TIDAL/Qobuz/Deezer 즐겨찾는 트랙, Amazon Music 내가 좋아하는 노래, Apple Music 좋아하는 노래, YouTube Music 좋아요 음악에 적용됩니다. 동일한 단방향, 권한 있는 그룹 및 N방향 조정 경로와 안전 한도가 적용됩니다. 일반 재생 목록과 마찬가지로 **곡 삭제 동기화**를 켜기 전까지 삭제는 기본적으로 꺼져 있습니다.

TIDAL의 로그인된 웹 플레이어 권한은 `r_usr` 및 `w_usr`을 전달할 때 일반 재생 목록과 기본 즐겨찾기 트랙을 모두 처리합니다. 전체 로그인 토큰 응답을 캡처하면 SongMirror 새로 고침 토큰과 단기 Bearer 토큰이 제공되므로 세션이 자동으로 갱신될 수 있습니다.

이러한 통합 중 일부는 공급자의 자사 웹 인터페이스를 사용하며 예고 없이 변경될 수 있습니다. [타당성 평가](../design/2026-09-01-liked-tracks-sync-feasibility.md)는 API 및 각 공급자의 배포 제약 조건을 기록합니다.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 재생목록 메타데이터 백업

백업에는 두 번째 공급자나 동기화 작업이 필요하지 않습니다.

- 설정 → 재생목록 백업에서 상단의 백업 추가를 이용하여 연결된 계정을 추가하세요. JSON 또는 XML을 선택한 다음 매일 또는 매주 등 빈도를 선택하세요. 사용자 정의 간격은 숫자와 단위를 사용합니다. Keep 백업은 보존 사전 설정, 사용자 정의 개수 또는 모든 백업을 제공합니다.
- 백업의 기본값은 `data/playlist_backups/<account-profile-id>/`(또는 Docker의 `/data/playlist_backups/<account-profile-id>/`)입니다. 내장된 폴더 선택기에서 백업 폴더를 클릭하거나 수동으로 경로 입력을 선택합니다. 사용자 정의 폴더에는 여전히 각 계정에 대해 별도의 하위 폴더가 있습니다. 기본 백업 폴더 사용은 기본값을 복원합니다. 위치를 변경하면 향후 백업에 영향을 미칩니다. 오래된 파일은 그대로 유지됩니다. 보존 및 최신 다운로드는 선택한 위치에 적용됩니다. 일정을 제거해도 저장된 파일은 삭제되지 않습니다.
- 설정 → 다운로드 & Jellyfin → 다운로드 폴더는 동일한 내장 선택기와 수동 항목을 사용합니다. Jellyfin 라이브러리에 액세스할 수 있는 폴더를 선택하세요. 다운로드는 동기화 탭에서 선택한 각 동기화 일정을 따릅니다. 선택기는 내부적으로 Docker 매핑(`/music`)을 유지하면서 구성된 호스트 경로(예: `F:\Torrent\Music`)를 표시합니다. 기존 다운로드 마운트는 변경되지 않습니다. 추가 호스트 폴더는 먼저 Docker 바인드 마운트로 공유되어야 합니다. 마운트 해제된 폴더를 선택하면 오류가 표시되고 현재 설정은 변경되지 않은 상태로 유지됩니다.

- 동일한 설정 카드에는 다음 실행, 저장된 스냅샷 수, 마지막으로 성공한 파일 및 수, 가장 최근의 실패가 표시됩니다. 지금 백업은 안전한 주문형 실행을 대기열에 추가합니다. 최신 다운로드는 최신 지속형 스냅샷을 검색합니다.
- 재생 목록 페이지에서 서비스 카드 내보내기를 사용하여 해당 서비스의 모든 재생 목록을 하나의 버전 JSON 또는 XML 파일로 다운로드합니다.
- 해당 재생 목록만 내보내려면 재생 목록을 엽니다. Soundiiz 옵션은 [Soundiiz의 문서화됨 JSON 가져오기 모양](https://soundiiz.com/data/fileExamples/playlistExport.json) 뒤에 있으므로 다운로드한 트랙 목록은 Soundiiz의 재생 목록 가져오기 → 파일에서 흐름을 통해 업로드할 수 있습니다.
- SongMirror JSON/XML는 재생목록 순서와 이름, 제공자 트랙/발생 ID, 사용 가능한 ISRC, 아티스트, 앨범, 앨범 트랙 위치, 기간, 추가된 날짜, 아트워크 링크, 사용할 수 없는 항목 마커를 보존합니다. ID가 없는 카탈로그 고스트는 사라지지 않고 백업에 남아 있습니다. 파일에는 쿠키, 토큰, 요청 헤더, 미리 보기 또는 스트리밍 파일 URL이 포함되어 있지 않습니다.

수동 내보내기는 브라우저를 통해 UI를 실행하는 장치로 다운로드됩니다. 예약된 내보내기는 기존 애플리케이션 데이터 볼륨을 사용하므로 두 번째 호스트 경로나 컨테이너 마운트가 필요하지 않습니다. 백업은 공급자 클라이언트에 동시에 액세스하는 대신 동기화 및 전송 뒤의 대기열을 읽습니다. `schema_version` 필드를 사용하면 향후 릴리스에서 이전 스냅샷을 모호하게 만들지 않고 무손실 형식을 발전시킬 수 있습니다.

<a id="built-in-folder-picker"></a>

### 내장 폴더 선택기

폴더 필드를 클릭하거나 찾아보기...를 클릭하여 내장된 선택기를 엽니다. 위치, 클릭 가능한 이동 경로, 뒤로, 앞으로 및 한 폴더 위로 이동을 사용하세요. 폴더를 클릭하여 선택하세요. 두 번 클릭하거나 Enter 키를 누르거나 화살표를 사용하여 엽니다. 검색은 현재 폴더를 필터링합니다. 폴더 경로를 입력하면 전체 주소가 허용됩니다. 폴더를 선택하면 초안이 업데이트됩니다. 적용하려면 설정이나 일정을 저장하세요. 취소하면 초안이 변경되지 않습니다. 데스크탑 도우미나 추가 프로세스가 필요하지 않습니다.

새 폴더는 현재 열려 있는 위치에 명명된 하위 폴더를 생성한 다음 엽니다. 기존 항목은 덮어쓰지 않습니다. 이름 입력을 취소하면 아무 것도 생성되지 않습니다. 생성 후 선택기를 취소하면 새 폴더가 디스크에 남게 됩니다. 저장된 백업 또는 다운로드 위치는 선택하고 저장한 후에만 변경됩니다. Docker에서 선택기는 공유되는 경로를 설명하고 사용 가능한 경우 컨테이너 경로와 구성된 컴퓨터 경로를 모두 표시합니다.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 로컬 다운로드 미러(Jellyfin)

[spotDL](https://github.com/spotDL/spotify-downloader)를 통해 동기화된 각 재생목록의 오프라인 오디오 사본을 재생목록당 하나의 폴더로 보관하세요. 동기화는 진정한 미러링입니다. 새 트랙이 다운로드되고, 제거된 트랙은 로컬에서 삭제됩니다. 레이아웃은 Jellyfin 준비가 되어 있습니다. 다운로드 디렉토리에 Jellyfin 음악 라이브러리를 지정하면 트랙과 재생 목록이 모두 나타나 패스할 때마다 업데이트됩니다.

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

`DOWNLOAD_DIR`를 설정하고 spotDL + ffmpeg를 설치하여 활성화하세요.

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- 증분 — 첫 번째 전체 다운로드 후에는 새로 추가된 트랙만 가져옵니다. 제거된 트랙(및 비어 있는 앨범 폴더)은 정리됩니다. 중단된 실행은 다음 패스에서 계속됩니다.
- 최신순 `.m3u8` — 날짜가 추가된 순서로 작성되고 최신 항목이 맨 위에 옵니다(뒤집으려면 `LOCAL_MIRROR_ORDER=oldest` 설정). `uv run main.py --refresh-local`를 사용하여 기존 파일에서 표지/태그/시간을 다시 작성하세요.
- Jellyfin의 재생 목록 커버 — Jellyfin는 m3u 옆의 커버 파일을 무시하므로 `JELLYFIN_URL` + `JELLYFIN_API_KEY`를 설정하고 각 패스는 Jellyfin API를 통해 실제 재생 목록 커버를 업로드합니다.
- 오디오 품질 — 소스는 YouTube이므로 YT Music Premium 쿠키가 없으면 최대치는 ~128~160kbps입니다. `LOCAL_MIRROR_FORMAT=opus`는 mp3 재인코딩 없이 YouTube의 기본 스트림을 유지합니다. Premium 쿠키(`LOCAL_MIRROR_COOKIE_FILE`)는 256kbps AAC를 잠금 해제합니다. `flac`를 선택하면 출력 컨테이너가 변경되지만 손실이 있는 소스를 무손실 오디오로 바꿀 수는 없습니다.

Monochrome의 현재 FLAC 경로는 안정적인 공급자 승인 파일 내보내기 API 대신 브라우저 제어 일회용 재생 리소스를 사용하므로 SongMirror는 이를 자동화하지 않습니다. 귀하가 소유하고 있거나 복사 권한이 있는 컨텐츠에 대해서만 로컬 미러를 사용하십시오.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 각 서비스 연결

웹 앱의 계정 페이지는 각 서비스를 안내하고 붙여넣을 정확한 값을 보여줍니다. 어떠한 것도 제3자를 통해 프록시되지 않습니다.

<a id="credential-renewal"></a>

### 자격증명 갱신

SongMirror 별도의 토큰 새로 고침 타이머를 사용하지 않고 적시에 자격 증명을 새로 고칩니다. 모든 수동 또는 예약된 동기화 단계는 사용하는 커넥터의 유효성을 검사하고 첫 번째 요청 전(또는 인증 거부 후 한 번) 지원되는 액세스 토큰을 갱신합니다. 패스 사이에 단기 액세스 토큰이 만료되는 것은 일반적인 현상입니다. 지속 가능한 새로 고침 토큰이나 갱신 쿠키가 중요합니다. 계정 페이지는 포커스를 로드하거나 다시 얻을 때 상태의 유효성을 검사하지만 이는 백그라운드 세션 유지 관리가 아닙니다. 활성화된 동기화 일정은 다음과 같습니다.

| 서비스 | 갱신 행동 |
| --- | --- |
| Spotify | 기본 연결은 요청 시 저장된 `sp_dc` 쿠키에서 웹 플레이어 액세스 토큰을 생성하고 `401` 후에 새 토큰으로 재시도합니다. 기본 로그인 세션은 여전히 ​​취소될 수 있습니다. 기존 개발자 앱 OAuth은 기존 설치에 대해 계속 지원됩니다. |
| TIDAL | 가져온 웹 플레이어 액세스 토큰은 로그인 응답의 새로 고침 토큰을 사용하여 `auth.tidal.com`를 통해 자동으로 갱신됩니다. SongMirror는 응답이 생략될 때 기존 새로 고침 토큰을 유지하고 TIDAL가 토큰을 반환할 때 회전된 토큰을 유지합니다. 로그아웃하거나 취소하려면 여전히 새로운 캡처가 필요합니다. |
| Qobuz | 붙여넣은 `X-User-Auth-Token`는 Qobuz가 거부할 때까지 사용되며, 이후에는 다시 캡처해야 합니다. |
| Deezer | 수명이 짧은 파이프 JWT는 사용 전과 `401/403` 후에 저장된 `refresh-token`에서 자동으로 갱신됩니다. 순환된 갱신 상태가 지속됩니다. |
| Amazon Music | 웹 액세스 토큰은 캡처된 브라우저 사용자 에이전트, 리퍼러 및 허용 목록에 있는 쿠키를 사용하여 `/pandaToken`를 통해 갱신됩니다. 현재 `POST config.json?skipToken=false` 흐름은 필요한 경우 장치 컨텍스트를 부트스트랩하고 회전된 쿠키는 유지됩니다. 로그아웃, 보안 변경 또는 서버 측 취소에는 여전히 새로운 캡처가 필요합니다. |
| Apple Music | 붙여넣은 Bearer 및 Media-User-Token는 SongMirror로 갱신할 수 없으며 거부 후 다시 캡처해야 합니다. |
| YouTube Music | Data API OAuth 만료 후 60초 이내에 자동으로 새로고침됩니다. 브라우저 모드는 동기화 대상이 구축될 때마다 Google의 쿠키 순환을 시도합니다. 이미 만료된 브라우저 세션을 다시 내보내야 합니다. |
| Jellyfin | API 키에는 액세스 토큰 새로 고침 주기가 없습니다. 취소되거나 삭제된 경우에만 교체하십시오. |

<a id="spotify"></a>

### Spotify

1. <https://open.spotify.com>에 로그인하세요.
2. 브라우저 DevTools(`F12`) → 애플리케이션(Chrome/Edge) 또는 저장소(Firefox) → 쿠키 → `https://open.spotify.com`를 엽니다.
3. `sp_dc` 쿠키 값을 복사하여 계정 → Spotify에 붙여넣습니다.

단일 로그인 웹 세션은 라이브러리 탐색, 재생 목록 읽기 및 쓰기, 카탈로그 검색을 처리합니다. Spotify 개발자 앱, API 키 또는 Premium 계정이 필요하지 않습니다. `sp_dc`을 비밀번호처럼 취급합니다. SongMirror는 이를 개인 데이터 디렉토리에 저장하지만 통합은 Spotify의 내부 웹 플레이어 작업을 사용하며 Spotify이 이를 변경할 경우 유지 관리가 필요할 수 있습니다. 기존 개발자 앱 OAuth 자격 증명은 호환 가능한 대체 버전으로 유지됩니다.

<a id="tidal"></a>

### TIDAL

1. [TIDAL의 웹 플레이어](https://listen.tidal.com)를 열고, DevTools을 열고 → 네트워크를 열고 로그 보존을 활성화하세요.
2. 로그아웃했다가 다시 로그인한 다음 네트워크 목록을 `oauth2/token`로 필터링하세요.
3. 성공적인 `auth.tidal.com/v1/oauth2/token` 요청을 선택하세요. 페이로드(Chrome/Edge) 또는 요청(Firefox)에서 `client_id` 양식 값을 SongMirror의 웹 플레이어 클라이언트 ID 필드에 복사합니다.
4. 요청의 응답 탭을 열고 전체 JSON를 웹 플레이어 토큰 응답에 복사합니다. `access_token` 및 `refresh_token`을 모두 포함해야 합니다.
5. 연결하세요. SongMirror는 즉시 새로 고침 권한을 행사하고 해당 클라이언트 ID가 갱신될 수 없는 경우 성공 보고를 거부합니다.

OAuth 클라이언트 ID는 요청 메타데이터이며 TIDAL 액세스 토큰에 포함된 숫자 `cid` 클레임이 아닙니다. SongMirror 액세스 토큰, 새로 고침 토큰, 클라이언트 ID, 범위, 만료 및 카탈로그 국가만 추출합니다. 관련 없는 응답 데이터는 삭제됩니다. 만료 직전과 `https://auth.tidal.com/v1/oauth2/token`을 통해 인증 거부 후 한 번 갱신되어 새로 고침 토큰 순환이 유지됩니다. 이전 OpenAPI 요청 헤더 붙여넣기는 여전히 호환되지만 새로 고침 토큰이 포함되어 있지 않기 때문에 만료 후에도 다시 붙여넣어야 합니다. 카탈로그 메타데이터와 로그인한 사용자의 재생 목록만 사용되며 재생 자산은 이 통합 외부에 유지됩니다.

<a id="qobuz"></a>

### Qobuz

<https://play.qobuz.com>에 로그인하고 DevTools → 네트워크를 열고 `api.json/0.2`로 필터링하세요. 인증된 `album/story` 요청을 포함하여 `X-App-Id` 및 `X-User-Auth-Token`가 포함된 요청을 선택한 다음 해당 요청 헤더를 복사하거나 cURL로 복사하여 마법사에 붙여넣습니다. SongMirror 이 두 값만 유지하고 웹 플레이어와 동일한 헤더 기반 흐름을 사용하여 전송하며 쿠키 및 관련 없는 브라우저 메타데이터를 삭제합니다. 비즈니스 API 승인이나 사용자 ID가 필요하지 않습니다. 기존 파트너 자격 증명은 호환 가능한 환경 대체 상태로 유지됩니다.

어댑터는 카탈로그 검색 및 재생 목록 엔드포인트만 사용하며 스트림이나 파일 URL은 요청하지 않습니다.

<a id="deezer"></a>

### Deezer

<https://www.deezer.com>에서 로그인하고 DevTools → 네트워크를 열고 페이지를 새로고침하세요. `auth.deezer.com/login/renew`을 필터링하고 해당 요청의 헤더를 복사(또는 cURL로 복사)한 후 갱신 필드에 붙여넣습니다. Firefox 대신 요청 쿠키를 세미콜론으로 구분된 블록으로 복사할 수 있습니다. 그 모양도 받아들여진다. SongMirror는 전용 `refresh-token` 쿠키만 유지하고 이를 사용하여 Deezer의 단기 파이프 JWT를 자동으로 갱신합니다. 현재 `pipe.deezer.com/api` 요청을 즉시 부트스트랩으로 붙여넣을 수도 있지만 갱신이 구성된 경우에는 필요하지 않습니다. 재생 목록 추가 및 제거는 모두 재생 가능한 Pipe 세션을 사용합니다. 아니요 `arl` 쿠키가 필요합니다. 기존 개발자 OAuth 토큰은 호환 가능한 환경 폴백으로 유지됩니다.

<a id="amazon-music"></a>

### Amazon Music

기본 커넥터에는 개발자 승인이 필요하지 않습니다. Amazon Music 웹 플레이어와 동일한 인증된 GraphQL 및 토큰 갱신 경로를 사용합니다.

1. <https://music.amazon.com>에 로그인하고 DevTools → 네트워크를 엽니다.
2. 페이지를 다시 로드하고 `config.json`로 필터링한 후 로그인된 요청을 선택하세요. (`pandaToken`가 나타날 때도 작동하지만 필수는 아닙니다.)
3. 요청 헤더 복사 또는 cURL로 복사를 선택한 다음 갱신 필드에 붙여넣습니다. `User-Agent`, `Referer`, `Cookie` 헤더 전체를 유지하여 SongMirror이 동일한 브라우저 컨텍스트를 재생할 수 있도록 하세요.
4. 선택적으로 로그인된 `config.json` 응답을 부트스트랩 필드에 복사합니다. SongMirror는 일반적으로 갱신 세션을 사용하여 해당 장치 컨텍스트를 가져올 수 있습니다.

SongMirror는 동일한 `AmznMusic` 인증 값을 로컬에서 파생하고 만료 전 또는 인증 거부 후 한 번 `music.amazon.com/pandaToken`을 통해 새로 고칩니다. 연결하는 동안 장치 컨텍스트가 필요할 때 현재 브라우저 스타일 구성 요청을 사용하고 액세스 토큰을 생성하기 위해 `/pandaToken`를 요구하며 Amazon이 음악 갱신 쿠키를 취소하면 연결을 거부합니다. 브라우저 사용자 에이전트, 언어, 음악 참조자, Amazon 인증/세션 쿠키의 명명된 허용 목록 및 제한된 음악 클라이언트 장치 컨텍스트만 저장합니다. 분석, 실험, AWS 콘솔, CSRF 및 기타 관련 없는 브라우저 데이터는 삭제됩니다. 보관된 쿠키는 여전히 민감하므로 LAN에서 SongMirror를 비공개로 유지하세요. 로그아웃, 비밀번호/보안 변경 또는 Amazon 측 취소에는 여전히 한 번의 새로운 캡처가 필요할 수 있습니다.

이는 지원되지 않는 자사 웹 클라이언트 인터페이스이며 Amazon에서는 사전 통지 없이 이를 변경할 수 있습니다. 문서화된 [Amazon Music 웹 API](https://developer.amazon.com/docs/music/API_web_overview.html)은 아직 비공개 베타 버전입니다. 승인된 파트너 자격 증명은 환경 변수를 통해 구성할 때 선택적 대체 상태로 유지됩니다.

<a id="apple-music"></a>

### Apple Music

Apple 개발자 계정이 필요하지 않습니다. `music.apple.com`의 헤더 두 개이면 충분합니다. <https://music.apple.com> 열기, 로그인, DevTools 열기 → 네트워크, 노래 재생, `amp-api.music.apple.com` 필터링 및 모든 요청 헤더 복사:

- `authorization: Bearer eyJ...` → Bearer 토큰(`eyJ...` 부분, `Bearer ` 제외)
- `media-user-token: ...` → 사용자 토큰(전체 값)

연결 마법사를 사용하면 원시 헤더를 붙여넣고 값을 구문 분석할 수 있습니다. 지난 달 토큰; 만료되면 계정 페이지에 다시 붙여넣으세요.

활성화된 Apple Music 구독이 없는 Apple ID는 여전히 카탈로그 전용 모드로 연결할 수 있습니다. 해당 모드에서는 공개 Apple Music 재생 목록 링크를 전송에 붙여넣어 다른 연결된 서비스에 복사하세요. Apple 라이브러리 탐색, 예약된 동기화 및 Apple Music를 전송 대상으로 사용하려면 여전히 유료 CloudLibrary 권한이 필요합니다. SongMirror는 유효한 카탈로그 자격 증명을 만료된 것으로 처리하는 대신 해당 작업을 사용할 수 없는 것으로 표시합니다.

<a id="youtube-music"></a>

### YouTube Music

OAuth 갱신 토큰이 내구성이 있고 다시 시작해도 유지되는 공식 [YouTube Data API v3](https://developers.google.com/youtube/v3)과 대화합니다.

1. [Google 클라우드 콘솔](https://console.cloud.google.com)에서 프로젝트를 생성하고, YouTube Data API v3를 활성화하고, TV 및 제한된 입력 장치 유형의 OAuth 클라이언트를 생성합니다.
2. OAuth 동의 화면에서 게시 상태 → 프로덕션 중으로 설정합니다('테스트' 상태로 두면 7일 후에 토큰이 만료됩니다).
3. 앱에서 클라이언트 ID + 비밀번호를 붙여넣고 화면에 표시되는 장치 코드를 완성하세요.

> 할당량: Data API는 하루 10,000개 단위를 허용합니다(검색 비용은 100, 추가/제거 비용은 50). 정상 상태 유지 비용이 저렴합니다. 큰 규모의 최초 백로그가 한도에 도달하고 다음날 재개될 수 있습니다.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ 그래픽 인터페이스 CLI 없이

`.env` + cron / Task Scheduler을 선호하시나요? 동일한 엔진이 그래픽 인터페이스 없이 실행됩니다.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

유용한 플래그:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

주요 환경 변수(`.env.example` 참조): 사용하는 공급자에 대한 자격 증명, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES`, `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ 안전 보호 장치

제거는 파괴적이므로 보호됩니다.

- 시뮬레이션이 기본값입니다. `--execute`(또는 UI의 실제 동기화 작업) 없이는 아무 것도 변경되지 않습니다.
- 소스가 대상이 비어 있지 않은 것으로 표시되는 재생 목록에 대해 0개의 트랙을 반환하는 경우 해당 단계에서 제거를 건너뜁니다(일시적인 API 실패로 인해 재생 목록이 비워질 수 없음).
- **삭제는 기본적으로 꺼져 있습니다** — `MAX_REMOVALS=0`은 모든 삭제를 보류하며, 로그에 기록만 하고 실행하지 않습니다. 따라서 한 플랫폼에서 라이선스 문제로 곡이 내려가더라도 다른 플랫폼에서 연쇄적으로 삭제되지 않습니다. 각 동기화에서 **곡 삭제 동기화**를 켜거나 `MAX_REMOVALS`를 설정하세요. 활성화한 뒤에도 한 번의 실행에서 삭제 예정 건수가 상한을 넘으면 모든 삭제를 건너뛰고 로그에 기록합니다.
- `MAX_ADDS` 연대순 복구를 포함하여 동기화 패스에서 모든 타임스탬프 생성 쓰기를 제한합니다. 오래된 복구 일치 항목에 한도가 허용하는 것보다 더 큰 접미사 재생이 필요한 경우 SongMirror 최신 항목으로 보이도록 하거나 대규모 공급자 버스트를 유발하는 대신 다음 단계로 연기합니다. 일회성 전송에는 다음 패스가 없으므로 결코 지연되지 않습니다. 해당 전송에 대해 "최근 추가된 순서 유지"를 전환하지 않는 한 요청된 모든 트랙을 복사하여 소스 순서에 추가합니다. 이 경우 수리 비용이 무엇이든 지출됩니다.
- 연대순 복구는 원본을 폐기하기 전에 복사본을 준비합니다. 노래의 모든 사본을 삭제하는 서비스에서는 해당 키퍼 수가 정확해야 하므로 준비된 사본이 표시될 때까지 Apple Music를 다시 읽고 여전히 자체 쓰기에 뒤처지는 읽기에 대해 폐기를 거부합니다. Deezer는 수리를 완전히 건너뛰고 항상 추가합니다. 위치 삽입도 없으므로 표현할 수 없는 명령을 재생하는 것은 대상에 위험을 감수할 가치가 없습니다. 전송 양식에는 주문 스위치가 회색으로 표시되고 그 이유가 설명되어 있습니다.
- 순 손실 보호 — 해당 서비스와 일치하는 항목이 없는 소스 트랙과 유사한 대상 측 트랙은 삭제되지 않고 유지됩니다.
- 공급자 인증에 실패하면 해당 공급자의 패스가 즉시 중단됩니다. 만료된 토큰은 부분적으로 삭제되지 않습니다.
- 병합 작업은 대상에서 삭제하기 전에 읽기된 모든 구성 소스를 완료해야 합니다. 추가 전용 동작으로 전달되는 부분적/실패한 소스 스냅샷 강제.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ 캐싱 및 노래 보관

해결 가능한 모든 것이 캐시되므로 정상 상태 통과가 거의 즉각적입니다. 서비스별 해결 캐시(ISRC + 검색, 누락 포함), `snapshot_id` 키 트랙 목록 캐시, SQLite의 정확한 식별자 링크, 쌍별 스냅샷 건너뛰기(`unchanged since last clean sync`).

모든 패스는 또한 보는 모든 트랙의 메타데이터를 `song_cache.db`(계속 커지기만 하는 SQLite 파일)에 보관합니다. 제거된 트랙은 이름, 아티스트, 앨범, 기간, ISRC, 원시 스냅샷 JSON 및 처음/마지막으로 본 타임스탬프와 함께 보관됩니다.

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### 매핑 해결

각 서비스는 자체 확인 캐시를 유지하여 정규화된 `title|artist` 키를 일치하는 카탈로그 ID에 매핑합니다.
그 서비스. 일치 항목은 영원히 재사용되며 "일치 없음" 결과도 마찬가지입니다. 이로 인해 트랙이 실패하게 됩니다.
한 번 일치하려면 이후 패스마다 일치하지 않는 상태로 유지됩니다.

웹 UI의 매핑 페이지는 서비스별로 해당 캐시를 직접 노출합니다.

- 제목, 아티스트 또는 확인된 ID로 전체 캐시를 검색하세요.
- 직접 설정한 항목(전송 충돌 편집기에서 선택한 일치 항목) 또는 일치 항목이 없는 항목으로 필터링
- 올바른 트랙의 링크를 붙여넣어 잘못된 ID를 수정하거나 다음 패스에서 다시 찾을 수 있도록 매핑을 삭제하세요.
- 한 번의 작업으로 서비스에 대한 모든 "일치 없음" 항목을 삭제하여 실패한 조회 배치에 대해 다시 시도합니다.

지워진 누락이 나중에 해결되면 이를 추가하기만 하면 이전 노래가 최신 노래로 표시됩니다. 재생목록의 경우
SongMirror 대신 해당 노래와 이미 존재하는 최신 접미사를 가장 오래된 것부터 최신 순으로 재생한 다음 제거합니다.
오래된 사본. 공급자는 클라이언트가 원래 타임스탬프를 복원하는 것을 허용하지 않지만 이로 인해 상대적인 타임스탬프가 유지됩니다.
최근 추가된 주문입니다. 기본 좋아요/즐겨찾기 컬렉션은 회원 전용으로 유지되며 재생되지 않습니다.

동기화가 실행되는 동안에는 명확한 메시지와 함께 편집이 거부됩니다. 왜냐하면 패스는 해당 작업에 대한 캐시를 메모리에 보유하기 때문입니다.
전체 기간 동안 완료되며 덮어쓰게 됩니다.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 프로젝트 레이아웃

CLI 항목: `uv run main.py`(얇은 심) 또는 `python -m songmirror`. 웹 항목: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

다른 서비스 추가: 하위 클래스 `MirrorTarget`, ~8개의 메소드 구현, `engine/targets`' `_REGISTRY`에 해당 빌더를 추가하고 `_CLASSES`에 해당 클래스를 추가하고, `services/accounts` 아래에 일치하는 `Connector`를 추가합니다. 모든 조정(차이, 순서 지정, 안전 보호, 로깅, 스냅샷 건너뛰기)이 상속됩니다.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 문제 해결

- `Missing required environment variable` — `.env`(CLI)을 입력하거나 UI에서 서비스를 연결합니다.
- TIDAL 보고서 `Expired` — `listen.tidal.com`에서 로그아웃했다가 다시 로그인한 다음 `oauth2/token` 요청 페이로드의 `client_id`와 전체 응답 JSON을 계정에 붙여넣습니다. 복사된 OpenAPI 요청에는 단기 Bearer 요청만 포함되며 갱신할 수 없습니다.
- TIDAL 보고서 HTTP 429 — 이는 만료된 로그인이 아니라 임시 속도 제한입니다. SongMirror는 API를 반복적으로 조사하는 대신 공급자의 재시도 지연을 존중하고 계정 상태 확인을 캐시합니다.
- Qobuz 또는 Apple 보고서 `Expired` / `401` / `403` — 붙여넣은 세션에는 재생 가능한 비밀이 없습니다. 계정에서 새로 로그인한 요청이나 토큰을 캡처하세요.
- TIDAL는 토큰에 좋아요 트랙 액세스가 부족하다고 말합니다. `r_usr` 및 `w_usr`을 포함하는 새로 로그인한 웹 플레이어 토큰 응답을 캡처합니다.
- Deezer 갱신 실패 — 새로운 `auth.deezer.com/login/renew` 요청(또는 해당 `refresh-token` 쿠키)을 캡처합니다. 현재 파이프 Bearer만으로는 임시 부트스트랩일 뿐입니다.
- Amazon Music 갱신 실패 — 전체 `User-Agent`, `Referer` 및 `Cookie` 헤더가 포함된 새로 로그인한 `POST /config.json?skipToken=false` 요청을 캡처합니다. 응답 JSON는 선택 사항입니다.
- YouTube Music 브라우저 모드 만료 — 새로운 브라우저 요청 헤더를 내보냅니다. 가장 안정적인 무인 설정을 위해서는 제작 중인 동의 화면에서 Data API OAuth를 사용하세요.
- Spotify 보고서가 만료되었습니다. `open.spotify.com`에서 다시 로그인하고 계정에 새로운 `sp_dc` 쿠키를 붙여넣으세요.
- 재생 목록이 동기화되지 않습니다. 동기화의 재생 목록 범위에 있고 소스에 존재하는지 확인하세요(대상은 실제 패스에서 자동 생성됨).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 라이센스

저작권 © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
이 프로젝트는 [MIT](../../LICENSE) 라이선스가 부여되었습니다.

<!-- LINK GROUP -->

[back-to-top]: https://img.shields.io/badge/-BACK_TO_TOP-151515?style=flat-square
[ci-shield]: https://img.shields.io/github/actions/workflow/status/ahnafnafee/songmirror/ci.yml?branch=main&label=CI&labelColor=black&logo=githubactions&logoColor=white&style=flat-square
[ci-link]: https://github.com/ahnafnafee/songmirror/actions/workflows/ci.yml
[license-shield]: https://img.shields.io/github/license/ahnafnafee/songmirror?color=F2601A&labelColor=black&style=flat-square
[license-link]: https://github.com/ahnafnafee/songmirror/blob/main/LICENSE
[python-shield]: https://img.shields.io/badge/python-3.13%2B-F2601A?labelColor=black&logo=python&logoColor=white&style=flat-square
[python-link]: https://www.python.org/
[docker-shield]: https://img.shields.io/badge/docker-ready-F2601A?labelColor=black&logo=docker&logoColor=white&style=flat-square
[docker-link]: https://github.com/ahnafnafee/songmirror/pkgs/container/songmirror
[stars-shield]: https://img.shields.io/github/stars/ahnafnafee/songmirror?color=F2601A&labelColor=black&logo=github&logoColor=white&style=flat-square
[stars-link]: https://github.com/ahnafnafee/songmirror/stargazers
[forks-shield]: https://img.shields.io/github/forks/ahnafnafee/songmirror?color=F2601A&labelColor=black&logo=github&logoColor=white&style=flat-square
[forks-link]: https://github.com/ahnafnafee/songmirror/network/members
[issues-shield]: https://img.shields.io/github/issues/ahnafnafee/songmirror?color=F2601A&labelColor=black&logo=github&logoColor=white&style=flat-square
[issues-link]: https://github.com/ahnafnafee/songmirror/issues
[last-commit-shield]: https://img.shields.io/github/last-commit/ahnafnafee/songmirror?color=F2601A&labelColor=black&logo=github&logoColor=white&style=flat-square
[last-commit-link]: https://github.com/ahnafnafee/songmirror/commits/main
[github-issues-link]: https://github.com/ahnafnafee/songmirror/issues
[share-x-shield]: https://img.shields.io/badge/-share%20on%20x-black?labelColor=black&logo=x&logoColor=white&style=flat-square
[share-x-link]: https://x.com/intent/tweet?text=SongMirror%20%E2%80%94%20self-hosted%20playlist%20sync%20across%20seven%20music%20services&url=https%3A%2F%2Fgithub.com%2Fahnafnafee%2Fsongmirror
[share-reddit-shield]: https://img.shields.io/badge/-share%20on%20reddit-black?labelColor=black&logo=reddit&logoColor=white&style=flat-square
[share-reddit-link]: https://www.reddit.com/submit?title=SongMirror%20%E2%80%94%20self-hosted%20playlist%20sync%20across%20seven%20music%20services&url=https%3A%2F%2Fgithub.com%2Fahnafnafee%2Fsongmirror
[share-linkedin-shield]: https://img.shields.io/badge/-share%20on%20linkedin-black?labelColor=black&logo=linkedin&logoColor=white&style=flat-square
[share-linkedin-link]: https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fgithub.com%2Fahnafnafee%2Fsongmirror
