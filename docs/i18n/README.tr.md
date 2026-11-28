<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**Çalma listelerin eşzamanlı kalsın.**<br>
Zamanlanmış eşitlemeyi kendi sunucunda çalıştır, bir çalma listesini tek seferlik kopyala veya Jellyfin için yerel bir müzik kopyası tut. Ücretsiz ve açık kaynaklı.

[![Docker ile çalıştır][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Ko-fi’de destek ol][kofi-badge]][kofi-link]

[Rehberli kurulum](#guided-install) · [Desteklenen hizmetler](#supported-services) · [Özellikler](#features) · [Ekran görüntüleri](guide.tr.md#screenshots) · [SongMirror projesini destekle](#support) · [Web sitesi][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.tr.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — Genel bakış · Çalma listeleri" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![GitHub’da yıldız ver][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 Hızlı Başlangıç

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

**http://localhost:8888** adresini açın. **Hesaplar** bölümünde kullandığınız hizmetleri bağlayın. Bir kez kopyalamak için **Aktarımlar**, listeleri zamanlamayla güncel tutmak için **Senkronizasyon** seçeneğini kullanın.

<a id="guided-install"></a>

### Rehberli kurulum

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [Kullanıcı kılavuzu](guide.tr.md#guided-install)

<a id="app-language"></a>

### Uygulama dili

Dili **Ayarlar → Genel → Dil** bölümünden değiştirin. Tarayıcının dilini kullanmak için **Otomatik (tarayıcı)** ayarını seçin.

<a id="supported-services"></a>

## Desteklenen hizmetler

**Hesaplar → Hesap ekle** bölümünü açıp bir hizmet arayın.

| Hizmet | Eşitleme ve aktarım desteği |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | Çalma listeleri ve favoriler |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | Çalma listeleri |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | Sunucu çalma listeleri |
| [Last.fm](https://www.last.fm/) | Sevilen ve en çok dinlenen parçalar ile dinleme geçmişi. Sevilen parçaları düzenlemek için yetki ver. |
| [ListenBrainz](https://listenbrainz.org/) | Çalma listeleri ve sevilen kayıtlar. Kullanıcı belirteci yazma erişimi sağlar. |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | Herkese açık çalma listesi bağlantılarını veya oturum açtığınız hesabın kitaplığını kaynak olarak kullanın. |

[Her servisi bağlama](guide.tr.md#connecting-each-service) · [çalma listesi bağdaştırıcısı kılavuzuna](../music-service-adapters.md)

<a id="features"></a>

## ✨ Özellikler

- [Tek yönlü, çift yönlü ve çok kaynaklı senkronizasyon](guide.tr.md#how-it-works)
- [Tek seferlik çalma listesi aktarımı](guide.tr.md#features) · [Geçmiş ve kurtarma](../transfer-history.md)
- [Çalma listesi meta veri yedeklemeleri](guide.tr.md#playlist-metadata-backups) · [Kaydedilen albümlerin aktarımı](../saved-albums.md) · [Yerel indirme aynası (Jellyfin)](guide.tr.md#local-download-mirror-jellyfin)

[Kullanıcı kılavuzu](guide.tr.md)

<a id="support"></a>

## SongMirror projesini destekle

Desteğin, müzik hizmetlerinde bakım ve test çalışmalarını finanse etmeye yardımcı olur.

[![Ko-fi’de destek ol][kofi-badge]][kofi-link]
[![GitHub’da sponsor ol][sponsor-badge]][sponsor-link]

[GitHub’da yıldız ver][stars-link] · [Başa dön](#readme-top)

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
