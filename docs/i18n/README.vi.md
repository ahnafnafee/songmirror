<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Đồng bộ hóa danh sách phát tự lưu trữ, luôn bật cho Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music và YouTube Music — cùng với một máy nhân bản âm thanh cục bộ sẵn sàng cho Jellyfin.<br/>
Một giải pháp thay thế miễn phí, mã nguồn mở, tự lưu trữ cho Soundiiz, TuneMyMusic và FreeYourMusic mà bạn sở hữu và điều hành.

**Hợp nhất một chiều, nhiều nguồn, nhóm có thẩm quyền hoặc đồng bộ hóa hai chiều hoàn toàn (N-way) · chuyển danh sách phát một lần · khớp chính xác tới ISRC · tất cả từ trình duyệt của bạn**

[Bắt đầu nhanh](#quick-start) · [Tính năng](#features) · [Ảnh chụp màn hình](#screenshots) · [Luôn chạy: Docker](#always-running-docker) · [Cách thức hoạt động](#how-it-works) · [Báo lỗi][github-issues-link] · [Đề xuất tính năng][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Chia sẻ dự án này**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Thiết lập một lần — mọi danh sách phát mà bạn tuyển chọn vẫn được phản ánh trên mọi dịch vụ, theo thứ tự ngày thêm.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror bản demo — hiển thị logo, trang tổng quan, thiết lập đồng bộ hóa một chiều và hai chiều, chuyển danh sách phát trực tiếp và kết hợp chính xác theo ISRC trên bảy dịch vụ âm nhạc" width="88%"></a>

<sup>± <a href="../../.github/assets/songmirror-demo.mp4">Xem phiên bản 1080p</a></sup>

</div>

> [!NOTE]
> Ứng dụng web + không có giao diện đồ họa CLI, một công cụ. Nhấp qua giao diện người dùng trình duyệt để kết nối các dịch vụ, xây dựng đồng bộ hóa và chuyển danh sách phát — hoặc chạy nó `.env` + kiểu cron. Cả hai đều điều khiển cùng một lõi đồng bộ.

<details>
<summary><kbd>Mục lục</kbd></summary>

#### TOC

- [✨ Tính năng](#features)
- [📸 Ảnh chụp màn hình](#screenshots)
- [🚀 Bắt đầu nhanh](#quick-start)
  - [Ngôn ngữ ứng dụng](#app-language)
- [🐳 Luôn chạy: Docker](#always-running-docker)
- [⚙️ Cách thức hoạt động](#how-it-works)
  - [Kết hợp](#matching)
  - [Đồng bộ hóa hợp nhất nhiều nguồn](#multi-source-merge-sync)
  - [Nhóm có thẩm quyền](#authoritative-groups)
  - [Đồng bộ hai chiều (N-way)](#bidirectional-n-way-sync)
- [📦 Sao lưu siêu dữ liệu danh sách phát](#playlist-metadata-backups)
- [💿 Nhân bản tải xuống cục bộ (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Kết nối từng dịch vụ](#connecting-each-service)
  - [Gia hạn thông tin xác thực](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ không có giao diện đồ họa CLI](#headless-cli)
- [🛡️ Biện pháp đảm bảo an toàn](#safety-rails)
- [🗃️ Bộ nhớ đệm và lưu trữ bài hát](#caching-song-archive)
  - [Giải quyết ánh xạ](#resolve-mappings)
- [🧱 Bố cục dự án](#project-layout)
- [🩺 Khắc phục sự cố](#troubleshooting)
- [📄 Giấy phép](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Tính năng

SongMirror giữ cho danh sách phát của bạn giống hệt nhau ở mọi nơi mà không cần thêm lại thủ công, sao chép từng cái một hoặc dịch vụ đám mây trả phí giữ thư viện của bạn. Nó đa nền tảng, tự lưu trữ và nguồn mở.

- 🔁 **Phản chiếu chân thực, không chỉ bổ sung** - bổ sung và xóa. Chọn một nguồn sự thật (Spotify theo mặc định) và những nguồn khác tuân theo nó.
- ⇆ **Nhóm có thẩm quyền** - tin tưởng hai hoặc nhiều dịch vụ (ví dụ: Spotify + Apple Music) trong khi mọi dịch vụ được chọn khác vẫn chỉ là bản sao của đích.
- ⇄ **Đồng bộ hóa N-way hai chiều** — việc thêm hoặc xóa trên bất kỳ dịch vụ được kết nối nào sẽ truyền đến tất cả các dịch vụ khác, không có tiếng vang, đằng sau các tấm bảo vệ loại bỏ.
- ⇉ **Đồng bộ hóa hợp nhất nhiều nguồn** - lên lịch liên kết các danh sách phát thư viện và URL danh sách phát công khai đã được loại bỏ trùng lặp vào một đích mà không cần lưu hoặc theo dõi danh sách công khai.
- ♥ **Các bản nhạc được yêu thích và yêu thích** - đồng bộ hóa bộ sưu tập yêu thích tích hợp của mỗi dịch vụ trên tất cả bảy nhà cung cấp âm nhạc, vào danh sách yêu thích của riêng điểm đến hoặc danh sách phát được đặt tên mới.
- 🎯 **đối sánh chính xác theo ISRC** — danh tính bản ghi chính xác nếu có, với dự phòng tiêu đề/nghệ sĩ/thời lượng tương thích gần đúng Unicode (sự khác biệt về phần ghi công của nghệ sĩ nổi bật, hậu tố "- 2015 Remaster", tập lệnh không phải tiếng Latinh, nội dung tải lên chỉ dành cho video — tất cả đều được xử lý).
- 🎛️ **Nhiều lần đồng bộ hóa được đặt tên** - thiết lập bao nhiêu lần đồng bộ hóa độc lập tùy thích, mỗi lần đồng bộ hóa có các dịch vụ, danh sách phát, lịch biểu và giới hạn an toàn riêng.
- ↪️ **chuyển một lần** — sao chép bất kỳ danh sách phát nào từ dịch vụ này sang dịch vụ khác bằng thanh tiến trình trực tiếp; tạm dừng, tiếp tục hoặc dừng sao chép giữa chừng và giải quyết các bản nhạc chưa khớp theo cách thủ công.
- 🕒 **Nối các bản nhạc hoặc giữ nguyên thứ tự bản nhạc** — theo mặc định, các bản sao sẽ ở cuối đích đến, nhanh chóng và bổ sung. Bật Bảo tồn Thứ tự đã thêm gần đây để viết lại các bản nhạc sau bản nhạc mới cũ nhất để thứ tự ngày thêm khớp với nguồn.
- 🔗 **Chuyển từ một liên kết** — dán URL danh sách phát công khai từ bất kỳ dịch vụ được kết nối nào và sao chép trực tiếp. Không cần phải lưu hoặc theo dõi nó trước.
- 🌐 **Danh sách phát đã theo dõi** — đồng bộ hóa và chuyển danh sách phát bạn theo dõi nhưng không sở hữu, không chỉ những danh sách bạn đã tạo.
- 📦 **Sao lưu siêu dữ liệu theo lịch trình** — lưu trữ toàn bộ thư viện danh sách phát của tài khoản theo lịch riêng theo dữ liệu ứng dụng liên tục, với JSON/XML, giới hạn lưu giữ và lịch sử thành công/thất bại rõ ràng. tải xuống một lần và sẵn sàng nhập Soundiiz JSON vẫn có sẵn.
- 💿 **Bản sao tải xuống cục bộ** - giữ âm thanh ngoại tuyến, một thư mục cho mỗi danh sách phát theo bố cục `AlbumArtist/Album` của Jellyfin, có bìa và `.m3u8` được cập nhật tự động.
- 🛡️ **Các biện pháp bảo vệ an toàn** — mô phỏng theo mặc định, giới hạn thêm/xóa mỗi lần vượt qua, bảo vệ chống mất mạng, bảo vệ ảnh chụp nhanh trống, hủy bỏ mà không ghi khi mã thông báo hết hạn.
- 🗃️ **Kho lưu trữ bài hát ngày càng phát triển** - mọi bản nhạc từng xem đều được ghi lại trong cơ sở dữ liệu SQLite cục bộ (tên, nghệ sĩ, album, ISRC, siêu dữ liệu thô, nhìn thấy lần đầu/lần cuối).
- 🧭 **Lịch sử đối sánh có thể chỉnh sửa** - duyệt, sửa và xóa mọi bản nhạc trùng khớp được lưu trong bộ nhớ đệm cho mỗi dịch vụ khỏi trang Bản đồ, bao gồm cả các kết quả "không khớp" mà nếu không sẽ mãi mãi không thể sánh được.
- 🐳 **Chạy ở mọi nơi** — một `docker compose up -d` cho ứng dụng trình duyệt hoặc CLI đơn giản + cron / Task Scheduler.

> [!IMPORTANT]
> Tự lưu trữ và riêng tư theo thiết kế. Dữ liệu nghe và thông tin xác thực của bạn không bao giờ rời khỏi máy của bạn. Giao diện người dùng web không có xác thực — liên kết nó với LAN của bạn và không chuyển tiếp nó sang internet.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Ảnh chụp màn hình

<div align="center">

**Một bảng thông tin cho mọi thư viện — trạng thái đồng bộ hóa, công việc, hoạt động trực tiếp và tình trạng dịch vụ**

<img src="../../.github/assets/dashboard.png" alt="Trang tổng quan SongMirror hiển thị trạng thái đồng bộ hóa, công việc đã định cấu hình, hoạt động trực tiếp và tình trạng cho Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music và Jellyfin" width="82%">

**Thiết lập bất kỳ số lượng đồng bộ hóa nào — hợp nhất một chiều, nhiều nguồn, nhóm có thẩm quyền hoặc hai chiều — trong một trình hướng dẫn ngắn**

<img src="../../.github/assets/sync-wizard.png" alt="Trình hướng dẫn thiết lập SongMirror chọn các dịch vụ để đồng bộ hóa hai chiều trên Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music và YouTube Music" width="82%">

**Kết nối mọi dịch vụ trong trình duyệt của bạn — chỉ bằng một cú nhấp chuột OAuth, dán mã thông báo được hướng dẫn hoặc phím API**

<img src="../../.github/assets/accounts.png" alt="Trang Tài khoản để kết nối Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music và Jellyfin" width="82%">

**Duyệt và ghép danh sách phát trên các dịch vụ**

<img src="../../.github/assets/playlists.png" alt="Duyệt danh sách phát trên các dịch vụ được kết nối với ảnh bìa và số lượng bản nhạc" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Bắt đầu nhanh

Cách nhanh nhất để chạy nó là Docker — Compose kéo hình ảnh đã xuất bản, phục vụ giao diện người dùng web và chạy đồng bộ hóa của bạn theo lịch trình.

Để cài đặt liên tục với khởi động lại tự động:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Hoặc thử trực tiếp hình ảnh GHCR công khai mà không cần sao chép kho lưu trữ:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Sau đó mở `http://localhost:8888` và kết nối các dịch vụ của bạn trong trình duyệt. Quá trình thiết lập Compose không cần `.env` để bắt đầu; mọi thứ đều được định cấu hình trong giao diện người dùng và được lưu trong `./data`.

Tùy chọn `docker run` trực tiếp chỉ dùng một lần: `docker stop songmirror` xóa vùng chứa và cấu hình của nó. Sử dụng Compose để cài đặt lâu bền với thông tin xác thực, bộ nhớ đệm và nội dung tải xuống liên tục hoặc xem [hướng dẫn hình ảnh container](../docker-image.md) để biết thẻ và ghim thông báo.

Thích chạy nó mà không có Docker?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Yêu cầu [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Đối với máy nhân bản tải xuống cục bộ, cũng có `uv tool install spotdl` và có `ffmpeg` trên PATH.

<a id="app-language"></a>

### Ngôn ngữ ứng dụng

SongMirror hỗ trợ tiếng Anh, tiếng Ả Rập, tiếng Thổ Nhĩ Kỳ, tiếng Tây Ban Nha, tiếng Trung giản thể, tiếng Pháp, tiếng Bồ Đào Nha, tiếng Đức, tiếng Nhật, tiếng Hindi, tiếng Bengali, tiếng Indonesia, tiếng Hàn, tiếng Ý và tiếng Việt. Khi mở lần đầu, ứng dụng kiểm tra các tùy chọn ngôn ngữ của trình duyệt theo thứ tự, kể cả biến thể theo khu vực, rồi dùng ngôn ngữ đầu tiên được hỗ trợ. Nếu không có ngôn ngữ phù hợp, ứng dụng dùng tiếng Anh. Đổi ngôn ngữ tại **Cài đặt → Chung → Ngôn ngữ**. Lựa chọn được lưu trong trình duyệt này và vẫn giữ nguyên sau khi tải lại trang. Chọn **Tự động (trình duyệt)** để tiếp tục theo tùy chọn của trình duyệt. Giao diện tiếng Ả Rập hiển thị từ phải sang trái. Tên danh sách phát, nghệ sĩ và dịch vụ, thông tin xác thực cùng nhật ký chẩn đoán giữ nguyên giá trị gốc.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Luôn chạy: Docker

Vùng chứa Docker là cách triển khai được đề xuất: nó phục vụ giao diện người dùng web, chạy đồng bộ hóa của bạn theo lịch trình của chúng và khởi động lại với máy chủ. Compose kéo `ghcr.io/ahnafnafee/songmirror:latest`, chạy dưới dạng `songmirror` và duy trì tất cả xác thực + bộ đệm trong `./data`.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Để cập nhật, hãy chạy `docker compose up -d --pull always`. Thay vào đó, để xây dựng quy trình thanh toán hiện tại, hãy chạy `docker compose up -d --build`. Xem [hướng dẫn hình ảnh container](../docker-image.md) để biết thẻ, ghim thông báo, kéo trực tiếp, xác minh, cập nhật và khôi phục.

Không cần `.env` để bắt đầu - mọi thứ đều được định cấu hình trong trình duyệt và được lưu trong `./data`. OAuth, mã thông báo đối tác và thiết lập khóa API đều có trên trang Tài khoản; mỗi trình hướng dẫn giải thích các điều kiện tiên quyết dành riêng cho từng dịch vụ và URI gọi lại chính xác. Sau đó xây dựng đồng bộ hóa của bạn trên trang Đồng bộ hóa.

Việc mở SongMirror từ một máy tính khác hoạt động ở `http://<server>:8888`. Kết nối Spotify mặc định sử dụng phiên web `sp_dc` đã dán, do đó, kết nối này không cần ứng dụng dành cho nhà phát triển hoặc URL gọi lại. Nếu bạn cố tình sử dụng ứng dụng cũ dành cho nhà phát triển OAuth dự phòng phía sau Docker hoặc proxy ngược, hãy đặt URL cơ sở hiển thị trên trình duyệt trong `.env`:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror sau đó sẽ quảng cáo `https://music.example.com/oauth/spotify/callback`; đăng ký URI chính xác đó trong bảng điều khiển ứng dụng Spotify và tạo lại vùng chứa bằng `docker compose up -d --force-recreate`. Đường dẫn cơ sở proxy ngược cũng được hỗ trợ (ví dụ: `https://example.com/songmirror`). [Spotify yêu cầu HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) cho mỗi chuyển hướng không vòng lặp; đơn giản HTTP chỉ được chấp nhận với các địa chỉ vòng lặp theo nghĩa đen như `127.0.0.1`, không phải là LAN IP hoặc `localhost`.

| | |
| --- | --- |
| Hình ảnh | `ghcr.io/ahnafnafee/songmirror:latest` hỗ trợ AMD64 và ARM64. Mỗi bản dựng cũng được xuất bản với thẻ `sha-...` dành riêng cho cam kết; Các thẻ Git như `v1.2.3` xuất bản thêm `1.2.3`, `1.2` và `1`. Sử dụng [hướng dẫn hình ảnh container](../docker-image.md) để ghim một bản tóm tắt bất biến. |
| Cảng | Giao diện người dùng được xuất bản trên máy chủ 8888 (ánh xạ `8888:8080` trong `docker-compose.yml`; thay đổi phía máy chủ nếu nó xung đột). LAN-only — không chuyển tiếp nó sang internet; giao diện người dùng chưa có xác thực. |
| Kiên trì | `./data` chứa thông tin xác thực, mã thông báo, bộ nhớ đệm, kho lưu trữ bài hát và ảnh chụp nhanh danh sách phát theo lịch trong `playlist_backups/`. Sao lưu nó để duy trì thiết lập và lưu trữ của bạn trong quá trình xây dựng lại. |
| Tải xuống | Đặt `DOWNLOAD_DIR` (trong `.env` hoặc shell của bạn) vào thư mục nhạc chủ của bạn (ví dụ: `F:\Torrent\Music`); soạn liên kết gắn kết nó với `/music`. Từ Docker, đặt `JELLYFIN_URL` thành `http://host.docker.internal:8096`. |
| Phiên hết hạn | Các phiên có thể gia hạn sẽ phục hồi ở lần vượt qua theo lịch trình hoặc thủ công tiếp theo. TIDAL phiên trình phát trên web được gia hạn từ mã thông báo làm mới đã ghi lại; Mã thông báo Qobuz và Apple Music vẫn phải được dán lại khi bị từ chối. Không cần khởi động lại. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Cách thức hoạt động

Mỗi thẻ, cho mỗi tên danh sách phát đã chọn tồn tại trên nguồn:

1. Chụp nhanh danh sách phát nguồn (các bản nhạc, ISRC, ngày được thêm vào).
2. Đồng thời điều chỉnh danh sách phát có cùng tên trên mọi mục tiêu đã chọn, được kết nối thông qua danh sách phát được tài khoản ủy quyền của dịch vụ đó API.
3. Các bản nhạc bị thiếu được giải quyết (các liên kết được lưu trong bộ nhớ đệm → ISRC → tìm kiếm được tính điểm) và được thêm vào bản cũ nhất trước; các dấu vết đi từ nguồn sẽ bị xóa sau những người bảo vệ.
4. Tùy chọn, [spotDL](https://github.com/spotDL/spotify-downloader) đồng bộ hóa thư mục âm thanh cục bộ cho mỗi danh sách phát.

Nguồn đáng tin cậy mặc định là Spotify, nhưng chế độ một chiều không phụ thuộc vào nhà cung cấp — bất kỳ danh sách ngang hàng nào được kết nối đều có thể là nguồn thay thế.

<a id="matching"></a>

### Kết hợp

Cùng một hệ thống phân cấp mà các công cụ dịch vụ chéo sử dụng ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): mã định danh chính xác → tìm kiếm → điểm mờ.

1. Liên kết được lưu trong bộ nhớ đệm — khi bản nhạc nguồn khớp với id danh mục/id video của mục tiêu, liên kết đó sẽ được lưu trữ và sử dụng lại (miễn nhiễm với hiện tượng trôi tiêu đề).
2. ISRC — bản ghi nhận dạng chính xác nơi dịch vụ hiển thị nó.
3. Tìm kiếm được tính điểm — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, trên cả tiêu đề và nghệ sĩ thô và La tinh hóa ([anyascii](https://github.com/anyascii/anyascii)), được cố định theo thời lượng. Điều này xử lý, không cần mã hóa cứng:
   - Tín dụng của nhiều nghệ sĩ - một dịch vụ liệt kê mọi tính năng, một dịch vụ khác liệt kê tính năng chính (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Trang trí tiêu đề — `(feat. …)`, `- 2015 Remaster`, `(From "…")`, thêm hậu tố "Video nhạc chính thức".
   - Phiên âm — Cyrillic / Bengali / Hy Lạp / Ả Rập (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Các bản nhạc chỉ có video — YouTube tìm kiếm quay lại bộ lọc `videos` dành cho các bản nhạc indie/OST chỉ tồn tại trên YT dưới dạng tải lên.

Cố định thời lượng sẽ mở khóa trận đấu tiêu đề lỏng lẻo hơn, do đó, một phiên bản khác (`Runaway - Piano Version`) hoặc bản cover không đúng nghệ sĩ sẽ không được chấp nhận khi độ dài của nó không đồng ý. Các bản nhạc không có kết quả trùng khớp chắc chắn sẽ được báo cáo và bỏ qua.

<a id="multi-source-merge-sync"></a>

### Đồng bộ hóa hợp nhất nhiều nguồn

Công việc Hợp nhất nguồn kết hợp một hoặc nhiều danh sách phát rõ ràng vào một đích đã chọn. Mỗi nguồn có thể đến từ thư viện của tài khoản được kết nối hoặc URL của nhà cung cấp công cộng được dán; cái sau được phân giải thành nhà cung cấp và id danh sách phát một lần, do đó danh sách phát không cần phải lưu hoặc theo dõi và các lần chạy theo lịch trình không phát lại một URL tùy ý.

- Một liên minh thành viên - tất cả các thành phần đều được đọc trước khi điểm đến được đối chiếu. ISRC được chia sẻ là một bản ghi; không có ISRC, bằng chứng về tiêu đề, nghệ sĩ, phiên bản và thời lượng chính xác/bảo thủ sẽ loại bỏ sự trùng lặp.
- Thứ tự xác định - ưu tiên mô tả nguồn trước, sau đó là thứ tự được trả về bởi mỗi danh sách phát nguồn. Lần xuất hiện đầu tiên sở hữu vị trí đích và hiển thị siêu dữ liệu; các bản sao sau này chỉ làm phong phú thêm siêu dữ liệu nhận dạng còn thiếu.
- Xóa an toàn theo liên minh - một bản nhạc đích chỉ có thể bị xóa khi một đường chuyền hoàn chỉnh không tìm thấy nó trong mọi nguồn cấu thành. Nguồn bị lỗi, bị cắt bớt, không đúng định dạng, không khả dụng hoặc không thể xác định được sẽ vô hiệu hóa mọi thao tác xóa đối với thẻ đó, trong khi các bổ sung an toàn từ các nguồn có thể đọc được có thể tiếp tục.
- Theo mặc định, chỉ nối thêm — tắt Xóa bản nhạc khỏi mọi nguồn để giữ lại tất cả các bản nhạc chỉ đích. Việc bật nó sẽ chuyển sang giới hạn loại bỏ mỗi lần vượt qua thông thường sau khi bộ bảo vệ đọc hoàn chỉnh đi qua.

Hợp nhất các công việc hiện nhắm mục tiêu vào một danh sách phát của nhà cung cấp; bản sao tải xuống cục bộ/Jellyfin riêng biệt do Spotify dẫn đầu không có sẵn cho công việc tổng hợp.

<a id="authoritative-groups"></a>

### Nhóm có thẩm quyền

Sử dụng nhóm có thẩm quyền khi bạn chủ động quản lý cùng một danh sách phát hợp lý trên hai hoặc nhiều dịch vụ nhưng muốn mọi dịch vụ được chọn khác tuân theo chúng. Thiết lập điển hình là Spotify + Apple Music làm cơ quan có thẩm quyền, với TIDAL, Qobuz, Deezer, Amazon Music và YouTube Music làm gương phản chiếu.

- Tư cách thành viên chỉ đến từ các cơ quan có thẩm quyền - một bản nhạc được thêm vào Spotify hoặc Apple Music sẽ được truyền đến cơ quan có thẩm quyền khác và mọi gương. Một đường đua chỉ được thêm vào trên gương là đường trôi dạt; nó không bao giờ được nhập trở lại vào chính quyền.
- Một cơ quan ra lệnh - chọn cơ quan nào cung cấp tên danh sách phát và thứ tự bổ sung. Các cơ quan chức năng khác vẫn góp phần thay đổi thành viên.
- Việc xóa đã được xác nhận được lan truyền từ một trong hai cơ quan - sự vắng mặt phải xuất hiện trong hai lần đọc hoàn chỉnh liên tiếp trước khi có thể xóa bất kỳ nội dung nào. Sự bổ sung đồng thời của bên có thẩm quyền sẽ thắng việc loại bỏ.
- Gương không bao giờ nhận được phiếu bầu - việc xóa một đường khỏi gương sẽ sửa chữa tấm gương đó; nó không xóa bản nhạc khỏi Spotify hoặc Apple Music.
- Vượt qua lần đầu an toàn - mỗi bộ quyền hạn đều có đường cơ sở riêng. Lần vượt qua thành công đầu tiên của nó có thể thêm các bản nhạc bị thiếu, nhưng giữ lại tất cả các phần bị xóa cho đến lần vượt qua sau đó chứng tỏ đường cơ sở ổn định.
- Đóng thất bại - nếu bất kỳ cơ quan nào bị ngắt kết nối, không thể đọc được hoặc không thể mở/tạo danh sách phát của nó thì danh sách phát hợp lý đó sẽ bị bỏ qua thay vì âm thầm quay trở lại ít cơ quan hơn.

Việc xóa phải được bật rõ ràng và vẫn chịu giới hạn số lượng. Bật **Đồng bộ việc xóa bài hát** cho tác vụ, hoặc đặt `MAX_REMOVALS` khi chạy không có giao diện đồ họa, nếu muốn xóa các bài hát thừa ở bản sao để khớp với tập bài hát của các nguồn chuẩn.

<a id="bidirectional-n-way-sync"></a>

### Đồng bộ hai chiều (N-way)

Theo mặc định, một nhà cung cấp là nguồn thông tin chính xác và các chỉnh sửa sẽ diễn ra theo một chiều. Trong chế độ N-way, mỗi nhà cung cấp được chọn đều là một nhà cung cấp ngang hàng: thêm hoặc xóa một bản nhạc trên bất kỳ nhà cung cấp nào và thay đổi sẽ lan truyền tới những nhà cung cấp khác.

Không thể đồng bộ hóa hai chiều một cách không trạng thái, vì vậy tư cách thành viên chuẩn của mỗi danh sách phát hợp lý sẽ được chụp nhanh sau mỗi lần vượt qua rõ ràng. Mỗi lần vượt qua sẽ làm khác biệt giữa mỗi nhà cung cấp với ảnh chụp nhanh đó, kết hợp các thay đổi và điều chỉnh mọi người với kết quả:

- Không có tiếng vang — phần bổ sung được lan truyền sẽ trở thành một phần của ảnh chụp nhanh nên nó không bao giờ bị trả lại.
- Lợi ích bổ sung khi xung đột - mất một bài hát còn tệ hơn việc giữ thêm một bài hát.
- Trình bảo vệ thu gọn dữ liệu đọc — nếu nhà cung cấp đột nhiên đọc ít bản nhạc hơn nhiều so với đường cơ sở (một trục trặc nhất thời API), nó sẽ bị bỏ qua đường chuyền đó nên một lần đọc sai không thể xếp tầng xóa hàng loạt.
- Các biện pháp bảo vệ tương tự như một chiều — giới hạn mỗi lượt `MAX_ADDS` / `MAX_REMOVALS` và bảo vệ chống mất mát ròng được giữ ở mọi mặt ghi.
- **Phải chủ động bật tính năng xóa** — `MAX_REMOVALS` mặc định là 0. Khi một bài hát biến mất khỏi một dịch vụ, do bị xóa tại đó hoặc bị gỡ vì bản quyền, bài hát vẫn được giữ ở các dịch vụ khác và thay đổi chỉ được ghi vào nhật ký. Đặt giới hạn hoặc bật **Đồng bộ việc xóa bài hát** trong giao diện để áp dụng việc xóa sang dịch vụ khác.

> Luôn luôn mô phỏng đầu tiên. Chạy mà không cần `--execute` (hoặc sử dụng Xem trước trong giao diện người dùng) và đọc kế hoạch - nó in mọi nội dung thêm/xóa được đề xuất trên mọi nhà cung cấp trước khi mọi nội dung được viết.

<a id="liked-and-favorite-tracks"></a>

### Các bài hát được yêu thích và yêu thích

Ở bước Danh sách phát của đồng bộ hóa, hãy chọn bộ sưu tập đã thích tích hợp sẵn của dịch vụ nguồn. SongMirror sau đó hỏi nó sẽ đi đâu trên mỗi điểm đến đã chọn: trực tiếp vào bộ sưu tập yêu thích/yêu thích của chính dịch vụ đó hoặc vào danh sách phát mới có tên gợi ý mà bạn có thể chỉnh sửa. Một lựa chọn mới chỉ được thích; bật Đồng thời đồng bộ hóa mọi danh sách phát thông thường hoặc chọn từng danh sách phát để bao gồm cả hai.

Tính năng này hoạt động trên Spotify Bài hát đã thích, TIDAL/Qobuz/Deezer Bài hát yêu thích, Amazon Music Lượt thích của tôi, Apple Music Bài hát yêu thích và YouTube Music Nhạc đã thích. Áp dụng cùng một đường dẫn hòa giải một chiều, nhóm có thẩm quyền và N-way và giới hạn an toàn. Giống như danh sách phát thông thường, việc xóa mặc định vẫn bị tắt cho đến khi bật **Đồng bộ việc xóa bài hát**.

Quyền cấp phép trình phát web đã đăng nhập của TIDAL xử lý cả danh sách phát thông thường và Bản nhạc yêu thích gốc khi nó mang `r_usr` và `w_usr`. Việc nắm bắt được phản hồi mã thông báo đăng nhập hoàn chỉnh sẽ mang lại SongMirror mã thông báo làm mới cũng như Bearer tồn tại trong thời gian ngắn, do đó phiên có thể tự động gia hạn.

Một số tiện ích tích hợp này sử dụng giao diện web bên thứ nhất của nhà cung cấp và có thể thay đổi mà không cần thông báo trước; [đánh giá tính khả thi](../design/2026-09-01-liked-tracks-sync-feasibility.md) ghi lại API và các ràng buộc phân phối cho mỗi nhà cung cấp.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Sao lưu siêu dữ liệu danh sách phát

Sao lưu không yêu cầu nhà cung cấp thứ hai hoặc công việc đồng bộ hóa:

- Trên Cài đặt → Sao lưu danh sách phát, sử dụng Thêm bản sao lưu ở trên cùng để thêm tài khoản được kết nối. Chọn JSON hoặc XML, sau đó chọn tần suất như hàng ngày hoặc hàng tuần. Khoảng thời gian tùy chỉnh sử dụng một số và một đơn vị. Giữ các bản sao lưu cung cấp các cài đặt trước lưu giữ, số lượng tùy chỉnh hoặc Tất cả các bản sao lưu.
- Các bản sao lưu mặc định là `data/playlist_backups/<account-profile-id>/` (hoặc `/data/playlist_backups/<account-profile-id>/` trong Docker). Nhấp vào Thư mục sao lưu cho bộ chọn thư mục tích hợp hoặc chọn Nhập đường dẫn theo cách thủ công. Thư mục tùy chỉnh vẫn có thư mục con riêng cho mỗi tài khoản. Sử dụng thư mục sao lưu mặc định khôi phục mặc định. Việc thay đổi vị trí ảnh hưởng đến các bản sao lưu trong tương lai; các tập tin cũ vẫn ở nguyên vị trí của chúng. Lưu giữ và Tải xuống mới nhất áp dụng cho vị trí đã chọn. Việc xóa lịch biểu không bao giờ xóa các tập tin đã lưu.
- Cài đặt → Tải xuống & Jellyfin → Thư mục tải xuống sử dụng cùng một bộ chọn tích hợp và mục nhập thủ công. Chọn một thư mục có thể truy cập vào thư viện Jellyfin của bạn. Quá trình tải xuống tuân theo lịch trình đồng bộ hóa được chọn tham gia trên tab Đồng bộ hóa. Bộ chọn hiển thị các đường dẫn máy chủ đã định cấu hình (ví dụ: `F:\Torrent\Music`) trong khi vẫn giữ lại ánh xạ Docker (`/music`) bên trong. Các mount tải xuống hiện tại không thay đổi. Các thư mục máy chủ bổ sung trước tiên phải được chia sẻ dưới dạng liên kết gắn kết Docker; việc chọn một thư mục chưa được gắn kết sẽ hiển thị lỗi và giữ nguyên cài đặt hiện tại.

- Thẻ Cài đặt tương tự hiển thị lần chạy tiếp theo, số lượng ảnh chụp nhanh được lưu trữ, số lượng và tệp thành công gần đây nhất cũng như lần thất bại gần đây nhất. Sao lưu ngay bây giờ xếp hàng chạy theo yêu cầu an toàn; Tải xuống mới nhất truy xuất ảnh chụp nhanh mới nhất.
- Trên trang Danh sách phát, sử dụng Xuất trên thẻ dịch vụ để tải xuống mọi danh sách phát từ dịch vụ đó trong một tệp JSON hoặc XML có phiên bản.
- Mở danh sách phát để chỉ xuất danh sách phát đó. Tùy chọn Soundiiz của nó tuân theo [Soundiiz được ghi lại JSON nhập hình dạng](https://soundiiz.com/data/fileExamples/playlistExport.json), do đó, danh sách bản nhạc đã tải xuống có thể được tải lên thông qua luồng Nhập danh sách phát → Từ tệp của Soundiiz.
- SongMirror JSON/XML giữ nguyên thứ tự và tên danh sách phát cộng với ID bản nhạc/sự xuất hiện của nhà cung cấp, ISRC có sẵn, nghệ sĩ, album, vị trí bản nhạc album, thời lượng, ngày thêm, liên kết tác phẩm nghệ thuật và điểm đánh dấu mục nhập không có sẵn. Bóng ma danh mục không có ID vẫn còn trong bản sao lưu thay vì biến mất. Tệp không chứa cookie, mã thông báo, tiêu đề yêu cầu, bản xem trước hoặc URL tệp phát trực tuyến.

Xuất thủ công được trình duyệt tải xuống thiết bị chạy giao diện người dùng. Xuất theo lịch trình sử dụng khối lượng dữ liệu ứng dụng hiện có, do đó không cần đường dẫn máy chủ thứ hai hoặc khung chứa. Bản sao lưu đọc hàng đợi sau quá trình đồng bộ hóa và chuyển giao thay vì truy cập đồng thời các ứng dụng khách của nhà cung cấp. Trường `schema_version` cho phép các bản phát hành trong tương lai phát triển định dạng lossless mà không làm cho các ảnh chụp nhanh cũ trở nên mơ hồ.

<a id="built-in-folder-picker"></a>

### Bộ chọn thư mục tích hợp

Nhấp vào trường thư mục hoặc Duyệt qua… để mở bộ chọn tích hợp. Sử dụng Vị trí, đường dẫn có thể nhấp, Quay lại, Chuyển tiếp và Lên trong một thư mục để điều hướng. Bấm vào một thư mục để chọn nó; bấm đúp, nhấn Enter hoặc sử dụng mũi tên của nó để mở nó. Tìm kiếm lọc thư mục hiện tại. Nhập đường dẫn thư mục chấp nhận địa chỉ đầy đủ. Chọn thư mục cập nhật bản nháp; lưu cài đặt hoặc lên lịch để áp dụng nó. Việc hủy giữ nguyên bản nháp. Không cần có trình trợ giúp máy tính để bàn hoặc quy trình bổ sung.

Thư mục mới tạo một thư mục con có tên ở vị trí hiện đang mở, sau đó mở nó ra. Các mục hiện có không bao giờ bị ghi đè. Việc hủy mục nhập tên không tạo ra gì; việc hủy bộ chọn sau khi tạo sẽ để lại thư mục mới trên đĩa. Vị trí tải xuống hoặc sao lưu đã lưu của bạn chỉ thay đổi sau khi chọn và lưu. Trong Docker, bộ chọn giải thích những đường dẫn nào được chia sẻ và hiển thị cả đường dẫn vùng chứa cũng như đường dẫn máy tính được định cấu hình của nó khi có sẵn.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Nhân bản tải xuống cục bộ (Jellyfin)

Giữ bản sao âm thanh ngoại tuyến của mỗi danh sách phát đã đồng bộ hóa, một thư mục cho mỗi danh sách phát, qua [spotDL](https://github.com/spotDL/spotify-downloader). Đồng bộ hóa là phản chiếu chân thực: các bản nhạc mới được tải xuống, các bản nhạc đã xóa sẽ bị xóa cục bộ. Bố cục đã sẵn sàng Jellyfin — trỏ thư viện nhạc Jellyfin vào thư mục tải xuống và cả các bản nhạc cũng như danh sách phát đều xuất hiện, luôn được cập nhật mỗi lượt:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Kích hoạt nó bằng cách cài đặt `DOWNLOAD_DIR` và cài đặt spotDL + ffmpeg:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Tăng dần - sau lần tải xuống đầy đủ đầu tiên, chỉ các bản nhạc mới được thêm vào mới được tìm nạp; các bản nhạc đã xóa (và các thư mục album trống của chúng) sẽ được cắt bớt. Một lượt chạy bị gián đoạn sẽ tiếp tục lượt tiếp theo.
- Mới nhất trước `.m3u8` — được viết theo thứ tự ngày thêm, mới nhất ở trên cùng (đặt `LOCAL_MIRROR_ORDER=oldest` để lật). Xây dựng lại bìa / thẻ / mtimes từ các tệp hiện có với `uv run main.py --refresh-local`.
- Danh sách phát bao gồm Jellyfin — Jellyfin bỏ qua tệp bìa bên cạnh m3u, vì vậy hãy đặt `JELLYFIN_URL` + `JELLYFIN_API_KEY` và mỗi lượt tải lên bìa danh sách phát thực thông qua Jellyfin API.
- Chất lượng âm thanh - nguồn là YouTube, vì vậy nếu không có cookie YT Music Premium thì mức trần là ~128–160 kbps. `LOCAL_MIRROR_FORMAT=opus` giữ luồng gốc của YouTube mà không cần mã hóa lại mp3; cookie Premium (`LOCAL_MIRROR_COOKIE_FILE`) mở khóa 256 kbps AAC. Chọn `flac` chỉ thay đổi vùng chứa đầu ra; nguồn âm thanh nén mất dữ liệu không thể trở thành âm thanh không mất dữ liệu.

Đường dẫn FLAC hiện tại của Monochrome sử dụng tài nguyên phát lại sử dụng một lần, được kiểm soát bởi trình duyệt thay vì xuất tệp ổn định, được nhà cung cấp ủy quyền API, vì vậy SongMirror không tự động hóa nó. Chỉ sử dụng máy nhân bản cục bộ cho nội dung bạn sở hữu hoặc được ủy quyền sao chép.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Kết nối từng dịch vụ

Trong ứng dụng web, trang Tài khoản sẽ hướng dẫn bạn từng dịch vụ và hiển thị các giá trị chính xác cần dán. Không có gì được ủy quyền thông qua bên thứ ba.

<a id="credential-renewal"></a>

### Gia hạn thông tin xác thực

SongMirror làm mới thông tin xác thực đúng lúc chứ không phải bằng bộ hẹn giờ làm mới mã thông báo riêng biệt. Mỗi lượt đồng bộ hóa thủ công hoặc theo lịch trình sẽ xác thực các trình kết nối mà nó sử dụng và gia hạn mã thông báo truy cập được hỗ trợ trước yêu cầu đầu tiên (hoặc một lần sau khi từ chối xác thực). Việc mã thông báo truy cập tồn tại trong thời gian ngắn hết hạn giữa các lần chuyển là điều bình thường. Mã thông báo làm mới lâu dài hoặc cookie gia hạn mới là điều quan trọng. Trang Tài khoản xác thực trạng thái khi tải hoặc lấy lại tiêu điểm, nhưng đó không phải là bảo trì phiên nền; đã bật lịch trình đồng bộ hóa.

| Dịch vụ | Hành vi đổi mới |
| --- | --- |
| Spotify | Kết nối mặc định tạo ra mã thông báo truy cập của trình phát web từ cookie `sp_dc` đã lưu theo yêu cầu và thử lại bằng mã thông báo mới sau `401`; phiên đăng nhập cơ bản vẫn có thể bị thu hồi. Ứng dụng dành cho nhà phát triển kế thừa OAuth vẫn được hỗ trợ cho các bản cài đặt hiện có. |
| TIDAL | Mã thông báo truy cập trình phát web đã nhập sẽ tự động gia hạn thông qua `auth.tidal.com` bằng cách sử dụng mã thông báo làm mới từ phản hồi đăng nhập. SongMirror giữ lại mã thông báo làm mới hiện có khi một phản hồi bỏ qua nó và duy trì mã thông báo đã xoay khi TIDAL trả về một mã thông báo. Đăng xuất hoặc thu hồi vẫn yêu cầu một bản chụp mới. |
| Qobuz | `X-User-Auth-Token` đã dán được sử dụng cho đến khi Qobuz từ chối nó, sau đó phải được chụp lại. |
| Deezer | Ống tồn tại trong thời gian ngắn JWT tự động gia hạn từ `refresh-token` đã lưu trước khi sử dụng và một lần sau `401/403`; trạng thái đổi mới luân phiên vẫn được duy trì. |
| Amazon Music | Mã thông báo truy cập web sẽ gia hạn thông qua `/pandaToken` bằng cách sử dụng tác nhân người dùng, người giới thiệu và cookie trong danh sách cho phép của trình duyệt đã thu thập. Bối cảnh thiết bị khởi động luồng `POST config.json?skipToken=false` hiện tại khi cần và các cookie đã xoay vẫn được duy trì. Đăng xuất, thay đổi bảo mật hoặc thu hồi phía máy chủ vẫn yêu cầu bản chụp mới. |
| Apple Music | Không thể gia hạn Bearer và Media-User-Token đã dán trước SongMirror và phải được chụp lại sau khi bị từ chối. |
| YouTube Music | Data API OAuth tự động làm mới trong vòng 60 giây sau khi hết hạn. Chế độ trình duyệt thử xoay cookie của Google bất cứ khi nào mục tiêu đồng bộ hóa được tạo; phiên trình duyệt đã hết hạn phải được xuất lại. |
| Jellyfin | Khóa API không có chu kỳ làm mới mã thông báo truy cập; chỉ thay thế nó nếu nó bị thu hồi hoặc xóa. |

<a id="spotify"></a>

### Spotify

1. Đăng nhập tại <https://open.spotify.com>.
2. Mở trình duyệt DevTools (`F12`) → Ứng dụng (Chrome/Edge) hoặc Bộ nhớ (Firefox) → Cookies → `https://open.spotify.com`.
3. Sao chép giá trị của cookie `sp_dc` và dán vào Tài khoản → Spotify.

Phiên web đăng nhập duy nhất đó xử lý việc duyệt thư viện, đọc và ghi danh sách phát cũng như tìm kiếm danh mục. Nó không yêu cầu ứng dụng dành cho nhà phát triển Spotify, khóa API hoặc tài khoản Premium. Coi `sp_dc` như mật khẩu: SongMirror lưu trữ nó trong thư mục dữ liệu riêng tư, nhưng việc tích hợp sử dụng các hoạt động của trình phát web nội bộ của Spotify và có thể cần bảo trì nếu Spotify thay đổi chúng. Thông tin xác thực hiện có của ứng dụng dành cho nhà phát triển OAuth vẫn là thông tin dự phòng tương thích.

<a id="tidal"></a>

### TIDAL

1. Mở [Trình phát web của TIDAL](https://listen.tidal.com), mở DevTools → Mạng và bật Lưu giữ nhật ký.
2. Đăng xuất và đăng nhập lại, sau đó lọc danh sách Mạng để tìm `oauth2/token`.
3. Chọn yêu cầu `auth.tidal.com/v1/oauth2/token` thành công. Trong Tải trọng (Chrome/Edge) hoặc Yêu cầu (Firefox), sao chép giá trị biểu mẫu `client_id` vào trường ID khách hàng trình phát web của SongMirror.
4. Mở tab Phản hồi của yêu cầu và sao chép JSON hoàn chỉnh của nó vào phản hồi mã thông báo của trình phát web. Nó phải bao gồm cả `access_token` và `refresh_token`.
5. Kết nối. SongMirror ngay lập tức thực hiện cấp phép làm mới và từ chối báo cáo thành công nếu ID khách hàng đó không thể gia hạn.

ID khách hàng OAuth là siêu dữ liệu yêu cầu và không phải là xác nhận quyền sở hữu số `cid` bên trong mã thông báo truy cập của TIDAL. SongMirror chỉ trích xuất mã thông báo truy cập, mã thông báo làm mới, ID khách hàng, phạm vi, thời hạn sử dụng và quốc gia danh mục; dữ liệu phản hồi không liên quan sẽ bị loại bỏ. Nó gia hạn ngay trước khi hết hạn và một lần sau khi từ chối xác thực thông qua `https://auth.tidal.com/v1/oauth2/token`, duy trì vòng quay mã thông báo làm mới. Dán tiêu đề yêu cầu OpenAPI cũ hơn vẫn tương thích, nhưng vì nó không chứa mã thông báo làm mới nên vẫn cần được dán lại sau khi hết hạn. Chỉ siêu dữ liệu danh mục và danh sách phát của người dùng đã đăng nhập mới được sử dụng—nội dung phát lại nằm ngoài sự tích hợp này.

<a id="qobuz"></a>

### Qobuz

Đăng nhập tại <https://play.qobuz.com>, mở DevTools → Mạng và lọc `api.json/0.2`. Chọn bất kỳ yêu cầu nào chứa `X-App-Id` và `X-User-Auth-Token`—bao gồm yêu cầu `album/story` đã được xác thực—sau đó sao chép tiêu đề yêu cầu của yêu cầu đó hoặc sao chép dưới dạng cURL và dán vào trình hướng dẫn. SongMirror chỉ tồn tại hai giá trị đó, gửi chúng bằng luồng dựa trên tiêu đề giống như trình phát web và loại bỏ cookie cũng như siêu dữ liệu trình duyệt không liên quan. Không yêu cầu phê duyệt doanh nghiệp API hoặc id người dùng; thông tin đăng nhập của đối tác hiện tại vẫn là phương án dự phòng môi trường tương thích.

Bộ điều hợp chỉ sử dụng điểm cuối tìm kiếm danh mục và danh sách phát—nó không yêu cầu URL luồng hoặc tệp.

<a id="deezer"></a>

### Deezer

Đăng nhập tại <https://www.deezer.com>, mở DevTools → Mạng và tải lại trang. Lọc tìm `auth.deezer.com/login/renew`, sao chép tiêu đề của yêu cầu đó (hoặc sao chép dưới dạng cURL) và dán vào trường gia hạn. Thay vào đó, Firefox có thể sao chép cookie yêu cầu dưới dạng khối được phân cách bằng dấu chấm phẩy; hình dạng đó cũng được chấp nhận. SongMirror chỉ giữ lại cookie `refresh-token` chuyên dụng và sử dụng nó để tự động gia hạn Pipe JWT tồn tại trong thời gian ngắn của Deezer. Bạn cũng có thể dán yêu cầu `pipe.deezer.com/api` hiện tại làm khởi động ngay lập tức, nhưng điều này không bắt buộc khi định cấu hình gia hạn. Việc bổ sung và xóa danh sách phát đều sử dụng phiên Pipe có thể tái tạo; không cần cookie `arl`. Mã thông báo OAuth dành cho nhà phát triển hiện tại vẫn là phương án dự phòng môi trường tương thích.

<a id="amazon-music"></a>

### Amazon Music

Không cần có sự phê duyệt của nhà phát triển đối với trình kết nối mặc định. Nó sử dụng các tuyến đường gia hạn mã thông báo và GraphQL đã được xác thực tương tự như trình phát web Amazon Music:

1. Đăng nhập tại <https://music.amazon.com> và mở DevTools → Mạng.
2. Tải lại trang, lọc `config.json` và chọn yêu cầu đăng nhập. (`pandaToken` cũng hoạt động khi nó xuất hiện nhưng không bắt buộc.)
3. Chọn Sao chép tiêu đề yêu cầu hoặc Sao chép dưới dạng cURL, sau đó dán vào trường gia hạn. Giữ các tiêu đề `User-Agent`, `Referer` và `Cookie` hoàn chỉnh để SongMirror có thể phát lại cùng một ngữ cảnh trình duyệt.
4. Tùy chọn sao chép Phản hồi `config.json` đã đăng nhập vào trường bootstrap; SongMirror thường có thể tìm nạp bối cảnh thiết bị đó bằng phiên gia hạn.

SongMirror lấy cùng một giá trị ủy quyền `AmznMusic` cục bộ và làm mới nó thông qua `music.amazon.com/pandaToken` trước khi hết hạn hoặc một lần sau khi từ chối xác thực. Trong quá trình kết nối, nó sử dụng yêu cầu cấu hình kiểu trình duyệt hiện tại khi cần ngữ cảnh của thiết bị, yêu cầu `/pandaToken` tạo mã thông báo truy cập và từ chối kết nối nếu Amazon thu hồi cookie gia hạn Âm nhạc. Nó chỉ lưu trữ tác nhân người dùng trình duyệt, ngôn ngữ, tham chiếu Âm nhạc, danh sách cho phép có tên của cookie phiên/xác thực Amazon và ngữ cảnh giới hạn của thiết bị Music-client; phân tích, thử nghiệm, bảng điều khiển AWS, CSRF và dữ liệu trình duyệt không liên quan khác sẽ bị loại bỏ. Những cookie được giữ lại đó vẫn nhạy cảm, vì vậy hãy giữ SongMirror ở chế độ riêng tư trên LAN của bạn. Đăng xuất, thay đổi mật khẩu/bảo mật hoặc thu hồi từ phía Amazon vẫn có thể yêu cầu một lần chụp mới.

Đây là giao diện web-client của bên thứ nhất không được hỗ trợ và Amazon có thể thay đổi giao diện này mà không cần thông báo trước. Tài liệu [Amazon Music Web API](https://developer.amazon.com/docs/music/API_web_overview.html) vẫn là bản beta kín; thông tin đăng nhập của đối tác được phê duyệt vẫn là dự phòng tùy chọn khi được định cấu hình thông qua các biến môi trường.

<a id="apple-music"></a>

### Apple Music

Không cần tài khoản Nhà phát triển Apple - hai tiêu đề từ `music.apple.com` là đủ. Mở <https://music.apple.com>, đăng nhập, mở DevTools → Mạng, phát bài hát, lọc `amp-api.music.apple.com` và từ bản sao tiêu đề của bất kỳ yêu cầu nào:

- `authorization: Bearer eyJ...` → Bearer mã thông báo (phần `eyJ...`, không có `Bearer `)
- `media-user-token: ...` → Mã thông báo người dùng (giá trị đầy đủ)

Trình hướng dẫn kết nối cho phép bạn dán các tiêu đề thô và phân tích các giá trị cho bạn. Token tháng trước; dán lại chúng trên trang Tài khoản khi chúng hết hạn.

ID Apple không có đăng ký Apple Music đang hoạt động vẫn có thể kết nối ở chế độ chỉ Danh mục. Ở chế độ đó, hãy dán liên kết danh sách phát Apple Music công khai trên Chuyển để sao chép liên kết đó sang một dịch vụ được kết nối khác. Duyệt thư viện Apple, đồng bộ hóa theo lịch và sử dụng Apple Music làm đích chuyển vẫn yêu cầu đặc quyền trả phí CloudLibrary; SongMirror hiển thị các thao tác đó là không khả dụng thay vì coi thông tin xác thực danh mục hợp lệ là đã hết hạn.

<a id="youtube-music"></a>

### YouTube Music

Nói chuyện với [YouTube Data API v3](https://developers.google.com/youtube/v3) chính thức, có mã thông báo làm mới OAuth bền và vẫn tồn tại sau khi khởi động lại.

1. Trong [Google Bảng điều khiển đám mây](https://console.cloud.google.com), tạo dự án, bật YouTube Data API v3 và tạo ứng dụng khách OAuth thuộc loại TV và thiết bị Đầu vào hạn chế.
2. Trên màn hình đồng ý OAuth, đặt trạng thái Xuất bản → Đang sản xuất (để ở trạng thái "Thử nghiệm" thì mã thông báo sẽ hết hạn sau 7 ngày).
3. Trong ứng dụng, dán ID khách hàng + bí mật và hoàn thành mã thiết bị trên màn hình.

> Hạn ngạch: Data API cho phép 10.000 đơn vị/ngày (một lần tìm kiếm tốn 100, thêm/xóa 50). Bảo trì trạng thái ổn định là rẻ; lượng tồn đọng lớn lần đầu có thể đạt đến giới hạn và tiếp tục vào ngày hôm sau.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ không có giao diện đồ họa CLI

Thích `.env` + cron / Task Scheduler? Công cụ tương tự chạy mà không có giao diện đồ họa.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Cờ hữu ích:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Các biến env chính (xem `.env.example`): thông tin xác thực cho bất kỳ nhà cung cấp nào bạn sử dụng, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` và `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Biện pháp đảm bảo an toàn

Việc xóa có tính chất phá hoại nên chúng được bảo vệ:

- mô phỏng là mặc định — không có gì thay đổi nếu không có `--execute` (hoặc hành động đồng bộ hóa thực của giao diện người dùng).
- Nếu nguồn trả về 0 bản nhạc cho danh sách phát mà mục tiêu hiển thị là không trống thì việc xóa sẽ bị bỏ qua (lỗi API tạm thời không thể làm trống danh sách phát).
- **Tính năng xóa mặc định bị tắt** — `MAX_REMOVALS=0` giữ lại mọi thao tác xóa; chúng chỉ được ghi vào nhật ký và không bao giờ được thực hiện. Vì vậy, việc gỡ bài hát do bản quyền trên một nền tảng không gây ra chuỗi xóa trên các nền tảng khác. Bật **Đồng bộ việc xóa bài hát** cho từng lần đồng bộ được cấu hình hoặc đặt `MAX_REMOVALS`. Kể cả khi đã bật, nếu số thao tác xóa đang chờ trong một lượt chạy vượt quá giới hạn, tất cả đều được bỏ qua và ghi vào nhật ký.
- `MAX_ADDS` giới hạn mọi thao tác ghi tạo dấu thời gian trong thẻ đồng bộ hóa, bao gồm cả sửa chữa theo trình tự thời gian. Nếu một trận đấu được khôi phục cũ hơn cần phát lại hậu tố lớn hơn giới hạn cho phép, SongMirror sẽ trì hoãn nó sang lượt tiếp theo thay vì làm cho nó xuất hiện mới nhất hoặc gây ra sự bùng nổ nhà cung cấp khổng lồ. Chuyển một lần không có lượt tiếp theo nên không bao giờ bị trì hoãn: nó sao chép mọi bản nhạc được yêu cầu, nối thêm theo thứ tự nguồn trừ khi bạn bật "Duy trì đơn hàng đã thêm gần đây" cho lần chuyển đó, việc này sẽ chi tiêu bất kỳ chi phí sửa chữa nào.
- Quá trình sửa chữa niên đại sẽ tạo ra một bản sao trước khi gỡ bỏ bản gốc. Trên một dịch vụ mà việc xóa sẽ lấy đi mọi bản sao của một bài hát, số lượng người lưu giữ đó phải chính xác, vì vậy, Apple Music đọc lại cho đến khi các bản sao được dàn dựng hiển thị và từ chối loại bỏ bất kỳ nội dung nào đối với lượt đọc vẫn theo dõi lượt ghi của chính nó. Deezer bỏ qua hoàn toàn việc sửa chữa và luôn bổ sung: nó cũng không có phần chèn vị trí, vì vậy việc phát lại một lệnh mà nó không thể diễn đạt sẽ không đáng để mạo hiểm đến đích. Biểu mẫu chuyển giao màu xám chuyển đổi lệnh của nó ở đó và cho biết lý do.
- Bảo vệ chống mất mát ròng - một bản nhạc phía mục tiêu giống như bản nhạc nguồn không khớp với dịch vụ đó sẽ được giữ lại chứ không bị xóa.
- Bất kỳ lỗi xác thực nhà cung cấp nào đều hủy bỏ thẻ của nhà cung cấp đó ngay lập tức — không xóa một phần mã thông báo đã hết hạn.
- Công việc hợp nhất phải hoàn thành mọi nguồn cấu thành được đọc trước khi xóa khỏi đích của nó; bất kỳ ảnh chụp nhanh nguồn một phần/không thành công nào sẽ chuyển sang hành vi chỉ bổ sung.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Bộ nhớ đệm và lưu trữ bài hát

Mọi thứ có thể phân giải đều được lưu vào bộ nhớ đệm nên các lần chuyển ở trạng thái ổn định gần như ngay lập tức: bộ nhớ đệm phân giải trên mỗi dịch vụ (ISRC + tìm kiếm, bao gồm cả lỗi), bộ nhớ đệm danh sách theo dõi có khóa `snapshot_id`, liên kết nhận dạng chính xác trong SQLite và bỏ qua ảnh chụp nhanh cho mỗi cặp (`unchanged since last clean sync`).

Mỗi thẻ cũng lưu trữ siêu dữ liệu của mọi bản nhạc mà nó nhìn thấy vào `song_cache.db` — một tệp SQLite ngày càng phát triển. Các bản nhạc đã xóa vẫn được lưu trữ với tên, nghệ sĩ, album, thời lượng, ISRC, ảnh chụp nhanh thô JSON và dấu thời gian nhìn thấy lần đầu/lần cuối:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Giải quyết ánh xạ

Mỗi dịch vụ giữ bộ đệm phân giải riêng, ánh xạ khóa `title|artist` được chuẩn hóa tới id danh mục mà nó khớp với
dịch vụ đó. Một kết quả trùng khớp được sử dụng lại mãi mãi và kết quả "không khớp" cũng vậy, đó là nguyên nhân khiến đường đua không thành công
để khớp một lần và không thể so sánh được ở mỗi lần vượt qua sau đó.

Trang Ánh xạ trong giao diện người dùng web hiển thị trực tiếp các bộ đệm đó cho mỗi dịch vụ:

- tìm kiếm toàn bộ bộ đệm theo tiêu đề, nghệ sĩ hoặc id đã giải quyết
- lọc các mục nhập được đặt thủ công (kết quả khớp bạn đã chọn trong trình chỉnh sửa xung đột chuyển) hoặc không có mục nhập khớp nào
- sửa id sai bằng cách dán liên kết của bản nhạc phù hợp hoặc xóa ánh xạ để lần tiếp theo tìm kiếm lại
- xóa mọi mục nhập "không khớp" cho một dịch vụ bằng một hành động, do đó, một loạt tra cứu không thành công sẽ được thử lại

Khi lỗi đã xóa được giải quyết sau này, chỉ cần thêm nó vào sẽ làm cho bài hát cũ xuất hiện mới nhất. Dành cho danh sách phát
đích đến, SongMirror thay vào đó sẽ phát lại bài hát đó và hậu tố mới hơn đã có sẵn, cũ nhất đến mới nhất, sau đó xóa
các bản sao cũ hơn. Các nhà cung cấp không cho phép khách hàng khôi phục các dấu thời gian ban đầu, nhưng điều này sẽ giữ nguyên các dấu thời gian tương đối của họ.
Đơn hàng được thêm gần đây. Các bộ sưu tập gốc được yêu thích/thích vẫn chỉ dành cho thành viên và không bao giờ được phát lại.

Các chỉnh sửa bị từ chối kèm theo thông báo rõ ràng trong khi quá trình đồng bộ hóa đang chạy vì thẻ giữ bộ đệm trong bộ nhớ cho nó.
toàn bộ thời gian và sẽ ghi đè lên chúng khi hoàn thành.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Bố cục dự án

Mục nhập CLI: `uv run main.py` (miếng chêm mỏng) hoặc `python -m songmirror`. Mục web: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Thêm một dịch vụ khác: lớp con `MirrorTarget`, triển khai ~8 phương thức, thêm trình tạo của nó vào `engine/targets`' `_REGISTRY` và lớp của nó vào `_CLASSES`, đồng thời thêm một `Connector` phù hợp trong `services/accounts`. Tất cả sự đối chiếu — khác biệt, thứ tự, biện pháp bảo vệ an toàn, ghi nhật ký, bỏ qua ảnh chụp nhanh — đều được kế thừa.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Khắc phục sự cố

- `Missing required environment variable` — điền vào `.env` (CLI) hoặc kết nối dịch vụ trong giao diện người dùng.
- TIDAL báo cáo `Expired` — đăng xuất và đăng nhập lại tại `listen.tidal.com`, sau đó dán cả `client_id` từ tải trọng yêu cầu `oauth2/token` và Phản hồi hoàn chỉnh của nó JSON vào Tài khoản. Yêu cầu OpenAPI được sao chép chỉ tồn tại trong thời gian ngắn Bearer và không thể gia hạn.
- TIDAL báo cáo HTTP 429 - đây là giới hạn tốc độ tạm thời, không phải đăng nhập đã hết hạn. SongMirror tôn trọng việc trì hoãn thử lại của nhà cung cấp và lưu vào bộ nhớ đệm các lần kiểm tra tình trạng tài khoản thay vì liên tục thăm dò API.
- Qobuz hoặc báo cáo của Apple `Expired` / `401` / `403` — những phiên đã dán này không có bí mật có thể tái tạo; nắm bắt yêu cầu hoặc mã thông báo đăng nhập mới trong Tài khoản.
- TIDAL cho biết mã thông báo thiếu quyền truy cập theo dõi lượt thích - nắm bắt phản hồi mã thông báo của trình phát web đã đăng nhập mới mang theo `r_usr` và `w_usr`.
- Gia hạn Deezer không thành công — nắm bắt yêu cầu `auth.deezer.com/login/renew` mới (hoặc cookie `refresh-token` của nó). Chỉ riêng Pipe Bearer hiện tại chỉ là một bootstrap tạm thời.
- Gia hạn Amazon Music không thành công — nắm bắt yêu cầu `POST /config.json?skipToken=false` đăng nhập mới với các tiêu đề `User-Agent`, `Referer` và `Cookie` hoàn chỉnh. Câu trả lời JSON là tùy chọn.
- YouTube Music chế độ trình duyệt hết hạn - xuất tiêu đề yêu cầu trình duyệt mới. Để thiết lập không cần giám sát lâu bền nhất, hãy sử dụng Data API OAuth với màn hình chấp thuận đang trong quá trình sản xuất.
- Spotify báo cáo Đã hết hạn — đăng nhập lại tại `open.spotify.com` và dán cookie `sp_dc` mới vào Tài khoản.
- Danh sách phát không được đồng bộ hóa — hãy xác nhận danh sách phát đó nằm trong phạm vi danh sách phát của đồng bộ hóa và tồn tại trên nguồn (mục tiêu được tạo tự động trên thẻ thực).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Giấy phép

Bản quyền © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Dự án này đã được cấp phép [MIT](../../LICENSE).

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
