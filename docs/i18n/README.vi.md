<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**Giữ danh sách phát luôn đồng bộ.**<br>
Tự lưu trữ để đồng bộ theo lịch, sao chép danh sách phát một lần hoặc lưu bản sao nhạc cục bộ cho Jellyfin. Miễn phí và mã nguồn mở.

[![Chạy bằng Docker][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Ủng hộ trên Ko-fi][kofi-badge]][kofi-link]

[Cài đặt có hướng dẫn](#guided-install) · [Dịch vụ được hỗ trợ](#supported-services) · [Tính năng](#features) · [Ảnh chụp màn hình](guide.vi.md#screenshots) · [Ủng hộ SongMirror](#support) · [Trang web][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.vi.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — Tổng quan · Danh sách phát" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![Gắn sao trên GitHub][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Bắt đầu nhanh

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

Mở **http://localhost:8888**. Trong **Tài khoản**, kết nối các dịch vụ bạn dùng. Chọn **Chuyển danh sách** để sao chép một lần, hoặc **Đồng bộ** để cập nhật theo lịch.

<a id="guided-install"></a>

### Cài đặt có hướng dẫn

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [Hướng dẫn sử dụng](guide.vi.md#guided-install)

<a id="app-language"></a>

### Ngôn ngữ ứng dụng

Đổi ngôn ngữ trong **Cài đặt → Chung → Ngôn ngữ**. Chọn **Tự động (trình duyệt)** để dùng ngôn ngữ của trình duyệt.

<a id="supported-services"></a>

## Dịch vụ được hỗ trợ

Mở **Tài khoản → Thêm tài khoản** và tìm dịch vụ.

| Dịch vụ | Hỗ trợ đồng bộ và chuyển |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Danh sách phát và bài hát yêu thích |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Danh sách phát |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Danh sách phát trên máy chủ |
| [Last.fm](https://www.last.fm/) | Bài hát yêu thích, bài hát nghe nhiều nhất và lịch sử nghe. Cấp quyền để sửa bài hát yêu thích. |
| [ListenBrainz](https://listenbrainz.org/) | Danh sách phát và bản thu yêu thích. Mã thông báo người dùng cho phép chỉnh sửa. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Dùng liên kết danh sách phát công khai hoặc thư viện của tài khoản đã đăng nhập làm nguồn. |

[Kết nối từng dịch vụ](guide.vi.md#connecting-each-service) · [hướng dẫn bộ kết nối danh sách phát](../music-service-adapters.md)

<a id="features"></a>

## ✨ Tính năng

- [Đồng bộ một chiều, hai chiều và nhiều nguồn](guide.vi.md#how-it-works)
- [Chuyển danh sách phát một lần](guide.vi.md#features) · [Lịch sử và khôi phục](../transfer-history.md)
- [Sao lưu siêu dữ liệu danh sách phát](guide.vi.md#playlist-metadata-backups) · [Chuyển album đã lưu](../saved-albums.md) · [Nhân bản tải xuống cục bộ (Jellyfin)](guide.vi.md#local-download-mirror-jellyfin)

[Hướng dẫn sử dụng](guide.vi.md)

<a id="support"></a>

## Ủng hộ SongMirror

Sự ủng hộ của bạn giúp trang trải chi phí bảo trì và kiểm thử trên các dịch vụ nhạc.

[![Ủng hộ trên Ko-fi][kofi-badge]][kofi-link]
[![Tài trợ trên GitHub][sponsor-badge]][sponsor-link]

[Gắn sao trên GitHub][stars-link] · [Về đầu trang](#readme-top)

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
