<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

自托管、始终在线的播放列表同步，适用于 Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music 和 YouTube Music — 以及本地音频镜像对于 Jellyfin.<br/>
您拥有并运行的免费、开源、自托管的 Soundiiz、TuneMyMusic 和 FreeYourMusic 替代方案。

**单向、多源合并、权威组或完全双向（N 向）同步 · 一次性播放列表传输 · 通过 ISRC 精确匹配 · 全部来自您的浏览器**

[快速入门](#quick-start) · [特点](#features) · [截图](#screenshots) · [一直在奔跑：Docker](#always-running-docker) · [它是如何运作的](#how-it-works) · [报告问题][github-issues-link] · [提出功能建议][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**分享这个项目**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>设置一次 - 您策划的每个播放列表都会按照添加日期的顺序在每个服务中保持镜像。</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror 演示 — 徽标显示、仪表板、单向和双向同步设置、实时播放列表传输以及 ISRC 跨七个音乐服务的准确匹配" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">观看1080p版本</a></sup>

</div>

> [!NOTE]
> Web应用程序+无图形界面CLI，一个引擎。单击浏览器 UI 以连接服务、构建同步并传输播放列表 - 或运行它 `.env` + cron 样式。两者驱动相同的同步核心。

<details>
<summary><kbd>目录</kbd></summary>

#### 总有机碳

- [✨ 特点](#features)
- [📸 截图](#screenshots)
- [🚀 快速入门](#quick-start)
  - [应用语言](#app-language)
- [🐳 一直在奔跑：Docker](#always-running-docker)
- [⚙️ 它是如何运作的](#how-it-works)
  - [配套](#matching)
  - [多源合并同步](#multi-source-merge-sync)
  - [权威团体](#authoritative-groups)
  - [双向（N 路）同步](#bidirectional-n-way-sync)
- [📦 播放列表元数据备份](#playlist-metadata-backups)
- [💿本地下载镜像(Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 连接各个服务](#connecting-each-service)
  - [证书更新](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️没有图形界面CLI](#headless-cli)
- [🛡️安全保障](#safety-rails)
- [🗃️ 缓存和歌曲存档](#caching-song-archive)
  - [解析映射](#resolve-mappings)
- [🧱 项目布局](#project-layout)
- [🩺 故障排除](#troubleshooting)
- [📄 许可证](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ 特点

SongMirror 使您的播放列表在任何地方都保持相同，无需手动重新添加、逐一复制或保存您的库的付费云服务。它是跨平台、自托管且开源的。

- 🔁 真正的镜像，而不是仅追加——添加和删除。选择一个事实来源（默认为Spotify），其他信息遵循它。
- ⇆ **权威组** — 信任两个或多个服务（例如 Spotify + Apple Music），而每个其他选定的服务仍然是仅目标镜像。
- ⇄ **双向 N 路同步** — 任何连接的服务上的添加或删除都会传播到所有其他服务，无回声，位于删除防护后面。
- ⇉ **多源合并同步** — 将库播放列表和公共播放列表 URL 的重复数据删除联合安排到一个目的地，而不保存或遵循公共列表。
- ♥ **喜欢和最喜欢的曲目** - 将所有七个音乐提供商的每个服务的内置喜欢收藏同步到目的地自己的收藏夹或新命名的播放列表中。
- 🎯 **通过 ISRC 进行准确匹配** — 准确的录音身份（如果可用），以及大约与 Unicode 兼容的标题/艺术家/持续时间后备（特色艺术家制作人员名单中的差异、“- 2015 Remaster”后缀、非拉丁脚本、仅视频上传 — 全部处理）。
- 🎛️ **多个命名同步** — 根据需要设置多个独立同步，每个同步都有自己的服务、播放列表、时间表和安全上限。
- ↪️ **一次性传输** — 使用实时进度条将任何播放列表从一项服务复制到另一项服务；暂停、恢复或停止复制过程，并手动解决不匹配的轨道。
- 🕒 **追加轨道或保留轨道顺序** - 默认情况下，快速且可附加地复制目的地末尾的陆地。打开“保留最近添加的顺序”以在最旧的新曲目之后重写曲目，以便添加日期的顺序与源匹配。
- 🔗 **从链接传输** — 从任何连接的服务粘贴公共播放列表 URL 并直接复制。无需先保存或遵循它。
- 🌐 **关注的播放列表** — 同步和传输您关注但不拥有的播放列表，而不仅仅是您创建的播放列表。
- 📦 **计划元数据备份** — 根据自己的计划在持久性应用程序数据下存档帐户的整个播放列表库，具有 JSON/XML、保留限制和可见的成功/失败历史记录。一次性下载和导入就绪 Soundiiz JSON 也仍然可用。
- 💿 **本地下载镜像** — 保留离线音频，每个播放列表一个文件夹，采用 Jellyfin 的 `AlbumArtist/Album` 布局，带有封面和自动更新的 `.m3u8`。
- 🛡️ **安全保障** — 默认模拟、每次添加/删除上限、净损失保护、空快照防护、令牌过期时不写入而中止。
- 🗃️ **不断增长的歌曲档案** - 每首看过的曲目都记录在本地 SQLite 数据库中（姓名、艺术家、专辑、ISRC、原始元数据、首次/最后一次看到）。
- 🧭 **可编辑的比赛历史记录** - 从“映射”页面浏览、更正和删除每个服务的每个缓存的赛道比赛，包括“不匹配”结果，否则这些结果将永远保持不匹配。
- 🐳 **可以在任何地方运行** — 一个用于浏览器应用程序的 `docker compose up -d`，或者普通的 CLI + cron / Task Scheduler。

> [!IMPORTANT]
> 自托管且设计私密。您的收听数据和凭据永远不会离开您的机器。 Web UI 没有身份验证 - 将其绑定到您的 LAN 并且不要将其端口转发到互联网。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 截图

<div align="center">

**每个图书馆都有一个仪表板 — 同步状态、作业、实时活动和服务运行状况**

<img src="../../.github/assets/dashboard.png" alt="SongMirror 仪表板显示Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music、的同步状态、已配置作业、实时活动和运行状况， YouTube Music和Jellyfin" width="82%">

**在简短的向导中设置任意数量的同步 - 单向、多源合并、权威组或双向**

<img src="../../.github/assets/sync-wizard.png" alt="SongMirror 设置向导选择跨 Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music 和 YouTube Music 进行双向同步的服务" width="82%">

**连接浏览器中的每项服务 — 一键式 OAuth、引导式令牌粘贴或 API 键**

<img src="../../.github/assets/accounts.png" alt="用于连接 Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music、YouTube Music 和 Jellyfin 的帐户页面" width="82%">

**跨服务浏览和配对播放列表**

<img src="../../.github/assets/playlists.png" alt="浏览互联服务中的播放列表以及封面艺术和曲目数量" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 快速入门

运行它的最快方法是 Docker — Compose 拉取已发布的图像、提供 Web UI 服务并按计划运行同步。

对于具有自动重启功能的持久安装：

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

或者直接尝试公共 GHCR 映像而不克隆存储库：

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

然后打开`http://localhost:8888`并在浏览器中连接您的服务。 Compose 设置无需 `.env` 即可启动；一切都在 UI 中配置并保存在 `./data` 下。

直接 `docker run` 选项是一次性的：`docker stop songmirror` 删除容器及其配置。使用 Compose 进行具有持久凭证、缓存和下载的持久安装，或者查看 [容器镜像指南](../docker-image.md) 进行标签和摘要固定。

更喜欢在没有 Docker 的情况下运行它？

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> 需要[`uv`](https://docs.astral.sh/uv/)（Python 3.13+）。对于本地下载镜像，PATH 上还有`uv tool install spotdl` 和`ffmpeg`。

<a id="app-language"></a>

### 应用语言

SongMirror支持英语、阿拉伯语、土耳其语、西班牙语、简体中文、法语、葡萄牙语、德语、日语、印地语、孟加拉语、印度尼西亚语、韩语、意大利语和越南语。 首次启动时，应用会依次检查浏览器的语言偏好（包括地区变体），使用其中第一个受支持的语言；如果没有匹配项，则使用英语。可在 **设置 → 常规 → 语言** 中更改语言。选择会保存在此浏览器中，重新加载页面后仍然有效。选择 **自动（浏览器）** 可重新跟随浏览器的语言偏好。阿拉伯语界面采用从右到左的布局。播放列表名称、艺术家姓名、服务名称、凭据和诊断日志保留原始值。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 一直在奔跑：Docker

Docker 容器是建议的部署：它提供 Web UI，按计划运行同步，并与主机一起重新启动。 Compose拉取`ghcr.io/ahnafnafee/songmirror:latest`，将其作为`songmirror`运行，并将所有身份验证+缓存保留在`./data`中。

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

要更新，请运行 `docker compose up -d --pull always`。要构建当前结帐，请运行 `docker compose up -d --build`。请参阅[容器镜像指南](../docker-image.md)了解标签、摘要固定、直接拉取、验证、更新和回滚。

无需 `.env` 即可启动 — 所有内容均在浏览器中配置并保存在 `./data` 下。 OAuth、合作伙伴令牌和API密钥设置均位于帐户页面上；每个向导都会解释特定于服务的先决条件和确切的回调 URI。然后在“同步”页面上构建同步。

从另一台计算机打开 SongMirror 的效果为 `http://<server>:8888`。默认 Spotify 连接使用粘贴的 `sp_dc` Web 会话，因此不需要开发人员应用程序或回调 URL。如果您有意使用旧版开发者应用程序 OAuth 后备Docker 或反向代理，请在 `.env` 中设置浏览器可见的基本 URL：

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror 将会发布`https://music.example.com/oauth/spotify/callback`；在 Spotify 应用仪表板中注册该确切的 URI，并使用 `docker compose up -d --force-recreate` 重新创建容器。还支持反向代理基本路径（例如，`https://example.com/songmirror`）。 [Spotify需要HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) 对于每个非环回重定向；普通的 HTTP 仅接受文字环回地址，例如 `127.0.0.1`，而不是 LAN IP 或 `localhost`。

| | |
| --- | --- |
|图片| `ghcr.io/ahnafnafee/songmirror:latest`支持AMD64和ARM64。每个构建版本还带有特定于提交的 `sha-...` 标签； Git 标签（例如 `v1.2.3`）另外发布 `1.2.3`、`1.2` 和 `1`。使用 [容器镜像指南](../docker-image.md) 固定不可变的摘要。 |
|港口| UI 发布在主机 8888 上（`docker-compose.yml` 中的 `8888:8080` 映射；如果发生冲突，请更改主机端）。 LAN-only — 不要将其端口转发到互联网； UI 尚未进行身份验证。 |
|坚持| `./data` 在 `playlist_backups/` 下保存凭证、令牌、缓存、歌曲存档和计划的播放列表快照。对其进行备份，以在重建过程中保留您的设置和存档。 |
|下载 |将 `DOWNLOAD_DIR` （在 `.env` 或您的 shell 中）设置为您的主机音乐目录（例如 `F:\Torrent\Music`）； compose 将其绑定安装到 `/music`。从Docker，将`JELLYFIN_URL`设置为`http://host.docker.internal:8096`。 |
|过期会话 |可更新会话将在下一次计划或手动传递时恢复。 TIDAL 网络播放器会话通过捕获的刷新令牌进行更新； Qobuz 和 Apple Music 令牌在被拒绝后仍必须重新粘贴。无需重新启动。 |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ 它是如何运作的

对于源上存在的每个选定的播放列表名称，每次传递：

1. 源播放列表快照（曲目、ISRC、添加日期）。
2. 通过该服务的帐户授权播放列表API，同时协调每个选定的连接目标上的同名播放列表。
3. 丢失的曲目已解决（缓存链接 → ISRC → 评分搜索）并附加最旧的优先；从源头消失的痕迹在警卫身后被清除。
4. （可选）[spotDL](https://github.com/spotDL/spotify-downloader) 同步每个播放列表的本地音频文件夹。

默认的事实来源是Spotify，但单向模式与提供商无关——任何连接的播放列表对等点都可以作为来源。

<a id="matching"></a>

### 配套

跨服务工具使用相同的层次结构（[TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/)，MusicBrainz）：精确标识符→搜索→模糊分数。

1. 缓存链接 — 一旦源轨道与目标的目录 ID/视频 ID 匹配，该链接就会被存储并重复使用（不受标题漂移的影响）。
2. ISRC — 服务公开的准确记录身份。
3. 评分搜索 — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler，针对原始标题和罗马化 ([anyascii](https://github.com/anyascii/anyascii)) 标题和艺术家，按持续时间锚定。这可以处理，无需硬编码：
   - 多艺术家积分 — 一项服务列出了所有功能，另一项服务列出了主要功能 (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`)。
   - 标题装饰 — `(feat. …)`、`- 2015 Remaster`、`(From "…")`，额外的“官方音乐视频”后缀。
   - 音译 — 西里尔文/孟加拉文/希腊文/阿拉伯文（`Камин` ↔ `Kamin`、`নেশার বোঝা` ↔ `Neshar Bojha`）。
   - 仅视频曲目 — YouTube 搜索会退回到 `videos` 过滤器，以搜索仅在 YT 上上传的独立/OST 曲目。

持续时间锚点解锁了更宽松的标题匹配，因此当长度不一致时，不接受不同的版本（`Runaway - Piano Version`）或错误的艺术家封面。没有可靠匹配的曲目将被报告并跳过。

<a id="multi-source-merge-sync"></a>

### 多源合并同步

合并源作业将一个或多个显式播放列表合并到一个选定的目标中。每个源都可以来自连接帐户的库或粘贴的公共提供商 URL；后者一次解析为提供程序和播放列表 ID，因此不需要保存或跟踪播放列表，并且计划的运行不会重播任意 URL。

- 一个会员联盟——在协调目的地之前阅读所有选民的意见。共享 ISRC 是一个录音；如果没有 ISRC，精确/保守的标题、艺术家、版本和持续时间证据可以消除重复。
- 确定性顺序 - 首先是源描述符优先级，然后是每个源播放列表返回的顺序。第一次出现拥有目标位置和显示元数据；后来的副本只会丰富缺失的身份元数据。
- 联合安全删除——只有当完整的通行证发现每个组成源中都不存在目标轨道时，才可以删除目标轨道。失败、截断、格式错误、不可用或未知的空源会禁用该通道的所有删除，而来自可读源的安全添加可能会继续。
- 默认情况下仅附加 - 将删除每个源中不存在的轨道保留为关闭状态，以保留所有仅目标轨道。在完整读取防护通过后，将其打开会选择进入正常的每次删除上限。

合并作业当前针对一个提供商播放列表；单独的 Spotify-led 本地下载/Jellyfin 镜像不可用于聚合作业。

<a id="authoritative-groups"></a>

### 权威团体

当您在两个或多个服务上主动策划相同的逻辑播放列表，但希望所有其他选定的服务都遵循它们时，请使用权威组。典型的设置是 Spotify + Apple Music 作为权限，TIDAL、Qobuz、Deezer、Amazon Music 和 YouTube Music 作为镜像。

- 成员资格仅来自权威机构 - 添加到 Spotify 或 Apple Music 的轨道会传播到其他权威机构和每个镜像。仅在镜子上添加的轨迹是漂移；它永远不会被重新输入当局。
- 一种排序权限 — 选择哪个权限提供播放列表名称和添加内容的顺序。其他当局仍在做出成员变更。
- 确认的删除从任一权威机构传播——在两次连续的完整读取中必须出现缺席，然后才能删除任何内容。权威方同时添加的内容胜过删除内容。
- 镜像永远不会获得投票权——从镜像中删除轨道会修复该镜像；它不会删除Spotify或Apple Music中的曲目。
- 安全第一关——每个权限集都有自己的基线。其第一次成功的传递可能会添加丢失的轨迹，但会保留所有删除的内容，直到稍后的传递证明基线稳定。
- 失败关闭 - 如果任何权限断开连接、不可读或其播放列表无法打开/创建，则将跳过该逻辑播放列表，而不是默默地退回到较少的权限。

删除操作需要明确启用，并受数量上限约束。如果需要移除镜像中的多余曲目，使其与权威来源的曲目集合一致，请为该任务启用 **同步删除曲目**，或在无图形界面模式下设置 `MAX_REMOVALS`。

<a id="bidirectional-n-way-sync"></a>

### 双向（N 路）同步

默认情况下，一个提供者是事实来源，并且编辑流程以一种方式进行。在 N 路模式中，每个选定的提供者都是对等的：在任何一个提供者上添加或删除轨道，并且更改会传播到其他提供者。

无状态的双向同步是不可能的，因此每个逻辑播放列表的规范成员资格都会在每次干净传递后进行快照。每一次传递都将每个提供者与该快照进行比较，合并更改，并使每个人都与结果一致：

- 无回声——传播的添加成为快照的一部分，因此它永远不会反弹。
- 冲突中的附加胜利——失去一首歌比保留一首额外的歌曲更糟糕。
- 读取崩溃防护 - 如果提供者突然读取的轨道比基线少得多（短暂的 API 打嗝），它会跳过该通道，因此一次错误读取无法级联大规模删除。
- 与单向相同的保护措施 — 每通道 `MAX_ADDS` / `MAX_REMOVALS` 上限和每个写入侧的净丢失保护。
- **删除需要主动启用**：`MAX_REMOVALS` 默认为 0。因此，某个服务中的曲目消失时，无论是在该服务中被删除，还是因许可原因下架，其他服务都会保留该曲目，并且只记录这项变化。设置删除上限或启用界面中的 **同步删除曲目**，即可将删除同步到其他服务。

> 始终先进行模拟。在没有 `--execute` 的情况下运行（或使用 UI 中的预览）并阅读计划 - 它会在写入任何内容之前打印每个提供程序上的每个建议的添加/删除。

<a id="liked-and-favorite-tracks"></a>

### 喜欢和最喜欢的曲目

在同步的播放列表步骤中，选择源服务的内置喜欢的集合。 SongMirror 然后询问它应该在每个选定的目的地上的位置：直接进入该服务自己喜欢/最喜欢的集合，或者进入您可以编辑其建议名称的新播放列表。新的选择仅限点赞；打开同时同步每个常规播放列表或选择单个播放列表以包含两者。

这适用于Spotify喜欢的歌曲、TIDAL/Qobuz/Deezer最喜欢的曲目、Amazon Music我的喜欢、Apple Music最喜欢的歌曲和YouTube Music喜欢的音乐。适用相同的单向、权威组和 N 向协调路径和安全上限。与普通播放列表一样，删除操作默认保持关闭，直到启用 **同步删除曲目**。

当TIDAL的登录网络播放器授权携带`r_usr`和`w_usr`时，它可以处理普通播放列表和本机最喜欢的曲目。捕获完整的登录令牌响应会为 SongMirror 提供刷新令牌以及短暂的 Bearer，因此会话可以自动更新。

其中一些集成使用提供商的第一方 Web 界面，并且可能会发生更改，恕不另行通知； [可行性评估](../design/2026-09-01-liked-tracks-sync-feasibility.md)记录了API以及每个提供商的分配约束。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 播放列表元数据备份

备份不需要第二个提供商或同步作业：

- 在“设置”→“播放列表备份”中，使用顶部的“添加备份”来添加连接的帐户。选择JSON或XML，然后选择频率，例如每天或每周。自定义间隔使用数字和单位。保留备份提供保留预设、自定义计数或所有备份。
- 备份默认为 `data/playlist_backups/<account-profile-id>/`（或 Docker 中的 `/data/playlist_backups/<account-profile-id>/`）。单击内置文件夹选择器的备份文件夹，或选择手动输入路径。自定义文件夹仍然为每个帐户提供一个单独的子文件夹。使用默认备份文件夹恢复默认值。更改位置会影响以后的备份；旧文件保留在原处。保留和下载最新版本适用于所选位置。删除计划绝不会删除已保存的文件。
- 设置→下载和Jellyfin→下载文件夹使用相同的内置选择器和手动输入。选择您的 Jellyfin 库可访问的文件夹。下载遵循“同步”选项卡上每个选择加入的同步计划。选择器显示已配置的主机路径（例如，`F:\Torrent\Music`），同时在内部保留其 Docker 映射 (`/music`)。现有的下载安装保持不变。必须首先将其他主机文件夹共享为 Docker 绑定挂载；选择卸载的文件夹会显示错误并保持当前设置不变。

- 同一设置卡显示下一次运行、存储的快照计数、上次成功的文件和计数以及最近的失败。立即备份对安全的按需运行进行排队；下载最新版本检索最新的持久快照。
- 在“播放列表”页面上，使用服务卡上的“导出”可从该服务下载单个版本的 JSON 或 XML 文件中的每个播放列表。
- 打开播放列表以仅导出该播放列表。其Soundiiz选项位于[Soundiiz记录了JSON导入形状](https://soundiiz.com/data/fileExamples/playlistExport.json)之后，因此可以通过Soundiiz的导入播放列表→从文件流程上传下载的曲目列表。
- SongMirror JSON/XML 保留播放列表顺序和名称以及提供商曲目/事件 ID、可用 ISRC、艺术家、专辑、专辑曲目位置、持续时间、添加日期、插图链接和不可用条目标记。无 ID 的目录幻影保留在备份中而不是消失。文件不包含 cookie、令牌、请求标头、预览或流文件 URL。

手动导出由浏览器下载到运行 UI 的设备。计划导出使用现有的应用程序数据卷，因此不需要第二个主机路径或容器安装。备份在同步和传输之后读取队列，而不是同时访问提供者客户端。 `schema_version`字段让未来的版本能够发展无损格式，而不会使旧的快照变得模糊。

<a id="built-in-folder-picker"></a>

### 内置文件夹选择器

单击文件夹字段或浏览...以打开内置选择器。使用位置、可单击的面包屑、后退、前进和向上一个文件夹进行导航。单击一个文件夹以选择它；双击、按 Enter 键或使用箭头将其打开。搜索过滤当前文件夹。输入文件夹路径接受完整地址。选择文件夹更新草稿；保存设置或计划以应用它。取消会使草稿保持不变。不需要桌面助手或额外的过程。

新文件夹在当前打开的位置创建一个命名的子文件夹，然后将其打开。现有项目永远不会被覆盖。取消姓名输入不会产生任何影响；创建后取消选取器会将新文件夹保留在磁盘上。您保存的备份或下载位置仅在选择并保存后才会更改。在Docker中，选择器解释了哪些路径是共享的，并显示容器路径及其配置的计算机路径（如果可用）。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿本地下载镜像(Jellyfin)

通过 [spotDL](https://github.com/spotDL/spotify-downloader) 保留每个同步播放列表的离线音频副本，每个播放列表一个文件夹。同步是真正的镜像：下载新曲目，删除本地曲目。布局已准备好 Jellyfin — 将 Jellyfin 音乐库指向下载目录，曲目和播放列表都会出现，并在每次传递时保持更新：

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

通过设置 `DOWNLOAD_DIR` 并安装 spotDL + ffmpeg 来启用它：

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- 增量 - 第一次完整下载后，仅获取新添加的曲目；删除的曲目（及其清空的专辑文件夹）将被修剪。中断的运行将在下一次传递中继续。
- 最新在先 `.m3u8` — 按添加日期的顺序书写，最新的位于顶部（设置 `LOCAL_MIRROR_ORDER=oldest` 为翻转）。使用`uv run main.py --refresh-local`从现有文件重建封面/标签/mtimes。
- Jellyfin - Jellyfin 中的播放列表封面会忽略 m3u 旁边的封面文件，因此设置 `JELLYFIN_URL` + `JELLYFIN_API_KEY`，并且每次传递都会通过 Jellyfin API 上传真实的播放列表封面。
- 音频质量 — 源为 YouTube，因此如果没有 YT Music Premium cookie，上限约为 128–160 kbps。 `LOCAL_MIRROR_FORMAT=opus` 保留 YouTube 的本机流，无需 mp3 重新编码； Premium cookie (`LOCAL_MIRROR_COOKIE_FILE`) 解锁 256 kbps AAC。选择 `flac` 会更改输出容器，但无法将有损源转换为无损音频。

Monochrome当前的FLAC路径使用浏览器控制的一次性播放资源，而不是稳定的、提供商授权的文件导出API，因此SongMirror不会自动化它。仅将本地镜像用于您拥有或被授权复制的内容。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 连接各个服务

在 Web 应用程序中，“帐户”页面将引导您完成每项服务并显示要粘贴的确切值。没有任何内容通过第三方代理。

<a id="credential-renewal"></a>

### 证书更新

SongMirror 及时刷新凭据，而不是使用单独的令牌刷新计时器。每个手动或计划的同步传递都会在第一个请求之前（或在身份验证拒绝之后一次）验证其使用的连接器并更新受支持的访问令牌。短期访问令牌在两次传递之间过期是正常的——持久刷新令牌或续订 cookie 才是重要的。帐户页面在加载或重新获得焦点时验证状态，但这不是后台会话维护；启用的同步时间表是。

|服务 |续订行为 |
| --- | --- |
| Spotify |默认连接根据需要从保存的 `sp_dc` cookie 中创建网络播放器访问令牌，并在 `401` 之后使用新令牌重试；仍然可以撤销基础登录会话。旧版开发者应用程序 OAuth 仍然支持现有安装。 |
| TIDAL |导入的网络播放器访问令牌会使用登录响应中的刷新令牌通过 `auth.tidal.com` 自动更新。当响应省略时，SongMirror 保留现有的刷新令牌，并在 TIDAL 返回 1 时保留旋转令牌。注销或撤销仍然需要重新捕获。 |
| Qobuz |粘贴的`X-User-Auth-Token`将被使用，直到Qobuz拒绝它，然后必须再次捕获。 |
| Deezer |短命管道JWT会在使用前和`401/403`之后自动从保存的`refresh-token`更新一次；旋转更新状态持续存在。 |
| Amazon Music | Web 访问令牌使用捕获的浏览器用户代理、引用者和白名单 cookie 通过 `/pandaToken` 进行更新。当前的 `POST config.json?skipToken=false` 流会在需要时引导设备上下文，并保留旋转的 cookie。注销、安全更改或服务器端撤销仍然需要重新捕获。 |
| Apple Music |粘贴的Bearer和Media-User-Token无法通过SongMirror续订，必须在拒绝后重新捕获。 |
| YouTube Music | Data API OAuth 到期后 60 秒内自动刷新。每当构建同步目标时，浏览器模式都会尝试 Google 的 cookie 轮换；必须再次导出已过期的浏览器会话。 |
| Jellyfin | API密钥没有访问令牌刷新周期；仅当其被撤销或删除时才予以替换。 |

<a id="spotify"></a>

### Spotify

1. 登录<https://open.spotify.com>。
2. 打开浏览器DevTools（`F12`）→应用程序（Chrome/Edge）或存储（Firefox）→Cookie→`https://open.spotify.com`。
3. 复制 `sp_dc` cookie 的值并将其粘贴到帐户 → Spotify 中。

该单一登录的 Web 会话可处理库浏览、播放列表读写以及目录搜索。它不需要Spotify开发者应用程序、API密钥或Premium帐户。将`sp_dc`视为密码：SongMirror将其存储在其私有数据目录中，但集成使用Spotify的内部网络播放器操作，如果Spotify更改它们，则可能需要维护。现有的开发人员应用程序OAuth凭证仍然是兼容的后备。

<a id="tidal"></a>

### TIDAL

1. 打开[TIDAL的网络播放器](https://listen.tidal.com)，打开DevTools→网络，并启用保留日志。
2. 注销并重新登录，然后筛选网络列表中的 `oauth2/token`。
3. 选择成功的`auth.tidal.com/v1/oauth2/token`请求。在有效负载 (Chrome/Edge) 或请求 (Firefox) 中，将`client_id` 表单值复制到SongMirror 的网络播放器客户端 ID 字段。
4. 打开请求的“响应”选项卡并将其完整的 JSON 复制到网络播放器令牌响应中。它应包括 `access_token` 和 `refresh_token`。
5. 连接。 SongMirror 立即行使刷新授权，如果该客户端 ID 无法续订，则拒绝报告成功。

OAuth 客户端 ID 是请求元数据，而不是 TIDAL 访问令牌内的数字 `cid` 声明。 SongMirror 仅提取访问令牌、刷新令牌、客户端 ID、范围、到期日和目录国家/地区；不相关的响应数据将被丢弃。它会在到期前和通过`https://auth.tidal.com/v1/oauth2/token`拒绝身份验证后续订一次，从而保留刷新令牌轮换。旧的 OpenAPI 请求标头粘贴仍然兼容，但由于它不包含刷新令牌，因此在过期后仍然需要重新粘贴。仅使用目录元数据和登录用户的播放列表 - 播放资产不在此集成之外。

<a id="qobuz"></a>

### Qobuz

登录<https://play.qobuz.com>，打开DevTools→网络，过滤`api.json/0.2`。选择任何包含 `X-App-Id` 和 `X-User-Auth-Token` 的请求（包括经过身份验证的 `album/story` 请求），然后复制其请求标头或将其复制为 cURL 并将其粘贴到向导中。 SongMirror 仅保留这两个值，使用与网络播放器相同的基于标头的流程发送它们，并丢弃 cookie 和不相关的浏览器元数据。无需业务API审批或用户ID；现有的合作伙伴凭证仍然是兼容环境的后备方案。

该适配器仅使用目录搜索和播放列表端点 - 它不请求流或文件 URL。

<a id="deezer"></a>

### Deezer

登录<https://www.deezer.com>，打开DevTools→网络，然后重新加载页面。过滤 `auth.deezer.com/login/renew`，复制该请求的标头（或将其复制为 cURL），然后将其粘贴到续订字段中。 Firefox 可以将请求 cookie 复制为裸露的分号分隔块；该形状也被接受。 SongMirror 仅保留专用的`refresh-token` cookie，并使用它自动更新Deezer 的短期管道JWT。您还可以粘贴当前的 `pipe.deezer.com/api` 请求作为立即引导，但配置续订时不需要这样做。播放列表的添加和删除都使用可更新的 Pipe 会话；不需要 `arl` cookie。现有的开发人员OAuth代币仍然是兼容环境的后备方案。

<a id="amazon-music"></a>

### Amazon Music

默认连接器不需要开发人员批准。它使用与 Amazon Music 网络播放器相同的身份验证 GraphQL 和令牌更新路由：

1. 登录<https://music.amazon.com>并打开DevTools→网络。
2. 重新加载页面，筛选 `config.json`，然后选择登录请求。 （`pandaToken`出现时也可以工作，但不是必需的。）
3. 选择复制请求标头或复制为 cURL，然后将其粘贴到续订字段中。保留完整的 `User-Agent`、`Referer` 和 `Cookie` 标头，以便 SongMirror 可以重播相同的浏览器上下文。
4. （可选）将登录的 `config.json` 响应复制到引导字段中； SongMirror 可以正常使用更新会话获取该设备上下文。

SongMirror在本地导出相同的`AmznMusic`授权值，并在到期前或身份验证拒绝后通过`music.amazon.com/pandaToken`刷新它。在连接过程中，当需要设备上下文时，它会使用当前浏览器样式的配置请求，需要 `/pandaToken` 创建访问令牌，并在 Amazon 撤销音乐续订 cookie 时拒绝连接。它仅存储浏览器用户代理、语言、音乐引用、亚马逊身份验证/会话 cookie 的指定允许列表以及有限的音乐客户端设备上下文；分析、实验、AWS 控制台、CSRF 和其他不相关的浏览器数据将被丢弃。这些保留的 cookie 仍然很敏感，因此请在您的 LAN 上保留 SongMirror 的私密性。注销、密码/安全更改或亚马逊端撤销仍可能需要一次新的捕获。

这是不受支持的第一方 Web 客户端界面，亚马逊可以更改它，恕不另行通知。已记录的[Amazon Music 网页 API](https://developer.amazon.com/docs/music/API_web_overview.html)仍处于封闭测试阶段；通过环境变量进行配置时，批准的合作伙伴凭据仍然是可选的后备方案。

<a id="apple-music"></a>

### Apple Music

不需要 Apple 开发者帐户 - `music.apple.com` 中的两个标头就足够了。打开<https://music.apple.com>，登录，打开DevTools→网络，播放歌曲，过滤`amp-api.music.apple.com`，然后从任何请求的标头复制：

- `authorization: Bearer eyJ...`→Bearer代币（`eyJ...`部分，不含`Bearer `）
- `media-user-token: ...` → 用户代币（全值）

连接向导允许您粘贴原始标头并为您解析值。过去几个月的代币；当它们过期时，将它们重新粘贴到“帐户”页面上。

没有有效 Apple Music 订阅的 Apple ID 仍可以在仅限目录模式下进行连接。在该模式下，将公共 Apple Music 播放列表链接粘贴到传输上，以将其复制到另一个连接的服务中。 Apple 库浏览、计划同步以及使用 Apple Music 作为传输目的地仍然需要付费的 CloudLibrary 权限； SongMirror 将这些操作显示为不可用，而不是将有效目录凭据视为已过期。

<a id="youtube-music"></a>

### YouTube Music

与官方 [YouTubeData APIv3](https://developers.google.com/youtube/v3) 对话，其 OAuth 刷新令牌是持久的并且可以在重新启动后继续存在。

1. 在[Google 云控制台](https://console.cloud.google.com)中，创建一个项目，启用YouTubeData APIv3，并创建电视和有限输入设备类型的OAuth客户端。
2. 在 OAuth 同意屏幕上，设置发布状态 → 生产中（将其保留为“测试”会使令牌在 7 天后过期）。
3. 在应用程序中，粘贴客户端 ID + 密钥并完成屏幕上的设备代码。

> 配额：Data API允许10,000个单位/天（搜索费用100，添加/删除50）。稳态维护成本低廉；大量的首次积压可能会达到上限并在第二天恢复。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️没有图形界面CLI

更喜欢 `.env` + cron / Task Scheduler？相同的引擎在没有图形界面的情况下运行。

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

有用的标志：

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

关键环境变量（参见 `.env.example`）：您使用的提供商的凭据，`PLAYLISTS`、`SYNC_INTERVAL`、`MAX_ADDS` / `MAX_REMOVALS`、`DOWNLOAD_DIR`、`SYNC_MODE`、 `SYNC_SOURCE`、`SYNC_AUTHORITIES`和`PROVIDERS`。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️安全保障

删除具有破坏性，因此要加以保护：

- 模拟是默认设置 — 如果没有 `--execute` （或 UI 的实时同步操作），则不会发生任何变化。
- 如果源为播放列表返回 0 个曲目，而目标显示为非空，则将跳过该通道的删除（瞬态 API 故障无法清空播放列表）。
- **默认禁用删除**：`MAX_REMOVALS=0` 会阻止所有删除操作，仅记录而不执行。因此，一首歌在某个平台因许可原因下架，不会导致其他平台连锁删除。请为每项同步启用 **同步删除曲目**，或设置 `MAX_REMOVALS`。即使已经启用，如果单次运行中待删除的曲目数超过上限，本次的所有删除仍会被跳过并记录。
- `MAX_ADDS` 限制同步过程中每个生成时间戳的写入，包括时间顺序修复。如果较旧的恢复比赛需要比上限允许的更大的后缀重播，SongMirror会将其推迟到下一次传递，而不是使其显示为最新的或导致巨大的提供商爆发。一次性传输没有下一次传输，因此它永远不会延迟：它会复制每个请求的曲目，并按源顺序附加，除非您为该传输打开“保留最近添加的顺序”，这会花费任何修复成本。
- 年表修复会在废弃原始副本之前暂存副本。在删除歌曲的每个副本的服务上，守护者计数必须正确，因此 Apple Music 会重新读取，直到暂存的副本可见，并且拒绝撤回任何仍落后于其自己写入的读取。 Deezer 完全跳过修复并始终附加：它也没有位置插入，因此重播它无法表达的命令不值得目的地冒风险。转移表格将其订单开关显示为灰色并说明原因。
- 净丢失保护 — 与源轨道类似但与该服务不匹配的目标端轨道将被保留，而不是被删除。
- 任何提供者身份验证失败都会立即中止该提供者的通行证 - 不会部分删除过期的令牌。
- 合并作业必须在从目标删除之前完成每个组成源的读取；任何部分/失败的源快照都会强制传递到仅追加行为。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ 缓存和歌曲存档

所有可解析的内容都被缓存，因此稳态传递几乎是即时的：每个服务解析缓存（ISRC+搜索，包括未命中），`snapshot_id`键控的轨道列表缓存，SQLite中的精确标识符链接，以及每对快照跳过（`unchanged since last clean sync`）。

每个通道还将其看到的每个轨道的元数据存档到`song_cache.db`——一个只会增长的SQLite文件。已删除的曲目将保留存档，其中包含名称、艺术家、专辑、持续时间、ISRC、原始快照JSON以及首次/上次查看时间戳：

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### 解析映射

每个服务都保留自己的解析缓存，将规范化的 `title|artist` 键映射到它匹配的目录 ID
那个服务。匹配会永远重复使用，“不匹配”结果也是如此，这就是导致轨道失败的原因
匹配一次在以后的每次传递中都保持不匹配。

Web UI 中的映射页面按服务直接公开这些缓存：

- 按标题、艺术家或解析的 ID 搜索整个缓存
- 过滤到手动设置的条目（您在传输冲突编辑器中选择的匹配项）或不匹配的条目
- 通过粘贴正确曲目的链接来纠正错误的 ID，或删除映射以便下一次再次查找
- 在一个操作中清除服务的每个“不匹配”条目，以便一批失败的查找得到另一次尝试

当清除的未命中问题稍后解决时，只需将其附加即可使旧歌曲显示为最新歌曲。对于播放列表
目的地，SongMirror 而是重播该歌曲和已经存在的较新后缀（从旧到新），然后删除
较旧的副本。提供者不允许客户端恢复原始时间戳，但这保留了它们的相对时间戳
最近添加的订单。本地喜欢/最喜欢的收藏仍然仅限会员，并且永远不会重播。

同步运行时，编辑会被拒绝并带有明确的消息，因为传递将缓存保留在内存中以供其使用。
整个持续时间，并在完成后覆盖它们。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 项目布局

CLI 条目：`uv run main.py`（薄垫片）或`python -m songmirror`。网页条目：`songmirror.web:app`。

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

添加另一个服务：子类`MirrorTarget`，实现〜8个方法，将其构建器添加到`engine/targets`'`_REGISTRY`，将其类添加到`_CLASSES`，并在`services/accounts`下添加匹配的`Connector`。所有协调——差异、排序、安全保障、日志记录、快照跳过——都是继承的。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 故障排除

- `Missing required environment variable` — 填写`.env` (CLI) 或在 UI 中连接服务。
- TIDAL 报告 `Expired` — 在 `listen.tidal.com` 注销并重新登录，然后将 `oauth2/token` 请求负载中的 `client_id` 及其完整响应 JSON 粘贴到帐户中。复制的OpenAPI请求只有短暂的Bearer并且无法续订。
- TIDAL 报告 HTTP 429 — 这是临时速率限制，而不是过期登录。 SongMirror 尊重提供者重试延迟并缓存帐户运行状况检查，而不是重复探测 API。
- Qobuz 或 Apple 报告 `Expired` / `401` / `403` — 这些粘贴的会话没有可更新的秘密；捕获帐户中新的登录请求或令牌。
- TIDAL 表示令牌缺乏喜欢的曲目访问权限 - 捕获新登录的网络播放器令牌响应，其中包含 `r_usr` 和 `w_usr`。
- Deezer 续订失败 — 捕获新的 `auth.deezer.com/login/renew` 请求（或其 `refresh-token` cookie）。当前的 Pipe Bearer 本身只是一个临时引导程序。
- Amazon Music 续订失败 — 捕获新登录的 `POST /config.json?skipToken=false` 请求及其完整的 `User-Agent`、`Referer` 和 `Cookie` 标头。响应JSON是可选的。
- YouTube Music 浏览器模式过期 — 导出新的浏览器请求标头。对于最持久的无人值守设置，请使用 Data API OAuth 以及生产中的同意屏幕。
- Spotify 报告已过期 — 再次登录 `open.spotify.com` 并将新的 `sp_dc` Cookie 粘贴到帐户中。
- 播放列表未同步 - 确认它位于同步的播放列表范围内并且存在于源中（目标是在真实传递中自动创建的）。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 许可证

版权所有 © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
该项目已获得[MIT](../../LICENSE)许可。

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
