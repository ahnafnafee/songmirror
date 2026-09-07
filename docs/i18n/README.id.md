<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Sinkronisasi playlist yang dihosting sendiri dan selalu aktif untuk Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, dan YouTube Music — ditambah cermin audio lokal yang siap digunakan Jellyfin.<br/>
Alternatif gratis, sumber terbuka, dan dihosting sendiri untuk Soundiiz, TuneMyMusic, dan FreeYourMusic yang Anda miliki dan jalankan.

**Sinkronisasi satu arah, penggabungan multi-sumber, grup otoritatif, atau dua arah penuh (N-arah) · transfer daftar putar satu kali · pencocokan akurat sebesar ISRC · semuanya dari browser Anda**

[Mulai Cepat](#quick-start) · [Fitur](#features) · [Tangkapan layar](#screenshots) · [Selalu berjalan: Docker](#always-running-docker) · [Cara kerjanya](#how-it-works) · [Laporkan masalah][github-issues-link] · [Usulkan fitur][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Bagikan proyek ini**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Atur sekali — setiap playlist yang Anda buat akan tetap ditampilkan di setiap layanan, sesuai urutan tanggal yang ditambahkan.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror demo — pengungkapan logo, dasbor, pengaturan sinkronisasi satu arah dan dua arah, transfer playlist langsung, dan pencocokan akurat dengan ISRC di tujuh layanan musik" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">Tonton versi 1080p</a></sup>

</div>

> [!NOTE]
> Aplikasi web + tanpa antarmuka grafis CLI, satu mesin. Klik melalui UI browser untuk menghubungkan layanan, membuat sinkronisasi, dan mentransfer daftar putar — atau menjalankannya `.env` + gaya cron. Keduanya menggerakkan inti sinkronisasi yang sama.

<details>
<summary><kbd>Daftar isi</kbd></summary>

#### Daftar Isi

- [✨ Fitur](#features)
- [📸 Tangkapan layar](#screenshots)
- [🚀 Mulai Cepat](#quick-start)
  - [Bahasa aplikasi](#app-language)
- [🐳 Selalu berjalan: Docker](#always-running-docker)
- [⚙️ Cara kerjanya](#how-it-works)
  - [Cocok](#matching)
  - [Sinkronisasi penggabungan multi-sumber](#multi-source-merge-sync)
  - [Kelompok yang berwenang](#authoritative-groups)
  - [Sinkronisasi dua arah (N-arah).](#bidirectional-n-way-sync)
- [📦 Cadangan metadata daftar putar](#playlist-metadata-backups)
- [💿 Cermin unduhan lokal (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Menghubungkan setiap layanan](#connecting-each-service)
  - [Pembaruan kredensial](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ tanpa antarmuka grafis CLI](#headless-cli)
- [🛡️ Perlindungan keamanan](#safety-rails)
- [🗃️ Caching & arsip lagu](#caching-song-archive)
  - [Selesaikan pemetaan](#resolve-mappings)
- [🧱 Tata letak proyek](#project-layout)
- [🩺 Pemecahan masalah](#troubleshooting)
- [📄 Lisensi](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Fitur

SongMirror menjaga daftar putar Anda tetap sama di mana saja tanpa menambahkan ulang secara manual, menyalin satu per satu, atau layanan cloud berbayar yang menyimpan perpustakaan Anda. Ini lintas platform, dihosting sendiri, dan open source.

- 🔁 **Pencerminan sejati, bukan hanya penambahan** — penambahan dan penghapusan. Pilih sumber kebenaran (Spotify secara default) dan yang lain mengikutinya.
- ⇆ **Grup otoritatif** — memercayai dua atau lebih layanan (misalnya Spotify + Apple Music) sementara setiap layanan lain yang dipilih tetap menjadi cermin tujuan saja.
- ⇄ **Sinkronisasi dua arah N-arah** — penambahan atau penghapusan pada layanan apa pun yang terhubung akan menyebar ke semua layanan lainnya, bebas gema, di belakang pelindung pelepasan.
- ⇉ **Sinkronisasi penggabungan multi-sumber** — menjadwalkan penggabungan daftar putar perpustakaan dan URL daftar putar publik yang dihapus duplikatnya ke dalam satu tujuan, tanpa menyimpan atau mengikuti daftar publik.
- ♥ **Lagu yang disukai dan favorit** — sinkronkan koleksi favorit yang ada di setiap layanan di ketujuh penyedia musik, baik ke favorit tujuan atau daftar putar baru yang diberi nama.
- 🎯 **pencocokan akurat sebesar ISRC** — identitas rekaman persis jika tersedia, dengan perkiraan penggantian judul/artis/durasi yang kompatibel dengan Unicode (perbedaan dalam kredit artis unggulan, akhiran "- Remaster 2015", skrip non-Latin, unggahan hanya video — semuanya ditangani).
- 🎛️ **Beberapa sinkronisasi bernama** — siapkan sinkronisasi independen sebanyak yang Anda suka, masing-masing dengan layanan, daftar putar, jadwal, dan batas keamanannya sendiri.
- ↪️ **transfer satu kali** — salin daftar putar apa pun dari satu layanan ke layanan lainnya dengan bilah kemajuan langsung; jeda, lanjutkan, atau hentikan saat penyalinan, dan selesaikan trek yang tidak cocok secara manual.
- 🕒 **Tambahkan trek atau pertahankan urutan trek** — salinan mendarat di akhir tujuan secara default, cepat dan aditif. Aktifkan Pertahankan yang Baru Ditambahkan untuk menulis ulang trek setelah trek baru terlama sehingga urutan penambahan tanggal cocok dengan sumbernya.
- 🔗 **Transfer dari tautan** — tempelkan URL daftar putar publik dari layanan mana pun yang terhubung dan salin langsung. Tidak perlu menyimpan atau mengikutinya terlebih dahulu.
- 🌐 **Daftar putar yang diikuti** — menyinkronkan dan mentransfer daftar putar yang Anda ikuti tetapi bukan milik Anda, bukan hanya daftar putar yang Anda buat.
- 📦 **Pencadangan metadata terjadwal** — arsipkan seluruh pustaka daftar putar akun sesuai jadwalnya sendiri berdasarkan data aplikasi yang persisten, dengan JSON/XML, batas retensi, dan riwayat keberhasilan/kegagalan yang terlihat. unduhan satu kali dan siap impor Soundiiz JSON tetap tersedia juga.
- 💿 **Cermin unduhan lokal** — simpan audio offline, satu folder per daftar putar dalam tata letak Jellyfin `AlbumArtist/Album`, dengan sampul dan `.m3u8` yang diperbarui secara otomatis.
- 🛡️ **Perlindungan keamanan** — simulasi secara default, batasan penambahan/penghapusan per pass, perlindungan kerugian bersih, pelindung snapshot kosong, dibatalkan tanpa menulis saat token kedaluwarsa.
- 🗃️ **Arsip lagu yang terus bertambah** — setiap lagu yang pernah dilihat direkam dalam database SQLite lokal (nama, artis, album, ISRC, metadata mentah, pertama/terakhir dilihat).
- 🧭 **Riwayat kecocokan yang dapat diedit** — telusuri, perbaiki, dan hapus setiap kecocokan trek yang disimpan dalam cache per layanan dari halaman Pemetaan, termasuk hasil "tidak cocok" yang jika tidak, akan tetap tidak cocok selamanya.
- 🐳 **Berjalan di mana saja** — satu `docker compose up -d` untuk aplikasi browser, atau CLI + cron / Task Scheduler.

> [!IMPORTANT]
> Dihosting sendiri dan bersifat pribadi berdasarkan desain. Data dan kredensial pendengaran Anda tidak pernah meninggalkan mesin Anda. UI web tidak memiliki autentikasi — ikat ke LAN Anda dan jangan meneruskannya ke internet.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Tangkapan layar

<div align="center">

**Satu dasbor untuk setiap perpustakaan — sinkronisasi status, pekerjaan, aktivitas langsung, dan kesehatan layanan**

<img src="../../.github/assets/dashboard.png" alt="SongMirror dasbor menampilkan status sinkronisasi, pekerjaan yang dikonfigurasi, aktivitas langsung, dan kesehatan untuk Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music, dan Jellyfin" width="82%">

**Siapkan sejumlah sinkronisasi — satu arah, penggabungan multi-sumber, grup otoritatif, atau dua arah — dalam panduan singkat**

<img src="../../.github/assets/sync-wizard.png" alt="Wizard pengaturan SongMirror memilih layanan untuk sinkronisasi dua arah di Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, dan YouTube Music" width="82%">

**Hubungkan setiap layanan di browser Anda — sekali klik OAuth, tempel token terpandu, atau kunci API**

<img src="../../.github/assets/accounts.png" alt="Halaman Akun untuk menghubungkan Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music, dan Jellyfin" width="82%">

**Jelajahi dan pasangkan daftar putar di seluruh layanan**

<img src="../../.github/assets/playlists.png" alt="Menelusuri daftar putar di seluruh layanan yang terhubung dengan sampul dan jumlah lagu" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Mulai Cepat

Cara tercepat untuk menjalankannya adalah Docker — Compose mengambil gambar yang dipublikasikan, menyajikan UI web, dan menjalankan sinkronisasi Anda sesuai jadwal.

Untuk instalasi persisten dengan restart otomatis:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Atau coba image GHCR publik secara langsung tanpa mengkloning repositori:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Kemudian buka `http://localhost:8888` dan sambungkan layanan Anda di browser. Penyiapan Compose tidak memerlukan `.env` untuk memulai; semuanya dikonfigurasi di UI dan disimpan di bawah `./data`.

Opsi langsung `docker run` dapat dibuang: `docker stop songmirror` menghapus wadah dan konfigurasinya. Gunakan Compose untuk instalasi yang tahan lama dengan kredensial, cache, dan unduhan yang persisten, atau lihat [panduan gambar kontainer](../docker-image.md) untuk penyematan tag dan intisari.

Lebih suka menjalankannya tanpa Docker?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Memerlukan [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Untuk mirror unduhan lokal, juga `uv tool install spotdl` dan miliki `ffmpeg` di PATH.

<a id="app-language"></a>

### Bahasa aplikasi

SongMirror mendukung bahasa Inggris, Arab, Turki, Spanyol, Cina Sederhana, Perancis, Portugis, Jerman, Jepang, Hindi, Bengali, Indonesia, Korea, Italia, dan Vietnam. Saat pertama kali dibuka, preferensi bahasa peramban diperiksa secara berurutan, termasuk varian regional, lalu bahasa pertama yang didukung digunakan. Jika tidak ada yang didukung, bahasa Inggris digunakan. Ubah bahasa melalui **Pengaturan → Umum → Bahasa**. Pilihan disimpan di peramban ini dan tetap berlaku setelah halaman dimuat ulang. Pilih **Otomatis (browser)** untuk kembali mengikuti preferensi peramban. Antarmuka bahasa Arab ditampilkan dari kanan ke kiri. Nama daftar putar, artis dan penyedia, kredensial, serta log diagnostik tetap mempertahankan nilai aslinya.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Selalu berjalan: Docker

Kontainer Docker adalah penerapan yang direkomendasikan: kontainer ini melayani UI web, menjalankan sinkronisasi Anda sesuai jadwalnya, dan memulai ulang dengan host. Compose menarik `ghcr.io/ahnafnafee/songmirror:latest`, menjalankannya sebagai `songmirror`, dan menyimpan semua cache autentikasi + di `./data`.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Untuk memperbarui, jalankan `docker compose up -d --pull always`. Untuk membuat checkout saat ini, jalankan `docker compose up -d --build`. Lihat [panduan gambar kontainer](../docker-image.md) untuk tag, penyematan intisari, penarikan langsung, verifikasi, pembaruan, dan rollback.

Tidak diperlukan `.env` untuk memulai — semuanya sudah dikonfigurasi di browser dan disimpan di bawah `./data`. OAuth, token mitra, dan API-penyiapan kunci semuanya aktif di halaman Akun; setiap wizard menjelaskan prasyarat khusus layanan dan URI panggilan balik yang tepat. Kemudian buat sinkronisasi Anda di halaman Sinkronisasi.

Membuka SongMirror dari komputer lain berfungsi pada `http://<server>:8888`. Koneksi Spotify default menggunakan sesi web `sp_dc` yang ditempelkan, sehingga tidak memerlukan aplikasi pengembang atau URL panggilan balik. Jika Anda sengaja menggunakan aplikasi pengembang lama OAuth sebagai pengganti Docker atau proksi terbalik, setel URL dasar yang terlihat di browser di `.env`:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror kemudian akan mengiklankan `https://music.example.com/oauth/spotify/callback`; daftarkan URI tersebut di dasbor aplikasi Spotify dan buat ulang container dengan `docker compose up -d --force-recreate`. Jalur dasar proxy terbalik juga didukung (misalnya, `https://example.com/songmirror`). [Spotify membutuhkan HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) untuk setiap pengalihan non-loopback; biasa HTTP hanya diterima dengan alamat loopback literal seperti `127.0.0.1`, bukan IP LAN atau `localhost`.

| | |
| --- | --- |
| Gambar | `ghcr.io/ahnafnafee/songmirror:latest` mendukung AMD64 dan ARM64. Setiap build juga diterbitkan dengan tag `sha-...` khusus komit; Tag Git seperti `v1.2.3` juga menerbitkan `1.2.3`, `1.2`, dan `1`. Gunakan [panduan gambar kontainer](../docker-image.md) untuk menyematkan intisari yang tidak dapat diubah. |
| Pelabuhan | UI diterbitkan pada host 8888 (pemetaan `8888:8080` di `docker-compose.yml`; ubah sisi host jika bentrok). LAN-only — jangan meneruskannya ke internet; UI belum memiliki otentikasi. |
| Kegigihan | `./data` menyimpan kredensial, token, cache, arsip lagu, dan cuplikan daftar putar terjadwal di bawah `playlist_backups/`. Cadangkan untuk menyimpan pengaturan dan arsip Anda selama pembangunan kembali. |
| Unduhan | Setel `DOWNLOAD_DIR` (dalam `.env` atau shell Anda) ke direktori musik host Anda (misalnya `F:\Torrent\Music`); composer bind-pasang ke `/music`. Dari Docker, setel `JELLYFIN_URL` ke `http://host.docker.internal:8096`. |
| Sesi kedaluwarsa | Sesi yang dapat diperbarui dipulihkan pada pass terjadwal atau manual berikutnya. TIDAL sesi pemutar web diperbarui dari token penyegaran yang diambil; Token Qobuz dan Apple Music masih harus ditempel ulang ketika ditolak. Tidak perlu memulai ulang. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Cara kerjanya

Setiap pass, untuk setiap nama playlist terpilih yang ada di sumbernya:

1. Ambil cuplikan playlist sumber (trek, ISRC, tanggal yang ditambahkan).
2. Rekonsiliasi daftar putar dengan nama yang sama pada setiap target yang dipilih dan terhubung secara bersamaan melalui daftar putar resmi akun layanan tersebut API.
3. Trek yang hilang diselesaikan (tautan cache → ISRC → pencarian skor) dan ditambahkan yang terlama-pertama; jejak yang hilang dari sumbernya dipindahkan ke belakang penjaga.
4. Opsional, [spotDL](https://github.com/spotDL/spotify-downloader) menyinkronkan folder audio lokal per daftar putar.

Sumber kebenaran default adalah Spotify, namun mode satu arah bersifat agnostik penyedia — rekan playlist mana pun yang terhubung dapat menjadi sumbernya.

<a id="matching"></a>

### Cocok

Hierarki yang sama yang digunakan alat lintas layanan ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): pengidentifikasi tepat → pencarian → skor fuzzy.

1. Tautan dalam cache — setelah trek sumber dicocokkan dengan id katalog/id video target, tautan tersebut disimpan dan digunakan kembali (kebal terhadap penyimpangan judul).
2. ISRC — identitas rekaman persis di tempat layanan memaparkannya.
3. Penelusuran dengan skor — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, pada judul dan artis mentah maupun yang diromanisasi ([anyascii](https://github.com/anyascii/anyascii)), berdasarkan durasi. Ini menangani, tanpa hardcoding:
   - Kredit multi-artis — satu layanan mencantumkan setiap fitur, layanan lainnya mencantumkan fitur utama (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Dekorasi judul — `(feat. …)`, `- 2015 Remaster`, `(From "…")`, tambahan akhiran "Video Musik Resmi".
   - Transliterasi — Sirilik / Bengali / Yunani / Arab (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Lagu khusus video — pencarian YouTube kembali ke filter `videos` untuk lagu indie/OST yang ditayangkan di YT hanya sebagai upload.

Jangkar durasi membuka kecocokan judul yang lebih longgar, sehingga versi yang berbeda (`Runaway - Piano Version`) atau sampul artis yang salah tidak diterima jika panjangnya tidak sesuai. Trek yang tidak memiliki kecocokan yang meyakinkan dilaporkan dan dilewati.

<a id="multi-source-merge-sync"></a>

### Sinkronisasi penggabungan multi-sumber

Pekerjaan Gabungkan sumber menggabungkan satu atau lebih daftar putar eksplisit ke dalam satu tujuan yang dipilih. Setiap sumber dapat berasal dari perpustakaan akun yang terhubung atau URL penyedia publik yang ditempelkan; yang terakhir diselesaikan ke penyedia dan id daftar putar satu kali, sehingga daftar putar tidak perlu disimpan atau diikuti dan pemutaran terjadwal tidak memutar ulang URL sembarangan.

- Satu kesatuan keanggotaan — semua konstituen dibaca sebelum tujuan direkonsiliasi. ISRC bersama adalah satu rekaman; tanpa ISRC, judul persis/konservatif, artis, versi, dan bukti durasi akan menghilangkan duplikat yang tumpang tindih.
- Urutan deterministik — prioritas deskriptor sumber terlebih dahulu, lalu urutan yang dikembalikan oleh setiap playlist sumber. Kejadian pertama memiliki posisi tujuan dan menampilkan metadata; salinan selanjutnya hanya memperkaya metadata identitas yang hilang.
- Penghapusan yang aman bagi serikat pekerja — jalur tujuan hanya dapat dihapus jika izin lengkap tidak menemukannya di setiap sumber konstituen. Sumber yang gagal, terpotong, salah format, tidak tersedia, atau kosong tanpa diketahui akan menonaktifkan setiap penghapusan pass tersebut, sementara penambahan aman dari sumber yang dapat dibaca dapat dilanjutkan.
- Hanya tambahkan secara default — biarkan Hapus trek yang tidak ada dari setiap sumber nonaktif untuk menyimpan semua trek yang hanya tujuan. Mengaktifkannya akan masuk ke dalam batas pelepasan normal per lintasan setelah pelindung baca lengkap lolos.

Penggabungan pekerjaan saat ini menargetkan satu playlist penyedia; unduhan lokal terpisah yang dipimpin Spotify/mirror Jellyfin tidak tersedia untuk pekerjaan agregat.

<a id="authoritative-groups"></a>

### Kelompok yang berwenang

Gunakan grup otoritatif ketika Anda secara aktif menyusun daftar putar logis yang sama di dua atau lebih layanan, namun ingin setiap layanan lain yang dipilih mengikutinya. Pengaturan umumnya adalah Spotify + Apple Music sebagai otoritas, dengan TIDAL, Qobuz, Deezer, Amazon Music, dan YouTube Music sebagai cermin.

- Keanggotaan hanya berasal dari otoritas — jalur yang ditambahkan pada Spotify atau Apple Music menyebar ke otoritas lain dan setiap mirror. Trek yang ditambahkan hanya pada cermin adalah drift; itu tidak pernah diimpor kembali ke pihak berwenang.
- Satu otoritas urutan — pilih otoritas mana yang menyediakan nama daftar putar dan urutan penambahan. Otoritas lain masih berkontribusi pada perubahan keanggotaan.
- Penghapusan yang dikonfirmasi menyebar dari salah satu otoritas — ketidakhadiran harus muncul dalam dua pembacaan lengkap berturut-turut sebelum dapat menghapus apa pun. Penambahan pihak otoritas secara simultan menang atas penghapusan.
- Cermin tidak pernah mendapat suara — menghapus trek dari cermin memperbaiki cermin itu; itu tidak menghapus trek dari Spotify atau Apple Music.
- Jalur pertama yang aman — setiap kumpulan otoritas memiliki landasannya sendiri. Operan pertama yang berhasil mungkin menambah jejak yang hilang, namun menahan semua penghapusan hingga operan selanjutnya membuktikan garis dasar stabil.
- Gagal ditutup — jika ada otoritas yang terputus, tidak dapat dibaca, atau daftar putarnya tidak dapat dibuka/dibuat, daftar putar logis tersebut akan dilewati alih-alih secara diam-diam dikembalikan ke otoritas yang lebih sedikit.

Penghapusan harus diaktifkan secara eksplisit dan tetap dibatasi jumlahnya. Aktifkan **Sinkronkan penghapusan lagu** untuk tugas tersebut, atau atur `MAX_REMOVALS` saat menjalankan tanpa antarmuka grafis, jika Anda ingin menghapus lagu berlebih di salinan agar sesuai dengan kumpulan lagu sumber acuan.

<a id="bidirectional-n-way-sync"></a>

### Sinkronisasi dua arah (N-arah).

Secara default, satu penyedia adalah sumber kebenaran dan pengeditan mengalir satu arah. Dalam mode N-way, setiap penyedia yang dipilih adalah rekan: menambah atau menghapus trek pada salah satu penyedia dan perubahan akan menyebar ke penyedia lainnya.

Sinkronisasi dua arah tidak mungkin dilakukan tanpa negara, sehingga keanggotaan kanonik setiap daftar putar logis diambil setelah setiap clean pass. Setiap pass membedakan setiap penyedia dengan snapshot tersebut, menyatukan perubahan, dan merekonsiliasi semua orang dengan hasilnya:

- Bebas gema — penambahan yang disebarkan menjadi bagian dari cuplikan, sehingga tidak pernah dikembalikan lagi.
- Kemenangan tambahan dalam konflik — kehilangan sebuah lagu lebih buruk daripada menyimpan lagu tambahan.
- Penjaga baca-ciutkan — jika penyedia tiba-tiba membaca trek yang jauh lebih sedikit daripada garis dasar (cegukan sementara API), maka jalur tersebut dilewati sehingga satu pembacaan buruk tidak dapat melakukan penghapusan massal.
- Perlindungan yang sama seperti satu arah — batas per-pass `MAX_ADDS` / `MAX_REMOVALS` dan perlindungan kerugian bersih berlaku di setiap sisi tulis.
- **Penghapusan harus diaktifkan terlebih dahulu** — nilai bawaan `MAX_REMOVALS` adalah 0. Lagu yang hilang dari satu layanan, baik karena dihapus di sana maupun ditarik karena lisensi, tetap disimpan di layanan lain dan perubahannya hanya dicatat. Tetapkan batas atau aktifkan **Sinkronkan penghapusan lagu** di antarmuka untuk menerapkan penghapusan ke layanan lain.

> Selalu simulasi dulu. Jalankan tanpa `--execute` (atau gunakan Pratinjau di UI) dan baca rencananya — rencana tersebut akan mencetak setiap usulan penambahan/penghapusan pada setiap penyedia sebelum ada yang ditulis.

<a id="liked-and-favorite-tracks"></a>

### Lagu yang disukai dan favorit

Pada langkah Daftar Putar sinkronisasi, pilih koleksi yang disukai bawaan layanan sumber. SongMirror kemudian menanyakan ke mana harus pergi pada setiap tujuan yang dipilih: langsung ke koleksi kesukaan/favorit layanan tersebut, atau ke daftar putar baru yang nama sarannya dapat Anda edit. Pilihan baru hanya untuk disukai; aktifkan Juga sinkronkan setiap daftar putar reguler atau pilih daftar putar individual untuk menyertakan keduanya.

Ini berfungsi di Spotify Lagu yang Disukai, TIDAL/Qobuz/Deezer Lagu Favorit, Amazon Music Kesukaan Saya, Apple Music Lagu Favorit, dan YouTube Music Musik yang Disukai. Jalur rekonsiliasi dan batas keamanan satu arah, kelompok otoritatif, dan N-arah yang sama juga berlaku. Seperti daftar putar biasa, penghapusan tetap dinonaktifkan secara bawaan sampai **Sinkronkan penghapusan lagu** diaktifkan.

Hibah pemutar web yang masuk dari TIDAL menangani daftar putar biasa dan Lagu Favorit asli saat membawa `r_usr` dan `w_usr`. Menangkap respons token masuk yang lengkap akan memberikan SongMirror token penyegaran serta Bearer yang berumur pendek, sehingga sesi dapat diperpanjang secara otomatis.

Beberapa dari integrasi ini menggunakan antarmuka web pihak pertama penyedia dan dapat berubah tanpa pemberitahuan; [penilaian kelayakan](../design/2026-09-01-liked-tracks-sync-feasibility.md) mencatat API dan batasan distribusi untuk setiap penyedia.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Cadangan metadata daftar putar

Pencadangan tidak memerlukan penyedia kedua atau tugas sinkronisasi:

- Pada Pengaturan → Cadangan daftar putar, gunakan Tambahkan cadangan di bagian atas untuk menambahkan akun yang terhubung. Pilih JSON atau XML, lalu pilih frekuensi seperti harian atau mingguan. Interval khusus menggunakan angka dan satuan. Simpan cadangan menawarkan preset retensi, jumlah khusus, atau Semua cadangan.
- Cadangan default ke `data/playlist_backups/<account-profile-id>/` (atau `/data/playlist_backups/<account-profile-id>/` di Docker). Klik Folder cadangan untuk pemilih folder bawaan, atau pilih Masukkan jalur secara manual. Folder khusus masih mendapat subfolder terpisah untuk setiap akun. Gunakan folder cadangan default untuk memulihkan default. Mengubah lokasi mempengaruhi pencadangan di masa mendatang; file lama tetap di tempatnya. Retensi dan Unduhan terbaru berlaku untuk lokasi yang dipilih. Menghapus jadwal tidak pernah menghapus file yang disimpan.
- Pengaturan → Unduhan & Jellyfin → Folder unduhan menggunakan pemilih bawaan dan entri manual yang sama. Pilih folder yang dapat diakses oleh perpustakaan Jellyfin Anda. Pengunduhan mengikuti setiap jadwal sinkronisasi yang diikutsertakan di tab Sinkronisasi. Picker menampilkan jalur host yang dikonfigurasi (misalnya, `F:\Torrent\Music`) sambil mempertahankan pemetaan Docker (`/music`) secara internal. Mount unduhan yang ada tidak berubah. Folder host tambahan harus dibagikan terlebih dahulu sebagai Docker pengikatan pengikat; memilih folder yang tidak di-mount menunjukkan kesalahan dan membiarkan pengaturan saat ini tidak berubah.

- Kartu Pengaturan yang sama menunjukkan proses berikutnya, jumlah snapshot yang disimpan, file dan jumlah terakhir yang berhasil, serta kegagalan terbaru. Cadangkan sekarang antrekan proses yang aman sesuai permintaan; Download terbaru mengambil snapshot terbaru yang masih ada.
- Di halaman Daftar Putar, gunakan Ekspor pada kartu layanan untuk mengunduh setiap daftar putar dari layanan tersebut dalam satu file berversi JSON atau XML.
- Buka daftar putar untuk mengekspor daftar putar itu saja. Opsi Soundiiz-nya mengikuti [Soundiiz didokumentasikan JSON bentuk impor](https://soundiiz.com/data/fileExamples/playlistExport.json), sehingga daftar lagu yang diunduh dapat diunggah melalui Impor Daftar Putar → Dari aliran File Soundiiz.
- SongMirror JSON/XML mempertahankan urutan dan nama daftar putar ditambah ID trek/kemunculan penyedia, ISRC yang tersedia, artis, album, posisi trek album, durasi, tanggal tambahan, tautan karya seni, dan penanda entri yang tidak tersedia. Katalog tanpa ID hantu tetap ada di cadangan bukannya menghilang. File tidak berisi cookie, token, header permintaan, pratinjau, atau URL file streaming.

Ekspor manual diunduh oleh browser ke perangkat yang menjalankan UI. Ekspor terjadwal menggunakan volume data aplikasi yang ada, sehingga tidak diperlukan jalur host kedua atau pemasangan kontainer. Antrean baca cadangan di belakang sinkronisasi dan transfer alih-alih mengakses klien penyedia secara bersamaan. Bidang `schema_version` memungkinkan rilis mendatang mengembangkan format lossless tanpa membuat snapshot lama menjadi ambigu.

<a id="built-in-folder-picker"></a>

### Pemilih folder bawaan

Klik bidang folder atau Telusuri… untuk membuka alat pilih bawaan. Gunakan Lokasi, remah roti yang dapat diklik, Mundur, Maju, dan Atas satu folder untuk bernavigasi. Klik folder untuk memilihnya; klik dua kali, tekan Enter, atau gunakan panahnya untuk membukanya. Pencarian memfilter folder saat ini. Masukkan jalur folder menerima alamat lengkap. Pilih folder pembaruan draf; simpan pengaturan atau jadwal untuk menerapkannya. Batal membuat draf tidak berubah. Tidak diperlukan bantuan desktop atau proses tambahan.

Folder baru membuat subfolder bernama di lokasi yang sedang dibuka, lalu membukanya. Item yang ada tidak pernah ditimpa. Membatalkan entri nama tidak menghasilkan apa-apa; membatalkan pemilih setelah pembuatan akan meninggalkan folder baru di disk. Lokasi cadangan atau unduhan yang Anda simpan hanya berubah setelah memilih dan menyimpan. Di Docker, pemilih menjelaskan jalur mana yang dibagikan dan menampilkan jalur kontainer dan jalur komputer yang dikonfigurasi jika tersedia.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Cermin unduhan lokal (Jellyfin)

Simpan salinan audio offline dari setiap daftar putar yang disinkronkan, satu folder per daftar putar, melalui [spotDL](https://github.com/spotDL/spotify-downloader). Sinkronisasi adalah pencerminan yang sebenarnya: trek baru diunduh, trek yang dihapus dihapus secara lokal. Tata letaknya sudah Jellyfin siap — arahkan perpustakaan musik Jellyfin ke direktori unduhan dan lagu serta daftar putar akan muncul, terus diperbarui setiap kali lewat:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Aktifkan dengan mengatur `DOWNLOAD_DIR` dan menginstal spotDL + ffmpeg:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Inkremental — setelah pengunduhan penuh pertama, hanya trek yang baru ditambahkan yang diambil; trek yang dihapus (dan folder albumnya yang dikosongkan) dipangkas. Lari yang terputus berlanjut pada lintasan berikutnya.
- Terbaru-pertama `.m3u8` — ditulis dalam urutan penambahan tanggal, terbaru di atas (atur `LOCAL_MIRROR_ORDER=oldest` untuk membalik). Bangun kembali sampul / tag / mtimes dari file yang ada dengan `uv run main.py --refresh-local`.
- Sampul daftar putar di Jellyfin — Jellyfin mengabaikan file sampul di sebelah m3u, jadi atur `JELLYFIN_URL` + `JELLYFIN_API_KEY` dan setiap pass mengunggah sampul daftar putar sebenarnya melalui Jellyfin API.
- Kualitas audio — sumbernya adalah YouTube, jadi tanpa cookie YT Music Premium, batas maksimumnya adalah ~128–160 kbps. `LOCAL_MIRROR_FORMAT=opus` menyimpan aliran asli YouTube tanpa pengkodean ulang mp3; cookie Premium (`LOCAL_MIRROR_COOKIE_FILE`) membuka 256 kbps AAC. Memilih `flac` akan mengubah wadah keluaran tetapi tidak dapat mengubah sumber lossy menjadi audio lossless.

Jalur FLAC Monochrome saat ini menggunakan sumber daya pemutaran sekali pakai yang dilindungi browser, bukan ekspor file stabil dan resmi dari penyedia API, jadi SongMirror tidak mengotomatiskannya. Gunakan mirror lokal hanya untuk konten yang Anda miliki atau yang diizinkan untuk disalin.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Menghubungkan setiap layanan

Di aplikasi web, halaman Akun memandu Anda melalui setiap layanan dan menunjukkan nilai yang tepat untuk ditempel. Tidak ada yang diproksi melalui pihak ketiga.

<a id="credential-renewal"></a>

### Pembaruan kredensial

SongMirror menyegarkan kredensial tepat pada waktunya, bukan dengan pengatur waktu penyegaran token terpisah. Setiap jalur sinkronisasi manual atau terjadwal memvalidasi konektor yang digunakannya dan memperbarui token akses yang didukung sebelum permintaan pertama (atau satu kali setelah penolakan autentikasi). Merupakan hal yang normal jika token akses yang berumur pendek akan kedaluwarsa di antara pass—token penyegaran atau cookie pembaruan yang tahan lama adalah yang terpenting. Halaman Akun memvalidasi status ketika memuat atau mendapatkan kembali fokus, namun ini bukan pemeliharaan sesi latar belakang; jadwal sinkronisasi yang diaktifkan adalah.

| Layanan | Perilaku pembaruan |
| --- | --- |
| Spotify | Koneksi default mencetak token akses pemutar web dari cookie `sp_dc` yang disimpan sesuai permintaan dan mencoba lagi dengan token baru setelah `401`; sesi masuk yang mendasarinya masih dapat dicabut. Aplikasi pengembang lama OAuth tetap didukung untuk pemasangan yang sudah ada. |
| TIDAL | Token akses pemutar web yang diimpor diperbarui secara otomatis melalui `auth.tidal.com` menggunakan token penyegaran dari respons masuk. SongMirror menyimpan token penyegaran yang ada ketika respons menghilangkannya dan mempertahankan token yang diputar ketika TIDAL mengembalikannya. Logout atau pencabutan masih memerlukan tangkapan baru. |
| Qobuz | `X-User-Auth-Token` yang ditempel digunakan sampai Qobuz menolaknya, lalu harus ditangkap lagi. |
| Deezer | Pipa berumur pendek JWT diperbarui secara otomatis dari `refresh-token` sebelum digunakan dan sekali setelah `401/403`; status pembaruan yang diputar tetap ada. |
| Amazon Music | Token akses web diperbarui melalui `/pandaToken` menggunakan agen pengguna browser yang diambil, rujukan, dan cookie yang diizinkan. Konteks perangkat bootstrap aliran `POST config.json?skipToken=false` saat ini bila diperlukan, dan cookie yang diputar tetap ada. Logout, perubahan keamanan, atau pencabutan sisi server masih memerlukan pengambilan baru. |
| Apple Music | Bearer dan Media-User-Token yang ditempel tidak dapat diperpanjang dengan SongMirror dan harus diambil lagi setelah ditolak. |
| YouTube Music | Data API OAuth disegarkan secara otomatis dalam waktu 60 detik setelah habis masa berlakunya. Mode browser mencoba rotasi cookie Google setiap kali target sinkronisasi dibuat; sesi browser yang sudah kedaluwarsa harus diekspor lagi. |
| Jellyfin | Kunci API tidak memiliki siklus penyegaran token akses; menggantinya hanya jika dicabut atau dihapus. |

<a id="spotify"></a>

### Spotify

1. Masuk di <https://open.spotify.com>.
2. Buka browser DevTools (`F12`) → Aplikasi (Chrome/Edge) atau Penyimpanan (Firefox) → Cookie → `https://open.spotify.com`.
3. Salin nilai cookie `sp_dc` dan tempelkan ke Akun → Spotify.

Sesi web masuk tunggal tersebut menangani penjelajahan perpustakaan, pembacaan dan penulisan daftar putar, dan pencarian katalog. Ini tidak memerlukan aplikasi pengembang Spotify, kunci API, atau akun Premium. Perlakukan `sp_dc` seperti kata sandi: SongMirror menyimpannya dalam direktori data pribadinya, namun integrasinya menggunakan operasi pemutar web internal Spotify dan memerlukan pemeliharaan jika Spotify mengubahnya. Kredensial aplikasi pengembang OAuth yang ada tetap merupakan cadangan yang kompatibel.

<a id="tidal"></a>

### TIDAL

1. Buka [pemutar web TIDAL](https://listen.tidal.com), buka DevTools → Jaringan, dan aktifkan Pertahankan log.
2. Keluar dan masuk kembali, lalu filter daftar Jaringan untuk `oauth2/token`.
3. Pilih permintaan `auth.tidal.com/v1/oauth2/token` yang berhasil. Di Payload (Chrome/Edge) atau Permintaan (Firefox), salin nilai formulir `client_id` ke bidang ID klien pemutar Web SongMirror.
4. Buka tab Respons permintaan dan salin JSON lengkapnya ke respons token pemutar Web. Ini harus mencakup `access_token` dan `refresh_token`.
5. Hubungkan. SongMirror segera menggunakan izin penyegaran dan menolak melaporkan keberhasilan jika ID klien tidak dapat memperbaruinya.

ID klien OAuth adalah metadata permintaan dan bukan klaim numerik `cid` di dalam token akses TIDAL. SongMirror hanya mengekstrak token akses, token penyegaran, ID klien, cakupan, masa berlaku, dan negara katalog; data respons yang tidak terkait dibuang. Ini diperbarui tepat sebelum habis masa berlakunya dan satu kali setelah penolakan autentikasi melalui `https://auth.tidal.com/v1/oauth2/token`, mempertahankan rotasi token penyegaran. Tempel header permintaan OpenAPI yang lebih lama tetap kompatibel, namun karena tidak mengandung token penyegaran, maka masih perlu ditempel ulang setelah habis masa berlakunya. Hanya metadata katalog dan playlist pengguna yang login yang digunakan—aset pemutaran tetap berada di luar integrasi ini.

<a id="qobuz"></a>

### Qobuz

Masuk di <https://play.qobuz.com>, buka DevTools → Jaringan, dan filter untuk `api.json/0.2`. Pilih permintaan apa pun yang berisi `X-App-Id` dan `X-User-Auth-Token`—termasuk permintaan `album/story` yang diautentikasi—lalu salin header permintaannya atau salin sebagai cURL dan tempelkan ke wizard. SongMirror hanya mempertahankan kedua nilai tersebut, mengirimkannya menggunakan aliran berbasis header yang sama dengan pemutar web, dan membuang cookie dan metadata browser yang tidak terkait. Tidak diperlukan persetujuan bisnis API atau id pengguna; kredensial mitra yang ada tetap menjadi pengganti lingkungan yang kompatibel.

Adaptor hanya menggunakan pencarian katalog dan titik akhir daftar putar—tidak meminta URL streaming atau file.

<a id="deezer"></a>

### Deezer

Masuk di <https://www.deezer.com>, buka DevTools → Jaringan, dan muat ulang halaman. Filter untuk `auth.deezer.com/login/renew`, salin header permintaan tersebut (atau salin sebagai cURL), dan tempelkan ke kolom pembaruan. Firefox mungkin menyalin cookie permintaan sebagai blok yang dibatasi titik koma; bentuk itu diterima juga. SongMirror hanya menyimpan cookie `refresh-token` khusus dan menggunakannya untuk memperbarui Pipe JWT yang berumur pendek Deezer secara otomatis. Anda juga dapat menempelkan permintaan `pipe.deezer.com/api` saat ini sebagai bootstrap langsung, namun hal ini tidak diperlukan saat pembaruan dikonfigurasi. Penambahan dan penghapusan daftar putar menggunakan sesi Pipe yang terbarukan; tidak diperlukan cookie `arl`. Token pengembang OAuth yang ada tetap merupakan pengganti lingkungan yang kompatibel.

<a id="amazon-music"></a>

### Amazon Music

Tidak diperlukan persetujuan pengembang untuk konektor default. Ia menggunakan rute GraphQL dan pembaruan token yang diautentikasi sama dengan pemutar web Amazon Music:

1. Masuk di <https://music.amazon.com> dan buka DevTools → Jaringan.
2. Muat ulang halaman, filter `config.json`, dan pilih permintaan masuk. (`pandaToken` juga berfungsi saat muncul, tetapi tidak diperlukan.)
3. Pilih Salin header permintaan atau Salin sebagai cURL, lalu tempelkan ke bidang pembaruan. Simpan header lengkap `User-Agent`, `Referer`, dan `Cookie` sehingga SongMirror dapat memutar ulang konteks browser yang sama.
4. Secara opsional, salin Respons `config.json` yang sudah masuk ke kolom bootstrap; SongMirror biasanya dapat mengambil konteks perangkat tersebut menggunakan sesi pembaruan.

SongMirror memperoleh nilai otorisasi `AmznMusic` yang sama secara lokal dan menyegarkannya melalui `music.amazon.com/pandaToken` sebelum habis masa berlakunya atau satu kali setelah penolakan autentikasi. Selama koneksi, Amazon menggunakan permintaan konfigurasi gaya browser saat ini ketika konteks perangkat diperlukan, memerlukan `/pandaToken` untuk membuat token akses, dan menolak koneksi jika Amazon mencabut cookie pembaruan Musik. Ini hanya menyimpan agen pengguna browser, bahasa, referensi Musik, daftar cookie autentikasi/sesi Amazon yang diizinkan, dan konteks perangkat klien Musik yang terbatas; analitik, eksperimen, konsol AWS, CSRF, dan data browser lain yang tidak terkait akan dibuang. Cookie yang disimpan tersebut masih bersifat sensitif, jadi jaga kerahasiaan SongMirror di LAN Anda. Logout, perubahan kata sandi/keamanan, atau pencabutan pihak Amazon masih memerlukan satu pengambilan baru.

Ini adalah antarmuka klien web pihak pertama yang tidak didukung dan Amazon dapat mengubahnya tanpa pemberitahuan. [Amazon Music Web API](https://developer.amazon.com/docs/music/API_web_overview.html) yang terdokumentasi masih dalam versi beta tertutup; kredensial mitra yang disetujui tetap menjadi cadangan opsional ketika dikonfigurasi melalui variabel lingkungan.

<a id="apple-music"></a>

### Apple Music

Tidak diperlukan akun Pengembang Apple — dua header dari `music.apple.com` sudah cukup. Buka <https://music.apple.com>, masuk, buka DevTools → Jaringan, putar lagu, filter untuk `amp-api.music.apple.com`, dan salin dari header permintaan apa pun:

- `authorization: Bearer eyJ...` → Bearer token (bagian `eyJ...`, tanpa `Bearer `)
- `media-user-token: ...` → Token pengguna (nilai penuh)

Wizard koneksi memungkinkan Anda menempelkan header mentah dan mem-parsing nilainya untuk Anda. Token beberapa bulan terakhir; rekatkan kembali di halaman Akun ketika masa berlakunya sudah habis.

ID Apple tanpa langganan Apple Music yang aktif masih dapat terhubung dalam mode Katalog saja. Dalam mode tersebut, tempelkan tautan daftar putar publik Apple Music di Transfer untuk menyalinnya ke layanan lain yang terhubung. Penjelajahan perpustakaan Apple, sinkronisasi terjadwal, dan penggunaan Apple Music sebagai tujuan transfer masih memerlukan hak istimewa CloudLibrary berbayar; SongMirror menunjukkan operasi tersebut sebagai tidak tersedia alih-alih menganggap kredensial katalog yang valid telah kedaluwarsa.

<a id="youtube-music"></a>

### YouTube Music

Berbicara dengan [YouTube Data API v3](https://developers.google.com/youtube/v3) resmi, yang token penyegarannya OAuth tahan lama dan bertahan saat dimulai ulang.

1. Di [Google Konsol awan](https://console.cloud.google.com), buat proyek, aktifkan YouTube Data API v3, dan buat klien OAuth jenis TV dan perangkat Input Terbatas.
2. Pada layar persetujuan OAuth, atur Status penerbitan → Dalam produksi (biarkan dalam "Pengujian", token akan habis masa berlakunya setelah 7 hari).
3. Di aplikasi, tempel ID klien + rahasia dan lengkapi kode perangkat di layar.

> Kuota: Data API memungkinkan 10.000 unit/hari (biaya pencarian 100, tambah/hapus 50). Pemeliharaan dalam kondisi tunak itu murah; simpanan pertama yang besar dapat mencapai batasnya dan dilanjutkan keesokan harinya.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ tanpa antarmuka grafis CLI

Lebih suka `.env` + cron / Task Scheduler? Mesin yang sama berjalan tanpa antarmuka grafis.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Bendera yang berguna:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Vars env kunci (lihat `.env.example`): kredensial untuk penyedia mana pun yang Anda gunakan, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES`, dan `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Perlindungan keamanan

Penghapusan bersifat merusak, sehingga dijaga:

- simulasi adalah defaultnya — tidak ada yang berubah tanpa `--execute` (atau tindakan sinkronisasi nyata UI).
- Jika sumber mengembalikan 0 lagu untuk daftar putar yang targetnya tampilkan sebagai tidak kosong, penghapusan akan dilewati (kegagalan sementara API tidak dapat mengosongkan daftar putar).
- **Penghapusan dinonaktifkan secara bawaan** — `MAX_REMOVALS=0` menahan semua penghapusan; tindakan tersebut dicatat, tetapi tidak pernah dijalankan. Karena itu, penarikan lagu akibat lisensi di satu platform tidak memicu penghapusan berantai di platform lain. Aktifkan **Sinkronkan penghapusan lagu** pada setiap sinkronisasi atau atur `MAX_REMOVALS`. Bahkan setelah diaktifkan, jika jumlah penghapusan tertunda dalam satu proses melebihi batas, semuanya dilewati dan dicatat.
- `MAX_ADDS` membatasi setiap penulisan yang menghasilkan stempel waktu dalam pass sinkronisasi, termasuk perbaikan kronologi. Jika kecocokan yang dipulihkan lebih lama memerlukan pemutaran ulang sufiks yang lebih besar daripada batas yang diperbolehkan, SongMirror menundanya ke lintasan berikutnya daripada membuatnya tampak terbaru atau menyebabkan ledakan penyedia raksasa. Transfer satu kali tidak memiliki lintasan berikutnya, sehingga tidak pernah ditangguhkan: transfer tersebut menyalin setiap trek yang diminta, menambahkan dalam urutan sumber kecuali Anda mengaktifkan "Pertahankan pesanan yang Baru Ditambahkan" untuk transfer tersebut, yang menghabiskan berapa pun biaya perbaikannya.
- Perbaikan kronologi melakukan salinan duplikat sebelum menghentikan yang asli. Pada layanan yang penghapusannya mengambil setiap salinan lagu, jumlah penjaganya harus benar, jadi Apple Music membaca ulang hingga salinan bertahap terlihat dan menolak menghentikan apa pun terhadap pembacaan yang masih tertinggal dari penulisannya sendiri. Deezer melewatkan perbaikan sepenuhnya dan selalu menambahkan: ia juga tidak memiliki sisipan posisi, jadi memutar ulang pesanan yang tidak dapat diungkapkan tidak sebanding dengan risikonya terhadap tujuan. Formulir transfer berwarna abu-abu, urutannya beralih di luar sana dan menjelaskan alasannya.
- Perlindungan kerugian bersih — jalur sisi target yang menyerupai jalur sumber yang tidak cocok dengan layanan tersebut ditahan, tidak dihapus.
- Kegagalan autentikasi penyedia apa pun akan segera membatalkan pass penyedia tersebut — tidak ada penghapusan sebagian pada token yang kedaluwarsa.
- Pekerjaan penggabungan harus menyelesaikan setiap sumber konstituen yang dibaca sebelum dihapus dari tujuannya; kekuatan snapshot sumber sebagian/gagal yang diteruskan ke perilaku hanya penambahan.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Caching & arsip lagu

Segala sesuatu yang dapat diselesaikan di-cache sehingga lintasan kondisi-mapan hampir seketika: cache penyelesaian per layanan (ISRC + pencarian, termasuk kesalahan), cache daftar lagu dengan kunci `snapshot_id`, tautan pengidentifikasi tepat di SQLite, dan lompatan snapshot per pasangan (`unchanged since last clean sync`).

Setiap pass juga mengarsipkan metadata dari setiap trek yang dilihatnya ke dalam `song_cache.db` — file SQLite yang terus bertambah. Lagu yang dihapus tetap diarsipkan dengan nama, artis, album, durasi, ISRC, cuplikan mentah JSON, dan stempel waktu pertama/terakhir dilihat:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Selesaikan pemetaan

Setiap layanan menyimpan cache penyelesaiannya sendiri, memetakan kunci `title|artist` yang dinormalisasi ke id katalog yang cocok dengannya
layanan itu. Sebuah kecocokan digunakan kembali selamanya, begitu pula hasil "tidak ada kecocokan", yang membuat sebuah trek gagal
untuk mencocokkan sekali tetap tak tertandingi pada setiap operan selanjutnya.

Halaman Pemetaan di UI web memperlihatkan cache tersebut secara langsung, per layanan:

- cari seluruh cache berdasarkan judul, artis, atau id yang diselesaikan
- memfilter ke entri yang diatur secara manual (kecocokan yang Anda pilih di editor konflik transfer) atau ke entri yang tidak cocok
- perbaiki id yang salah dengan menempelkan tautan jalur yang benar, atau hapus pemetaan agar lintasan berikutnya mencarinya lagi
- menghapus setiap entri "tidak cocok" untuk layanan dalam satu tindakan, sehingga kumpulan pencarian yang gagal dapat dicoba lagi

Ketika kesalahan yang telah diselesaikan teratasi nanti, cukup menambahkannya akan membuat lagu lama tampak terbaru. Untuk daftar putar
tujuan, SongMirror malah memutar ulang lagu itu dan akhiran baru yang sudah ada, terlama hingga terbaru, lalu menghapus
salinan yang lebih tua. Penyedia tidak mengizinkan klien untuk memulihkan stempel waktu asli, tetapi ini mempertahankan stempel waktu relatif mereka
Pesanan baru ditambahkan. Koleksi asli yang disukai/disukai tetap menjadi milik keanggotaan saja dan tidak pernah diputar ulang.

Pengeditan ditolak dengan pesan yang jelas saat sinkronisasi berjalan, karena sebuah pass menyimpan cache di memorinya
seluruh durasi dan akan menimpanya setelah selesai.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Tata letak proyek

Entri CLI: `uv run main.py` (shim tipis) atau `python -m songmirror`. Entri web: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Menambahkan layanan lain: subkelas `MirrorTarget`, implementasikan metode ~8, tambahkan pembuatnya ke `engine/targets`' `_REGISTRY` dan kelasnya ke `_CLASSES`, dan tambahkan `Connector` yang cocok di bawah `services/accounts`. Semua rekonsiliasi — perbedaan, pengurutan, Perlindungan keamanan, logging, lompatan snapshot — diwariskan.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Pemecahan masalah

- `Missing required environment variable` — isi `.env` (CLI) atau sambungkan layanan di UI.
- TIDAL laporan `Expired` — keluar dan masuk kembali di `listen.tidal.com`, lalu tempel `client_id` dari payload permintaan `oauth2/token` dan Respon lengkapnya JSON di Akun. Permintaan OpenAPI yang disalin hanya memiliki Bearer yang berumur pendek dan tidak dapat diperpanjang.
- TIDAL laporan HTTP 429 — ini adalah batas tarif sementara, bukan masa masuk yang sudah habis masa berlakunya. SongMirror menghormati penundaan percobaan ulang penyedia dan menyimpan pemeriksaan kondisi akun dalam cache alih-alih memeriksa API berulang kali.
- Qobuz atau laporan Apple `Expired` / `401` / `403` — sesi yang ditempel ini tidak memiliki rahasia terbarukan; menangkap permintaan masuk atau token baru di Akun.
- TIDAL menyatakan bahwa token tidak memiliki akses jalur yang disukai — ambil respons token pemutar web baru yang masuk yang membawa `r_usr` dan `w_usr`.
- Deezer pembaruan gagal — ambil permintaan `auth.deezer.com/login/renew` baru (atau cookie `refresh-token`-nya). Pipa saat ini Bearer saja hanyalah bootstrap sementara.
- Amazon Music perpanjangan gagal — ambil permintaan masuk baru `POST /config.json?skipToken=false` dengan header lengkap `User-Agent`, `Referer`, dan `Cookie`. Respons JSON bersifat opsional.
- YouTube Music mode browser berakhir — ekspor header permintaan browser baru. Untuk penyiapan tanpa pengawasan yang paling tahan lama, gunakan Data API OAuth dengan layar persetujuan dalam produksi.
- Spotify laporan Kedaluwarsa — masuk lagi di `open.spotify.com` dan tempelkan cookie `sp_dc` baru di Akun.
- Daftar putar tidak disinkronkan — pastikan daftar putar tersebut ada dalam cakupan daftar putar sinkronisasi dan ada di sumbernya (target dibuat secara otomatis dengan pass nyata).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Lisensi

Hak Cipta © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Proyek ini [MIT](../../LICENSE) berlisensi.

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
