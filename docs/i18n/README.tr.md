<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music ve YouTube Music için kendi kendine barındırılan, kesintisiz çalışan çalma listesi senkronizasyonu — artı Jellyfin ile uyumlu yerel bir çevrimdışı ses kopyası.<br/>
Soundiiz, TuneMyMusic ve FreeYourMusic servislerine ücretsiz, açık kaynaklı, tamamen kendi sunucunuzda çalışan ve kontrolü sizde olan bir alternatif.

**Tek yönlü, çok kaynaklı birleştirme, yetkili grup veya tam çift yönlü (N yönlü) senkronizasyon · tek seferlik çalma listesi aktarımları · ISRC düzeyinde kesin eşleştirme · hepsi tarayıcınızdan**

[Hızlı Başlangıç](#quick-start) · [Özellikler](#features) · [Ekran görüntüleri](#screenshots) · [Docker](#always-running-docker) · [Nasıl çalışır?](#how-it-works) · [Hata bildir][github-issues-link] · [Özellik iste][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Bu projeyi paylaş**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Bir kez kurun — düzenlediğiniz her çalma listesi, eklenme tarihine göre tüm servislerde senkron kalsın.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror demo — logo tanıtımı, gösterge paneli, tek yönlü ve çift yönlü senkronizasyon kurulumu, canlı çalma listesi aktarımları ve yedi müzik servisinde ISRC ile kesin eşleştirme" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">1080p versiyonunu izleyin</a></sup>

</div>

> [!NOTE]
> **Web uygulaması + arayüzsüz CLI, tek bir motor.** Servisleri bağlamak, senkronizasyon kurmak ve çalma listelerini aktarmak için tarayıcı arayüzünü kullanın veya doğrudan `.env` + cron yaklaşımıyla çalıştırın. Her ikisi de aynı senkronizasyon çekirdeğini kullanır.

<details>
<summary><kbd>İçindekiler</kbd></summary>

#### İçindekiler

- [✨ Özellikler](#features)
- [📸 Ekran görüntüleri](#screenshots)
- [🚀 Hızlı Başlangıç](#quick-start)
  - [Uygulama dili](#app-language)
- [🐳 Kesintisiz çalışma: Docker](#always-running-docker)
- [⚙️ Nasıl çalışır?](#how-it-works)
  - [Eşleştirme](#matching)
  - [Çok kaynaklı birleştirme senkronizasyonu](#multi-source-merge-sync)
  - [Yetkili gruplar](#authoritative-groups)
  - [Çift yönlü (N yönlü) senkronizasyon](#bidirectional-n-way-sync)
- [📦 Çalma listesi meta veri yedeklemeleri](#playlist-metadata-backups)
- [💿 Yerel indirme aynası (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Her servisi bağlama](#connecting-each-service)
  - [Kimlik bilgilerinin yenilenmesi](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
  - [Last.fm](#lastfm)
- [🖥️ Arayüzsüz CLI (Headless)](#headless-cli)
- [🛡️ Güvenlik önlemleri](#safety-rails)
- [🗃️ Önbellek ve şarkı arşivi](#caching-song-archive)
  - [Eşlemeleri çözümle](#resolve-mappings)
- [🧱 Proje düzeni](#project-layout)
- [🩺 Sorun giderme](#troubleshooting)
- [📄 Lisans](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Özellikler

SongMirror; manuel olarak tek tek şarkı eklemeye, kopyalamaya ya da kitaplığınızı elinde tutan ücretli bulut servislerine gerek kalmadan çalma listelerinizi her yerde birebir aynı tutar. **Platformlar arası, kendi sunucunuzda barındırılabilir ve açık kaynaklıdır**.

- 🔁 **Gerçek yansıtma, yalnızca ekleme değil** — hem eklemeleri hem de silinenleri yansıtır. Güvenilir bir ana kaynak seçin (varsayılan olarak Spotify), diğer tüm servisler onu takip etsin.
- ⇆ **Yetkili gruplar** — iki veya daha fazla servisi ana kaynak kabul edin (örneğin Spotify + Apple Music), seçilen diğer tüm servisler yalnızca hedef yansısı olarak kalsın.
- ⇄ **Çift yönlü N yönlü senkronizasyon** — bağlı servislerin herhangi birinde yapılan ekleme veya silme işlemi, silme korumaları sayesinde sonsuz döngüye girmeden diğer tüm servislere yansıtılır.
- ⇉ **Çok kaynaklı birleştirme senkronizasyonu** — herkese açık listeleri kütüphanenize kaydetmenize gerek kalmadan, hem kendi listelerinizin hem de açık liste bağlantılarının tekilleştirilmiş birleşimini tek bir hedefe senkronize edin.
- ♥ **Beğenilen ve favori parçalar** — her servisin yerleşik beğenilen koleksiyonunu yedi müzik sağlayıcının tamamında, hedefin kendi favorileriyle veya yeni adlandırılmış bir çalma listesiyle senkronize edin.
- 🎯 **ISRC ile doğru eşleştirme** — mevcut olduğunda tam kayıt kimliğiyle, olmadığında ise Unicode destekli bulanık başlık/sanatçı/süre eşleştirmesiyle çalışır (düet sanatçı farkları, "- 2015 Remaster" ekleri, Latin dışı alfabeler ve yalnızca video olan yüklemelerin tamamı desteklenir).
- 🎛️ **Birden fazla adlandırılmış senkronizasyon** — her birinin kendi servisleri, çalma listeleri, zaman planı ve güvenlik sınırları olan dilediğiniz sayıda bağımsız senkronizasyon kurun.
- ↪️ **tek seferlik aktarımlar** — canlı ilerleme çubuğuyla herhangi bir çalma listesini bir servisten diğerine kopyalayın; kopyalama sırasında duraklatın, devam ettirin veya durdurun ve eşleşmeyen parçaları elinizle çözümleyin.
- 🕒 **Parçaları ekleyin veya parça sırasını koruyun** — kopyalanan şarkılar varsayılan olarak hedefin sonuna hızlıca eklenir. Kaynaktaki eklenme tarihi sırasını korumak için Son Eklenenleri Koru sırasını açarak şarkıların en eski yeni parçadan sonra yeniden yazılmasını sağlayın.
- 🔗 **Bağlantıdan aktarma** — bağlı herhangi bir servisteki herkese açık bir çalma listesi URL'sini yapıştırarak doğrudan kopyalayın. Listeyi önceden kaydetmeniz veya takip etmeniz gerekmez.
- 🌐 **Takip edilen çalma listeleri** — yalnızca kendi oluşturduğunuz değil, takip ettiğiniz ancak sahibi olmadığınız çalma listelerini de senkronize edin ve aktarın.
- 📦 **Zamanlanmış meta veri yedeklemeleri** — bir hesabın çalma listesi kitaplığının tamamını JSON/XML formatında, saklama sınırları ve başarı/başarısızlık geçmişiyle kalıcı uygulama verileri altında düzenli olarak arşivleyin. Tek seferlik indirmeler ve içe aktarmaya hazır Soundiiz JSON da kullanılabilir.
- 📻 **Last.fm**: Loved Tracks, Top Tracks (altı dönem) ve Recent Scrobbles koleksiyonlarınızı bağlı herhangi bir hizmete gönderin; hesabı yetkilendirdikten sonra diğer hizmetlerdeki beğenilen parçaları **Last.fm tarafına** geri taşıyın. Çalma listesi yoktur, dolayısıyla asla çalma listesi hedefi olmaz.
- 💿 **Yerel indirme aynası** — çevrimdışı ses dosyalarını, **Jellyfin'in** `AlbumArtist/Album` klasör yapısında, kapak resimleri ve otomatik güncellenen `.m3u8` dosyasıyla çalma listesi başına bir klasör halinde saklayın. Mevcut bir müzik kitaplığına yönlendirdiğinizde eşleşen parçalar **özgün kaliteleriyle** kopyalanır (bir FLAC yine FLAC kalır) ve indirmeler yalnızca eksikleri tamamlar.
- 🛡️ **Güvenlik önlemleri** — varsayılan olarak simülasyon, geçiş başına ekleme/kaldırma sınırları, net kayıp koruması, boş anlık görüntü koruması ve belirteçlerin süresi dolduğunda yazmadan güvenle iptal etme.
- 🗃️ **Sürekli büyüyen şarkı arşivi** — karşılaşılan her parça yerel bir SQLite veritabanına kaydedilir (isim, sanatçı, albüm, ISRC, ham meta veriler, ilk/son görülme).
- 🧭 **Düzenlenebilir eşleşme geçmişi** — servis başına önbelleğe alınmış tüm parça eşleşmelerini (ve aksi halde sonsuza kadar eşleşmeyecek olan "eşleşme yok" sonuçlarını) Eşlemeler sayfasından inceleyin, düzeltin ve silin.
- 🐳 **Her yerde çalışır** — tarayıcı uygulaması için bir `docker compose up -d` veya doğrudan CLI + cron / Task Scheduler.

> [!IMPORTANT]
> **Kendi sunucunuzda barındırılır ve tasarım gereği gizlilik odaklıdır.** Dinleme verileriniz ve kimlik bilgileriniz makinenizden asla ayrılmaz. Web kullanıcı arayüzünün **giriş şifresi yoktur**; bu nedenle onu yerel ağınıza (LAN) bağlayın ve internete port yönlendirmesi yapmayın.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Ekran görüntüleri

<div align="center">

**Her kitaplık için bir kontrol paneli — senkronizasyon durumu, işler, canlı etkinlik ve servis durumu**

<img src="../../.github/assets/dashboard.png" alt="SongMirror Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music için senkronizasyon durumunu, yapılandırılmış işleri, canlı etkinliği ve sağlığı gösteren kontrol paneli, YouTube Music ve Jellyfin" width="82%">

**Kısa bir sihirbazla istediğiniz sayıda senkronizasyonu (tek yönlü, çok kaynaklı birleştirme, yetkili grup veya çift yönlü) ayarlayın**

<img src="../../.github/assets/sync-wizard.png" alt="SongMirror kurulum sihirbazı, Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music ve YouTube Music arasında çift yönlü senkronizasyon için hizmetleri seçiyor" width="82%">

**Tarayıcınızdaki her servisi bağlayın; tek tıklamayla OAuth, yönlendirmeli belirteç yapıştırma veya API anahtarı**

<img src="../../.github/assets/accounts.png" alt="Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music ve Jellyfin'yi bağlamak için Hesaplar sayfası" width="82%">

**Servisler genelinde çalma listelerine göz atın ve eşleştirin**

<img src="../../.github/assets/playlists.png" alt="Kapak resmi ve parça sayılarıyla birlikte bağlı hizmetlerdeki çalma listelerine göz atma" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Hızlı Başlangıç

Bunu çalıştırmanın en hızlı yolu Docker'dır — Compose yayınlanan imajı çeker, web arayüzünü sunar ve senkronizasyonlarınızı belirlenen plana göre yürütür.

Otomatik yeniden başlatmalarla kalıcı bir kurulum için:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Veya depoyu klonlamadan genel GHCR görüntüsünü doğrudan deneyin:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Ardından **`http://localhost:8888`** adresini açın ve servislerinizi tarayıcıdan bağlayın. Compose kurulumunun başlaması için **`.env` dosyasına gerek yoktur**; her şey arayüzden yapılandırılır ve `./data` dizinine kaydedilir.

Doğrudan `docker run` seçeneği tek kullanımlıktır: `docker stop songmirror` komutu konteyneri ve yapılandırmasını kaldırır. Kalıcı kimlik bilgileri, önbellekler ve indirmelerle kalıcı bir kurulum için Compose kullanın veya etiketler ve özet sabitleme için **[konteyner görseli kılavuzu](../docker-image.md)** bölümüne bakın.

Docker olmadan çalıştırmayı mı tercih edersiniz?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> [`uv`](https://docs.astral.sh/uv/) (Python 3.13+) gerektirir. Yerel indirme aynası için ayrıca `uv tool install spotdl` komutunu çalıştırın ve PATH üzerinde `ffmpeg` bulundurun.

<a id="app-language"></a>

### Uygulama dili

SongMirror İngilizce, Arapça, Türkçe, İspanyolca, Basitleştirilmiş Çince, Fransızca, Portekizce, Almanca, Japonca, Hintçe, Bengalce, Endonezce, Korece, İtalyanca ve Vietnamca'yı destekler. İlk açılışta, bölgesel varyantlar da dahil olmak üzere tarayıcınızın dil tercihleri sırayla değerlendirilir ve desteklenen ilk dil kullanılır. Hiçbiri desteklenmiyorsa İngilizce kullanılır. Dili **Ayarlar → Genel → Dil** bölümünden değiştirebilirsiniz; seçiminiz bu tarayıcıda saklanır ve sayfa yeniden yüklendiğinde korunur. Tarayıcı tercihlerini yeniden izlemek için **Otomatik (tarayıcı)** seçeneğini seçin. Arapça arayüz sağdan sola yazılır. Çalma listesi, sanatçı ve sağlayıcı adları, kimlik bilgileri ve tanılama günlükleri özgün değerlerini korur.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Kesintisiz çalışma: Docker

Docker konteyneri önerilen dağıtım yöntemidir: web arayüzünü sunar, senkronizasyonlarınızı kendi zaman planlarına göre yürütür ve ana makineyle birlikte otomatik olarak yeniden başlar. Compose, **`ghcr.io/ahnafnafee/songmirror:latest`** imajını çeker, **`songmirror`** adıyla çalıştırır ve tüm kimlik doğrulama ile önbellekleri `./data` dizininde saklar.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Güncellemek için `docker compose up -d --pull always` komutunu çalıştırın. Bunun yerine mevcut yerel kodu derlemek için `docker compose up -d --build` komutunu çalıştırın. Etiketler, özet sabitleme, doğrudan çekme, doğrulama, güncellemeler ve geri alma için **[konteyner görseli kılavuzu](../docker-image.md)** bölümüne bakın.

**Başlamak için `.env` gerekmez** — her şey tarayıcıda yapılandırılır ve `./data` altına kaydedilir. OAuth, ortak belirteci ve API anahtarı kurulumunun tümü Hesaplar sayfasındadır; her sihirbaz servise özel önkoşulları ve tam geri arama URI'sini açıklar. Daha sonra senkronizasyonlarınızı Senkronizasyon sayfasında oluşturun.

SongMirror'ı başka bir bilgisayardan açmak `http://<server>:8888` adresinde çalışır. Varsayılan Spotify bağlantısı, yapıştırılan `sp_dc` web oturumunu kullanır, dolayısıyla geliştirici uygulamasına veya geri arama URL'sine ihtiyaç duymaz. Kasıtlı olarak eski geliştirici uygulaması OAuth yöntemini Docker arkasında veya ters proxy ile kullanıyorsanız, tarayıcı tarafından görülebilen temel URL'yi `.env` olarak ayarlayın:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror daha sonra `https://music.example.com/oauth/spotify/callback` adresini kullanacaktır; Spotify uygulama kontrol paneline tam olarak bu URI'yi kaydedin ve kapsayıcıyı `docker compose up -d --force-recreate` ile yeniden oluşturun. Ters proxy temel yolu da desteklenir (örneğin, `https://example.com/songmirror`). [Spotify gerektirir HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) geridöngü olmayan her yönlendirme için; düz HTTP yalnızca `127.0.0.1` gibi gerçek geridöngü adresleriyle kabul edilir, LAN IP veya `localhost` ile kabul edilmez.

| | |
| --- | --- |
| **İmaj** | `ghcr.io/ahnafnafee/songmirror:latest`, AMD64 ve ARM64'yi destekler. Her yapı aynı zamanda işleme özel bir `sha-...` etiketiyle yayınlanır; `v1.2.3` gibi Git etiketleri ayrıca `1.2.3`, `1.2` ve `1` yayınlar. Değişmez bir özeti sabitlemek için [konteyner görseli kılavuzu](../docker-image.md) bölümüne bakın. |
| **Port** | Kullanıcı arayüzü ana makinede **8888** portunda yayınlanır (`8888:8080`'deki `docker-compose.yml` eşlemesi; çakışıyorsa ana bilgisayar tarafını değiştirin). **Yalnızca LAN** — onu internete port olarak iletmeyin; Kullanıcı arayüzünün henüz kimlik doğrulaması yok. |
| **Kalıcılık** | `./data` kimlik bilgilerini, belirteçleri, önbellekleri, şarkı arşivini ve planlanmış çalma listesi anlık görüntülerini `playlist_backups/` altında tutar. Yeniden yapılandırmalarda kurulumunuzu ve arşivlerinizi korumak için yedekleyin. |
| **İndirmeler** | `DOWNLOAD_DIR`'yi (`.env`'de veya kabuğunuzda) ana müzik dizininize (örneğin `F:\Torrent\Music`) ayarlayın; compose bağlama onu `/music`'ye bağlar. Docker'den `JELLYFIN_URL`'yi `http://host.docker.internal:8096`'ye ayarlayın. |
| **Süresi dolmuş oturumlar** | Yenilenebilir oturumlar bir sonraki planlı veya manuel geçişte kurtarılır. TIDAL web oynatıcı oturumları, yakalanan yenileme belirtecinden yenilenir; Qobuz ve Apple Music jetonları reddedildiklerinde yine de yeniden yapıştırılmalıdır. Yeniden başlatmaya gerek yoktur. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Nasıl çalışır?

Kaynakta bulunan, seçilen her çalma listesi adı için her geçiş:

1. Kaynak çalma listesinin anlık görüntüsünü alın (parçalar, ISRC'ler, eklenme tarihleri).
2. İlgili servisin hesap tarafından yetkilendirilen çalma listesi API aracılığıyla seçilen, bağlı her hedefteki aynı adlı çalma listesini eş zamanlı olarak uzlaştırın.
3. Eksik parçalar çözümlendi (önbelleğe alınmış bağlantılar → ISRC → puanlı arama) ve en eski-önce eklendi; Kaynaktan çıkan izler korumaların arkasında kaldırılır.
4. İsteğe bağlı olarak, [spotDL](https://github.com/spotDL/spotify-downloader) her çalma listesi için yerel bir ses klasörünü senkronize eder.

Varsayılan doğruluk kaynağı Spotify'dir, ancak **tek yönlü mod sağlayıcıdan bağımsızdır** — bunun yerine bağlı herhangi bir çalma listesi eşi kaynak olabilir.

<a id="matching"></a>

### Eşleştirme

Çapraz servis araçlarının kullandığı hiyerarşinin aynısı ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): **tam tanımlayıcı → arama → bulanık puan**.

1. **Önbelleğe alınmış bağlantı** — bir kaynak parça, hedefin katalog kimliği/video kimliğiyle eşleştirildiğinde, bu bağlantı depolanır ve yeniden kullanılır (başlık kaymasından etkilenmez).
2. **ISRC** — servisin gösterdiği yerde tam kayıt kimliği.
3. **Puanlı arama** — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, hem ham hem de **romanlaştırılmış** ([anyascii](https://github.com/anyascii/anyascii)) başlık ve sanatçı üzerinde, süreye göre sabitlenmiş. Bu, sabit kodlama olmadan şunları yönetir:
   - **Çok sanatçılı jenerikler** — bir servis her özelliği listeler, diğeri birincil özellikleri listeler (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - **Başlık dekorasyonu** — `(feat. …)`, `- 2015 Remaster`, `(From "…")`, ekstra "Resmi Müzik Videosu" son ekleri.
   - **Harf çevirisi** — Kiril / Bengalce / Yunanca / Arapça (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - **Yalnızca video parçaları** — YouTube arama, YT'de yalnızca yükleme olarak yayınlanan bağımsız/OST parçaları için `videos` filtresine geri döner.

Süre çapası daha gevşek başlık eşleşmesinin kilidini açar, bu nedenle uzunluğu farklı olduğunda farklı bir versiyon (`Runaway - Piano Version`) veya yanlış sanatçının cover'ı kabul edilmez. Kesin eşleşmesi olmayan parçalar raporlanır ve atlanır.

<a id="multi-source-merge-sync"></a>

### Çok kaynaklı birleştirme senkronizasyonu

Bir **Kaynakları birleştir** görevi, bir veya daha fazla açık çalma listesini seçilen tek bir hedefte birleştirir. Her kaynak, bağlı bir hesabın kitaplığından veya yapıştırılan herkese açık bir servis URL'sinden gelebilir; URL servise ve çalma listesi kimliğine yalnızca bir kez çözümlenir; böylece çalma listesini kaydetmeniz veya takip etmeniz gerekmez ve planlı çalıştırmalar keyfi bir URL'yi tekrar tekrar sorgulamaz.

- **Tek üyelik birleşimi** — hedef uzlaştırılmadan önce tüm bileşenler okunur. Paylaşılan ISRC'ler tek bir kayıttır; ISRC olmadan, tam/muhafazakar başlık, sanatçı, versiyon ve süre kanıtı çakışmaları tekilleştirir.
- **Deterministik sıra** — önce kaynak tanımlayıcı önceliği, ardından her kaynak çalma listesi tarafından döndürülen sıra. İlk oluşum, hedef konumun sahibidir ve meta verileri görüntüler; daha sonraki kopyalar yalnızca eksik kimlik meta verilerini zenginleştirir.
- **Birlik açısından güvenli kaldırmalar** — bir hedef şarkı yalnızca tam bir geçişin tüm kurucu kaynaklarda bulunmadığını tespit ettiğinde kaldırılabilir. Başarısız, kesilmiş, hatalı biçimlendirilmiş, kullanılamayan veya bilinemeyecek kadar boş bir kaynak, bu geçişe ilişkin tüm kaldırma işlemlerini devre dışı bırakırken, okunabilir kaynaklardan güvenli eklemeler devam edebilir.
- **Varsayılan olarak yalnızca ekle** — yalnızca hedefteki tüm parçaları korumak için Her kaynakta olmayan parçaları kaldır seçeneğini kapalı bırakın. Açıldığında, tam okuma koruması geçtikten sonra normal geçiş başına çıkarma kapağı devreye girer.

Birleştirme işleri şu anda tek bir sağlayıcı oynatma listesini hedefliyor; ayrı Spotify-led yerel indirme/Jellyfin aynası toplu bir iş için mevcut değildir.

<a id="authoritative-groups"></a>

### Yetkili gruplar

Aynı mantıksal çalma listesini iki veya daha fazla serviste aktif olarak düzenliyorsanız ve seçilen diğer tüm servislerin bunları takip etmesini istiyorsanız bir **yetkili grup** kullanın. Tipik bir kurulumda **yetkililer Spotify + Apple Music** olurken, hedef aynaları TIDAL, Qobuz, Deezer, Amazon Music ve YouTube Music şeklindedir.

- **Üyelik yalnızca yetkililerden gelir** — Spotify veya Apple Music'ye eklenen bir parça diğer otoriteye ve her aynaya yayılır. Yalnızca aynaya eklenen iz drifttir; asla yetkililere geri aktarılmaz.
- **Tek sipariş yetkilisi** — Hangi yetkilinin çalma listesi adlarını ve eklemelerin sırasını sağlayacağını seçin. Diğer yetkililer hâlâ üyelik değişikliklerine katkıda bulunuyor.
- **Onaylanan kaldırma işlemleri her iki otoriteden de yayılır** — herhangi bir şeyin silinebilmesi için, ardışık iki tam okumada bir yokluğun görünmesi gerekir. Eş zamanlı olarak otorite tarafında yapılan bir ekleme, kaldırma işlemine karşı galip gelir.
- **Aynalar asla oy alamaz** — bir aynadan bir parçanın silinmesi, o aynayı onarır; Spotify veya Apple Music'deki parçayı silmez.
- **Güvenli ilk geçiş** — her yetki kümesinin kendi temel çizgisi vardır. İlk başarılı geçişi eksik parçaları ekleyebilir, ancak daha sonraki bir geçiş temel çizginin stabil olduğunu kanıtlayana kadar tüm kaldırma işlemlerini sürdürür.
- **Başarısız kapatma** — herhangi bir otoritenin bağlantısı kesilirse, okunamazsa veya çalma listesi açılamıyor/oluşturulamıyorsa, sessizce daha az sayıda otoriteye geri dönmek yerine bu mantıksal çalma listesi atlanır.

Silme işlemlerinin açıkça etkinleştirilmesi gerekir ve bu işlemler bir üst sınıra tabidir. Aynalardaki fazla parçaların kaldırılarak yetkili kaynak kümesiyle eşleşmesini istiyorsanız iş için **Silinen şarkıları eşitle** seçeneğini etkinleştirin veya grafik arayüz olmadan çalıştırırken `MAX_REMOVALS` değerini ayarlayın.

<a id="bidirectional-n-way-sync"></a>

### Çift yönlü (N yönlü) senkronizasyon

Varsayılan olarak tek bir sağlayıcı gerçeğin kaynağıdır ve düzenlemeler tek yönlü olarak akar. **N-way modunda** seçilen her sağlayıcı bir eştir: herhangi birine bir parça eklenir veya kaldırılır ve değişiklik diğerlerine de yayılır.

Çift yönlü senkronizasyon durum bilgisi olmadan imkansızdır, bu nedenle her mantıksal çalma listesinin kanonik üyeliğinin her temiz geçişten sonra anlık görüntüsü alınır. Her geçiş, her sağlayıcıyı bu anlık görüntüye göre farklılaştırır, değişiklikleri birleştirir ve herkesi sonuç konusunda uzlaştırır:

- **Yankısız** — yayılan bir ekleme, anlık görüntünün parçası haline gelir, böylece asla geri dönmez.
- Çatışma durumunda **ek kazançlar** — bir şarkıyı kaybetmek, fazladan bir şarkıyı tutmaktan daha kötüdür.
- **Okuma-çökme koruması** — eğer bir sağlayıcı aniden taban çizgisinden çok daha az parça okursa (geçici bir API hıçkırık), bu geçiş atlanır, böylece hatalı bir okuma toplu silmeyi basamaklandıramaz.
- **Tek yönlü güvenlik önlemlerinin aynısı** — geçiş başına `MAX_ADDS` / `MAX_REMOVALS` sınırlar ve net kayıp koruması her yazma tarafında geçerlidir.
- **Silme işlemleri isteğe bağlıdır** — `MAX_REMOVALS` varsayılan olarak 0 olduğundan bir sağlayıcıdan kaybolan parça, orada silinmiş veya lisans nedeniyle kaldırılmış olsa bile, diğerlerinde tutulur ve yalnızca günlüğe kaydedilir. Silmeleri diğer hizmetlere yansıtmak için bir üst sınır belirleyin veya arayüzdeki **Silinen şarkıları eşitle** seçeneğini açın.

> **Her zaman önce simülasyon.** `--execute` olmadan çalıştırın (veya kullanıcı arayüzünde **Önizleme**'yi kullanın) ve planı okuyun — herhangi bir şey yazılmadan önce her sağlayıcıda önerilen her ekleme/kaldırma işlemini yazdırır.

<a id="liked-and-favorite-tracks"></a>

### Beğenilen ve favori parçalar

Bir senkronizasyonun **Çalma Listeleri** adımında, kaynak servisin yerleşik beğenilenler koleksiyonunu seçin. SongMirror daha sonra seçilen her varış noktasında nereye gitmesi gerektiğini sorar: doğrudan o hizmetin kendi beğenilen/favori koleksiyonuna veya önerilen adını düzenleyebileceğiniz yeni bir çalma listesine. Yeni bir seçki yalnızca beğenilenlere yöneliktir; Ayrıca her normal çalma listesini senkronize et seçeneğini açın veya her ikisini de dahil etmek için ayrı çalma listeleri seçin.

Bu, Spotify **Beğenilen Şarkılar**, TIDAL/Qobuz/Deezer **Favori Parçalar**, Amazon Music **Beğendiklerim**, Apple Music **Favori Şarkılar** ve YouTube Music **Beğenilen Müzik**'te işe yarar. Aynı tek yönlü, yetkili grup ve N yönlü mutabakat yolları ve güvenlik sınırları geçerlidir. Sıradan çalma listelerinde olduğu gibi, **Silinen şarkıları eşitle** seçeneği açılana kadar silme işlemleri varsayılan olarak kapalı kalır.

TIDAL'nin oturum açtığı web oynatıcısı izni, `r_usr` ve `w_usr` taşıdığında hem sıradan çalma listelerini hem de yerel **Favori Parçalar** koleksiyonunu yönetir. Oturum açma jetonu yanıtının tamamının yakalanması, SongMirror yenileme jetonunun yanı sıra kısa ömürlü Bearer verir, böylece oturum otomatik olarak yenilenebilir.

Bu entegrasyonlardan bazıları sağlayıcıların birinci taraf web arayüzlerini kullanır ve önceden bildirimde bulunulmadan değiştirilebilir; [fizibilite değerlendirmesi](../design/2026-09-01-liked-tracks-sync-feasibility.md), her sağlayıcı için API ve dağıtım kısıtlamalarını kaydeder.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Çalma listesi meta veri yedeklemeleri

Yedeklemeler ikinci bir sağlayıcıya veya senkronizasyon işine ihtiyaç duymaz:

- **Ayarlar → Çalma listesi yedeklemeleri** bölümünde, bağlı bir hesap eklemek için üst kısımdaki **Yedekleme ekle** seçeneğini kullanın. JSON veya XML'yi seçin, ardından günlük veya haftalık gibi bir sıklık seçin. Özel aralıklar bir sayı ve bir birim kullanır. **Yedekleri sakla**, saklama ön ayarları, özel bir sayım veya **Tüm yedeklemeler** sunar.
- Yedeklemeler varsayılan olarak `data/playlist_backups/<account-profile-id>/` (veya Docker'de `/data/playlist_backups/<account-profile-id>/`) şeklindedir. Yerleşik klasör seçici için **Yedekleme klasörü**'ne tıklayın veya **Yolu manuel olarak girin**'i seçin. Özel bir klasörde hâlâ her hesap için ayrı bir alt klasör bulunur. **Varsayılan yedekleme klasörünü kullan** varsayılanı geri yükler. Konumların değiştirilmesi gelecekteki yedeklemeleri etkiler; eski dosyalar oldukları yerde kalır. Saklama ve **En son indir**, seçilen konum için geçerlidir. Bir programın kaldırılması hiçbir zaman kayıtlı dosyaları silmez.
- **Ayarlar → İndirilenler ve Jellyfin → İndirme klasörü** aynı yerleşik seçiciyi ve manuel girişi kullanır. Jellyfin kitaplığınızın erişebileceği bir klasör seçin. İndirmeler, Senkronizasyon sekmesindeki her etkinleştirilen senkronizasyonun zamanlamasını takip eder. Seçici, yapılandırılmış ana bilgisayar yollarını (örneğin, `F:\Torrent\Music`) görüntülerken, Docker eşlemelerini (`/music`) dahili olarak korur. Mevcut indirme bağlantıları değişmedi. Ek ana bilgisayar klasörleri öncelikle Docker bağlama bağlantıları olarak paylaşılmalıdır; bağlantısız bir klasörün seçilmesi bir hata gösterir ve geçerli ayarın değişmeden bırakılmasını sağlar.

- Aynı Ayarlar kartı bir sonraki çalıştırmayı, saklanan anlık görüntü sayısını, son başarılı dosyayı ve sayımları ve en son başarısızlığı gösterir. **Şimdi yedekle** güvenli bir isteğe bağlı çalıştırmayı sıraya koyuyor; **En son indir**, en yeni kalıcı anlık görüntüyü alır.
- **Çalma Listeleri** sayfasında, bir hizmet kartındaki her çalma listesini JSON veya XML sürümlü bir dosya halinde indirmek için bir hizmet kartındaki **Dışa Aktar**'ı kullanın.
- Yalnızca o çalma listesini dışa aktarmak için bir çalma listesi açın. **Soundiiz** seçeneği [Soundiiz'nin belgelenmiş JSON içe aktarma şekli](https://soundiiz.com/data/fileExamples/playlistExport.json)'yi takip eder, böylece indirilen parça listesi Soundiiz'nin **Çalma Listesini İçe Aktar → Dosyadan** akışı aracılığıyla yüklenebilir.
- SongMirror JSON/XML çalma listesi sırasını ve adlarının yanı sıra sağlayıcı parça/oluşma kimliklerini, mevcut ISRC'leri, sanatçıları, albümleri, albüm parça konumlarını, süreleri, eklenen tarihleri, çizim bağlantılarını ve kullanılamayan giriş işaretlerini korur. Kimliksiz katalog hayaletleri kaybolmak yerine yedekte kalır. Dosyalar; çerezler, belirteçler, istek üstbilgileri, önizlemeler veya akışlı dosya URL'leri içermez.

Manuel dışa aktarmalar tarayıcı tarafından kullanıcı arayüzünü çalıştıran cihaza indirilir. Zamanlanmış dışa aktarmalar mevcut uygulama veri birimini kullanır, dolayısıyla ikinci bir ana bilgisayar yolu veya konteyner montajı gerekmez. Yedekleme, sağlayıcı istemcilerine aynı anda erişmek yerine senkronizasyonların ve aktarımların arkasındaki kuyruğu okur. `schema_version` alanı, eski anlık görüntüleri belirsiz hale getirmeden gelecekteki sürümlerin kayıpsız formata dönüşmesine olanak tanır.

<a id="built-in-folder-picker"></a>

### Yerleşik klasör seçici

Yerleşik seçiciyi açmak için bir klasör alanına veya **Gözat…** öğesine tıklayın. Gezinmek için **Konumlar**, tıklanabilir içerik kırıntıları, **Geri**, **İleri** ve **Yukarı bir klasör** kullanın. Seçmek için bir klasörü tıklayın; açmak için çift tıklayın, Enter tuşuna basın veya okunu kullanın. Arama geçerli klasörü filtreler. **Bir klasör yolu girin** tam adresi doğrudan kabul eder. **Klasörü seç** taslağı günceller; uygulamak için ayarları veya programı kaydedin. İptal taslağı değiştirmeden bırakır. Hiçbir masaüstü yardımcısı veya ek işlem gerekmez.

**Yeni klasör**, o anda açık olan konumda adlandırılmış bir alt klasör oluşturur ve ardından onu açar. Mevcut öğelerin üzerine asla yazılmaz. Ad girişinin iptal edilmesi hiçbir şey yaratmaz; Oluşturma sonrasında seçiciyi iptal etmek, yeni klasörü diskte bırakır. Kaydedilen yedekleme veya indirme konumunuz yalnızca seçip kaydettikten sonra değişir. Docker'de seçici hangi yolların paylaşıldığını açıklar ve mümkün olduğunda hem kapsayıcı yolunu hem de yapılandırılmış bilgisayar yolunu gösterir.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Yerel indirme aynası (Jellyfin)

[spotDL](https://github.com/spotDL/spotify-downloader) aracılığıyla senkronize edilen her çalma listesinin çevrimdışı bir ses kopyasını, çalma listesi başına bir klasör olacak şekilde saklayın. Senkronizasyon gerçek yansıtmadır: yeni parçalar indirilir, kaldırılan parçalar yerel olarak silinir. Düzen **Jellyfin-hazırdır** — indirme dizinine bir Jellyfin müzik kitaplığını işaret ettiğinizde hem parçalar hem de çalma listeleri görünür ve her geçişte güncel kalır:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

`DOWNLOAD_DIR` ayarını yapıp spotDL + ffmpeg kurulumunu yaparak etkinleştirin:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- **Artımlı** — ilk tam indirmeden sonra yalnızca yeni eklenen parçalar getirilir; kaldırılan parçalar (ve bunların boşaltılan albüm klasörleri) budanır. Kesintiye uğrayan çalışma bir sonraki geçişte devam eder.
- **En yeni ilk `.m3u8`** — eklenme tarihine göre yazılır, en yeni en üsttedir (çevirmek için `LOCAL_MIRROR_ORDER=oldest` olarak ayarlayın). `uv run main.py --refresh-local` ile mevcut dosyalardan kapakları / etiketleri / mtime'ları yeniden oluşturun.
- **Çalma listesi kapakları Jellyfin** — Jellyfin m3u'nun yanındaki kapak dosyasını yok sayar, bu nedenle `JELLYFIN_URL` + `JELLYFIN_API_KEY` değerini ayarlayın ve her geçiş, Jellyfin API aracılığıyla gerçek çalma listesi kapağını yükler.
- **Yalnızca Spotify değil, her kaynak**: Ayna, eşitlemenin kaynak olarak kullandığı hizmeti okur. Spotify çalma listeleri hâlâ katalog adresinden indirilir; diğer her kaynak (Last.fm dahil) sanatçı ve parça adına göre aranır.
- **Önce kendi kitaplığınız (gerçek FLAC)**: `LOCAL_LIBRARY_DIR` değişkenini mevcut bir müzik ağacına yönlendirin; orada bulunan her parça **özgün biçimiyle çalma listesi klasörüne kopyalanır**, yani bir FLAC yine FLAC kalır. Yalnızca yerelde eşi bulunmayan parçalar spotDL tarafına düşer. Eşleştirme önce ISRC etiketiyle, sonra parça adı ve sanatçıyla yapılır; eşitleme motorunun kurallarıyla aynıdır. Sabit bağlantı yerine kopyalama bilinçli bir tercihtir: ayna değişiklik tarihlerini yazar ve etiketleri tamamlar, sabit bağlantı ise özgün dosyalarınızı değiştirirdi. Boş bırakmak kapalı anlamına gelir.
- **Ses kalitesi** — kaynak YouTube'dir, yani YT Music **Premium** çerezi olmadan tavan ~128–160 kbps'dir. `LOCAL_MIRROR_FORMAT=opus`, YouTube'nin yerel akışını mp3 yeniden kodlaması olmadan tutar; bir Premium çerez (`LOCAL_MIRROR_COOKIE_FILE`), 256 kbps AAC'nin kilidini açar. `flac` seçeneğinin seçilmesi çıkış kabını değiştirir ancak kayıplı bir kaynağı kayıpsız sese dönüştüremez. Gerçek kayıpsız ses için `LOCAL_LIBRARY_DIR` kullanın.

SongMirror, bir akış kataloğundan FLAC çıkarmayı otomatikleştirmez. Yeni her ses kaynağı önce [`docs/monochrome-flac-assessment.md`](../monochrome-flac-assessment.md) belgesindeki koşulları karşılamalıdır: sağlayıcının yayımladığı, sürümlenmiş bir indirme veya dışa aktarma uç noktası, kullanıcıya bağlı yetkilendirme, kalıcı kopya için açık haklar, bölge, son kullanma ve çevrimdışı kullanım kurallarının belgelenmiş olması ve DRM ile erişim denetiminin aşılmaması. Yerel aynayı yalnızca size ait olan veya kopyalamaya yetkili olduğunuz içerik için kullanın.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Her servisi bağlama

Web uygulamasında **Hesaplar** sayfası her serviste size yol gösterir ve yapıştırılacak tam değerleri gösterir. Hiçbir şey üçüncü bir taraf aracılığıyla vekalet edilmez.

<a id="credential-renewal"></a>

### Kimlik bilgilerinin yenilenmesi

SongMirror kimlik bilgilerini ayrı bir belirteç yenileme zamanlayıcısıyla değil, **tam zamanında** yeniler. Her manuel veya planlanmış senkronizasyon geçişi, kullandığı bağlayıcıları doğrular ve desteklenen erişim belirteçlerini ilk istekten önce (veya kimlik doğrulama reddinden sonra) yeniler. Kısa ömürlü bir erişim belirtecinin geçişler arasında süresinin dolması normaldir; önemli olan dayanıklı yenileme belirteci veya yenileme çerezidir. Hesaplar sayfası, yüklendiğinde veya yeniden odaklanıldığında durumu doğrular, ancak bu, arka plan oturum bakımı değildir; etkin senkronizasyon programları şunlardır.

| Hizmet | Yenilenme davranışı |
| --- | --- |
| **Spotify** | Varsayılan bağlantı, isteğe bağlı olarak kayıtlı `sp_dc` çerezinden bir web oynatıcı erişim jetonu basar ve `401`'den sonra yeni bir jetonla yeniden dener; temel oturum açma oturumu yine de iptal edilebilir. Eski geliştirici uygulaması OAuth mevcut yüklemeler için desteklenmeye devam ediyor. |
| **TIDAL** | İçe aktarılan web oynatıcısı erişim belirteci, oturum açma yanıtındaki yenileme belirteci kullanılarak `auth.tidal.com` aracılığıyla otomatik olarak yenilenir. SongMirror bir yanıt onu atladığında mevcut yenileme jetonunu korur ve TIDAL bir tane döndürdüğünde döndürülmüş jetonu sürdürür. Oturumu kapatma veya iptal etme yine de yeni bir yakalama gerektirir. |
| **Qobuz** | Yapıştırılan `X-User-Auth-Token`, Qobuz reddedene kadar kullanılır, ardından tekrar yakalanması gerekir. |
| **Deezer** | Kısa ömürlü Pipe JWT, kullanımdan önce ve `401/403` sonrasında kaydedilen `refresh-token`'den otomatik olarak yenilenir; dönüşümlü yenileme durumu sürdürülür. |
| **Amazon Music** | Web erişim belirteci, yakalanan tarayıcı kullanıcı aracısı, yönlendiren ve izin verilenler listesine eklenen çerezler kullanılarak `/pandaToken` aracılığıyla yenilenir. Mevcut `POST config.json?skipToken=false` akış, gerektiğinde cihaz bağlamını önyükler ve döndürülen çerezler kalıcı olur. Oturum kapatma, güvenlik değişiklikleri veya sunucu tarafı iptali hâlâ yeni bir yakalama gerektiriyor. |
| **Apple Music** | Yapıştırılan Bearer ve Media-User-Token, SongMirror tarihine kadar yenilenemez ve reddedildikten sonra yeniden yakalanmalıdır. |
| **YouTube Music** | Data API OAuth sürenin dolmasından itibaren 60 saniye içinde otomatik olarak yenilenir. Tarayıcı modu, bir senkronizasyon hedefi oluşturulduğunda Google'nin çerez rotasyonunu dener; süresi dolmuş bir tarayıcı oturumunun yeniden dışa aktarılması gerekir. |
| Last.fm | Ne API anahtarı ne de oturum anahtarı sona erer, dolayısıyla hiçbir şey yenilenmez. Yalnızca uygulamanın erişimini Last.fm hesap ayarlarınızdan geri aldıysanız yeniden yetkilendirin. |
| **Jellyfin** | API anahtarının erişim belirteci yenileme döngüsü yoktur; yalnızca iptal edilmesi veya silinmesi durumunda değiştirin. |

<a id="spotify"></a>

### Spotify

1. <https://open.spotify.com> adresinden oturum açın.
2. Tarayıcının DevTools (`F12`) konsolunu açın → **Application** (Chrome/Edge) veya **Storage** (Firefox) → **Cookies** → `https://open.spotify.com`.
3. `sp_dc` çerezinin değerini kopyalayın ve Hesaplar → Spotify bölümüne yapıştırın.

Bu tek oturum açmalı web oturumu; kitaplığa göz atma, çalma listesi okuma ve yazma işlemlerini ve katalog arama işlemlerini gerçekleştirir. Spotify geliştirici uygulaması, API anahtarı veya Premium hesap gerektirmez. `sp_dc` çerezine bir şifre gibi davranın: SongMirror bunu kendi özel veri dizininde saklar, ancak entegrasyon Spotify'nin dahili web oynatıcı işlemlerini kullanır ve Spotify bunları değiştirirse bakım gerektirebilir. Mevcut geliştirici uygulaması OAuth kimlik bilgileri uyumlu bir alternatif olmaya devam eder.

<a id="tidal"></a>

### TIDAL

1. [TIDAL'in web oynatıcısı](https://listen.tidal.com) sayfasını açın, DevTools → **Network** sekmesini açın ve **Preserve log** seçeneğini etkinleştirin.
2. Oturumu kapatıp tekrar açın, ardından Network listesinde `oauth2/token` filtresini uygulayın.
3. Başarılı `auth.tidal.com/v1/oauth2/token` isteğini seçin. **Payload** (Chrome/Edge) veya **Request** (Firefox) bölümünde, `client_id` form değerini SongMirror'nin **Web oynatıcı istemci kimliği** alanına kopyalayın.
4. İsteğin **Response** sekmesini açın ve JSON'nin tamamını **Web oynatıcı belirteci yanıtı** alanına yapıştırın. Hem `access_token` hem de `refresh_token` içermelidir.
5. Bağlan'a tıklayın. SongMirror yenileme yetkisini hemen test eder ve istemci kimliğinin belirteci yenileyememesi durumunda işlemi başarıyla tamamlamayı reddeder.

OAuth istemci kimliği bir istek meta verisidir ve TIDAL'nin erişim belirteci içindeki sayısal `cid` talebi değildir. SongMirror yalnızca erişim belirtecini, yenileme belirtecini, istemci kimliğini, kapsamları, geçerlilik tarihini ve katalog ülkesini çıkarır; ilgisiz yanıt verileri atılır. Sürenin dolmasından hemen önce ve kimlik doğrulama reddinden sonra `https://auth.tidal.com/v1/oauth2/token` aracılığıyla yenilenir ve yenileme belirteci rotasyonu korunur. Eski OpenAPI istek başlığı yapıştırması uyumlu kalmaya devam eder, ancak yenileme belirteci içermediğinden süresi dolduktan sonra yeniden yapıştırılması gerekir. Yalnızca katalog meta verileri ve oturum açan kullanıcının çalma listeleri kullanılır; oynatma akışları bu entegrasyonun kapsamı dışındadır.

<a id="qobuz"></a>

### Qobuz

<https://play.qobuz.com> adresinden oturum açın, DevTools → **Network** sekmesini açın ve `api.json/0.2` için filtreleyin. `X-App-Id` ve `X-User-Auth-Token` içeren (kimliği doğrulanmış `album/story` isteği dahil) herhangi bir isteği seçin, ardından istek başlıklarını kopyalayın veya cURL olarak kopyalayıp sihirbaza yapıştırın. SongMirror yalnızca bu iki değeri saklar, bunları web oynatıcısıyla aynı başlık tabanlı akışı kullanarak gönderir ve çerezleri ile ilgisiz tarayıcı meta verilerini atar. Kurumsal API onayı veya kullanıcı kimliği gerekmez; mevcut iş ortağı kimlik bilgileri uyumlu bir ortam alternatifi olarak kalır.

Bağdaştırıcı yalnızca katalog arama ve çalma listesi uç noktalarını kullanır; ses akışı veya dosya URL'leri istemez.

<a id="deezer"></a>

### Deezer

<https://www.deezer.com> adresinden oturum açın, DevTools → **Network** sekmesini açın ve sayfayı yenileyin. `auth.deezer.com/login/renew` filtresini uygulayın, bu isteğin başlıklarını kopyalayın (veya cURL olarak kopyalayın) ve yenileme alanına yapıştırın. Firefox bunun yerine istek çerezlerini yalın noktalı virgülle ayrılmış bir blok olarak kopyalayabilir; bu biçim de kabul edilir. SongMirror yalnızca özel `refresh-token` çerezini tutar ve bunu Deezer'nin kısa ömürlü Pipe JWT belirtecini otomatik olarak yenilemek için kullanır. Ayrıca mevcut bir `pipe.deezer.com/api` isteğini anında başlangıç olarak da yapıştırabilirsiniz, ancak yenileme yapılandırıldığında buna gerek yoktur. Çalma listesi ekleme ve silme işlemlerinin her ikisi de yenilenebilir Pipe oturumunu kullanır; `arl` çerezi gerekmez. Mevcut geliştirici OAuth belirteçleri uyumlu bir ortam alternatifi olarak desteklenir.

<a id="amazon-music"></a>

### Amazon Music

Varsayılan bağlayıcı için geliştirici onayı gerekmez. Amazon Music web oynatıcısıyla aynı kimliği doğrulanmış GraphQL ve belirteç yenileme rotalarını kullanır:

1. <https://music.amazon.com> adresinde oturum açın ve DevTools → **Network** sekmesini açın.
2. Sayfayı yenileyin, `config.json` için filtreleyin ve oturum açma isteğini seçin. (`pandaToken` göründüğünde de çalışır, ancak zorunlu değildir.)
3. **Copy request headers** veya **Copy as cURL** seçeneğini belirleyin ve ardından bunu yenileme alanına yapıştırın. `User-Agent`, `Referer` ve `Cookie` başlıklarını eksiksiz tutun, böylece SongMirror aynı tarayıcı bağlamını yeniden oynatabilir.
4. İsteğe bağlı olarak, oturum açılmış olan `config.json` yanıtını başlangıç alanına kopyalayın; SongMirror normalde yenileme oturumunu kullanarak bu cihaz bağlamını kendisi alabilir.

SongMirror aynı `AmznMusic` yetkilendirme değerini yerel olarak türetir ve süre dolmadan önce veya kimlik doğrulama reddinden sonra bunu `music.amazon.com/pandaToken` aracılığıyla yeniler. Bağlantı sırasında cihaz bağlamı gerektiğinde tarayıcı tarzı yapılandırma isteğini kullanır, bir erişim belirteci oluşturmak için `/pandaToken` rotasını çağırır ve Amazon yenileme çerezini iptal ederse bağlantıyı reddeder. Yalnızca tarayıcı kullanıcı aracısını, dili, Müzik yönlendirenini, Amazon kimlik doğrulama/oturum çerezlerinin izin verilenler listesini ve sınırlı istemci cihazı bağlamını saklar; analizler, denemeler, AWS konsolu, CSRF ve diğer ilgisiz veriler atılır. Saklanan çerezler hassas olduğundan SongMirror'yi yerel ağınızda gizli tutun. Oturum kapatma, parola/güvenlik değişikliği veya sunucu tarafı iptali yeni bir yakalama gerektirebilir.

Bu, desteklenmeyen bir birinci taraf web istemcisi arayüzüdür ve Amazon bunu bildirimde bulunmaksızın değiştirebilir. Belgelenen [Amazon Music İnternet API](https://developer.amazon.com/docs/music/API_web_overview.html) hâlâ kapalı betadadır; onaylanan iş ortağı kimlik bilgileri ortam değişkenleri aracılığıyla yapılandırıldığında isteğe bağlı bir alternatif olarak kalır.

<a id="apple-music"></a>

### Apple Music

Apple Developer hesabına gerek yoktur; `music.apple.com` üzerinden alınan iki başlık yeterlidir. <https://music.apple.com> adresini açın, oturum açın, DevTools → **Network** sekmesini açın, bir şarkı çalın, `amp-api.music.apple.com` için filtreleyin ve herhangi bir isteğin başlığından şunları kopyalayın:

- `authorization: Bearer eyJ...` → **Bearer token** (`Bearer ` hariç, `eyJ...` kısmı)
- `media-user-token: ...` → **User token** (tam değer)

Bağlantı sihirbazı, ham başlıkları yapıştırmanıza ve değerleri sizin için ayrıştırmanıza olanak tanır. Belirteçler aylarca geçerlidir; süreleri dolduğunda bunları Hesaplar sayfasına yeniden yapıştırın.

Etkin bir Apple Music aboneliği olmayan bir Apple Kimliği yine de **Yalnızca Katalog** modunda bağlanabilir. Bu modda, başka bir bağlı servise kopyalamak için Aktarımlar sayfasına herkese açık bir Apple Music çalma listesi bağlantısı yapıştırabilirsiniz. Apple kitaplığına göz atma, planlı senkronizasyon ve Apple Music'yi aktarım hedefi olarak kullanma hâlâ ücretli CloudLibrary yetkisi gerektirir; SongMirror geçerli katalog kimlik bilgilerini süresi dolmuş saymak yerine bu işlemleri kullanılamaz olarak gösterir.

<a id="youtube-music"></a>

### YouTube Music

OAuth yenileme belirteci dayanıklı olan ve yeniden başlatmalarda korunan resmi [YouTube Data API v3](https://developers.google.com/youtube/v3) ile iletişim kurar.

1. [Google Bulut konsolu](https://console.cloud.google.com) üzerinde bir proje oluşturun, **YouTube Data API v3**'ü etkinleştirin ve **TVs and Limited Input devices** türünde bir OAuth istemcisi oluşturun.
2. **OAuth consent screen** ekranında **Publishing status → In production** (Yayınlama durumu → Yayında) seçeneğini ayarlayın ("Testing" durumunda bırakmak belirtecin geçerliliğini 7 gün sonra sona erdirir).
3. Uygulamada istemci kimliğini + gizli anahtarını yapıştırın ve ekrandaki cihaz kodunu onaylayın.

> **Kota**: Data API günde 10.000 birime izin verir (arama maliyeti 100, ekleme/çıkarma maliyeti 50). Rutin bakım işlemleri oldukça ekonomiktir; ilk çalıştırmadaki büyük bir aktarım limite ulaşıp ertesi gün devam edebilir.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="lastfm"></a>

### Last.fm

Last.fm'in çalma listesi yoktur, dolayısıyla asla çalma listesi hedefi olmaz. **Dinleme geçmişinizi** salt okunur koleksiyonlar olarak sunar ve **Loved Tracks** koleksiyonu, diğer tüm sağlayıcılardaki gibi bir beğenilen parça koleksiyonudur; hesabı yetkilendirdiğinizde yazılabilir hale gelir.

1. <https://www.last.fm/api/account/create> adresinde bir API hesabı oluşturun. Hem **API anahtarını** hem de **paylaşılan gizli anahtarı** not edin.
2. Hesaplar → Last.fm bölümünde ikisini de yapıştırın, ardından Last.fm yetkilendirme sayfasını tamamlayın.

İki kimlik bilgisi düzeyi vardır ve yazmayı açan ikincisidir:

| Verdiğiniz | Aldığınız |
| --- | --- |
| API anahtarı + kullanıcı adı | o profilin herkese açık okumaları |
| + paylaşılan gizli anahtar + yetkilendirme | **özel** okumalar ve beğenilen parça ekleyip kaldırma |

Yetkilendirme tarayıcı üzerinden tek seferlik bir gidiş dönüştür: SongMirror sizi Last.fm'e yönlendirir, uygulamayı onaylarsınız ve dönen belirteç **süresiz ömürlü bir oturum anahtarıyla** değiştirilir. Yukarıdaki tablodaki yapıştırılan tüm kimlik bilgilerinin aksine bunun yeniden alınması hiç gerekmez. Last.fm hesap ayarlarınızdan geri alabilirsiniz.

Bu, şunları kullanıma açar:

| Koleksiyon | İçerik |
| --- | --- |
| **Loved Tracks** | beğenilen parça koleksiyonu. Her zaman okunabilir; yetkilendirmeden sonra **yazılabilir**, böylece Spotify, TIDAL veya Apple beğenileriniz *Last.fm tarafına* eşitlenebilir |
| **Top Tracks (7 gün … tüm zamanlar)** | her Last.fm dönemi için bir tane olmak üzere, sıralanmış altı salt okunur koleksiyon |
| **Recent Scrobbles** | o anda çalan satır dışında kalan dinleme akışı |

Buna güvenmeden önce bilinmesi gereken üç sınır:

- **ISRC yok.** `user.*` uç noktaları yalnızca sanatçı ve parça adı döndürür, bu yüzden Last.fm parçaları katalog kimliği yerine ada göre eşleştirilir. ISRC taşıyan bir sağlayıcının önleyeceği hatalı sürümlerle ara sıra karşılaşabilirsiniz. Bir parçayı beğenmeden önce SongMirror, `track.getInfo` üzerinden Last.fm'in standart yazımını sorar; böylece çok benzer bir başlık ikinci bir kayıt oluşturmaz.
- **Sıralanmış koleksiyonlarda tarih yoktur.** Top Tracks parça başına zaman damgası taşımaz, bu yüzden o parçalar tarihsiz eşitlenir ve eklenme sırasını belirleyemez.
- **Çalma listesi yolları geçerli değildir.** Beğenilen parçaların *Last.fm tarafına* eşitlenmesi yerel yolu kullanmak zorundadır. Adlandırılmış çalma listesi oluşturan yolun yazabileceği bir çalma listesi yoktur.

Paylaşılan gizli anahtar olmadan, belirttiğiniz profilin Loved Tracks ve Top Tracks koleksiyonları herkese açık olmalıdır.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ Arayüzsüz CLI (Headless)

`.env` + cron / Task Scheduler'yi mi tercih edersiniz? Aynı motor grafiksel bir arayüz olmadan da çalışır.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Yararlı bayraklar:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Anahtar env değişkenleri (bkz. `.env.example`): kullandığınız sağlayıcılara ait kimlik bilgileri, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` ve `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Güvenlik önlemleri

Kaldırma işlemleri yıkıcıdır, bu nedenle korunurlar:

- **Simülasyon varsayılandır** — `--execute` (veya arayüzün gerçek senkronizasyon eylemi) olmadan hiçbir şey değişmez.
- Kaynak, hedefin boş olmadığını gösterdiği bir çalma listesi için 0 parça döndürürse, bu geçişte kaldırma işlemleri atlanır (geçici bir API hatası, çalma listesini boşaltamaz).
- **Silme işlemleri varsayılan olarak kapalıdır** — `MAX_REMOVALS=0` tüm silmeleri bekletir; işlemler günlüğe kaydedilir ancak uygulanmaz. Böylece bir platformdaki lisans kaynaklı kaldırma diğer platformlarda zincirleme silmeye yol açamaz. Her senkronizasyon için **Silinen şarkıları eşitle** seçeneğini açın veya `MAX_REMOVALS` değerini ayarlayın. Etkinleştirilmiş olsa bile, bir çalıştırmada bekleyen silme sayısı üst sınırı aşarsa tüm silmeler atlanır ve günlüğe kaydedilir.
- `MAX_ADDS` kronoloji onarımı da dahil olmak üzere bir **senkronizasyon** geçişinde zaman damgası üreten her türlü yazmayı sınırlar. Kurtarılan daha eski bir eşleşme, sınırın izin verdiğinden daha büyük bir sonek tekrarına ihtiyaç duyuyorsa, SongMirror onu en yeni görünmesini sağlamak veya büyük bir sağlayıcı patlamasına neden olmak yerine bir sonraki geçişe erteler. Bir **tek seferlik aktarımın** bir sonraki geçişi yoktur; bu nedenle asla ertelemez: İstenilen her parçayı kopyalar, siz söz konusu aktarım için "Son Eklenenleri Koru" seçeneğini açmadığınız sürece kaynak sırasına göre ekler.
- Kronoloji onarımı, orijinali kullanımdan kaldırmadan önce yedek bir kopyayı hazırlar. Silme işleminin bir şarkının tüm kopyalarını kaldırdığı bir serviste, korunan kopya sayısının tam doğru olması gerekir; bu nedenle Apple Music aşamalı kopyalar görünene kadar yeniden okur ve hâlâ kendi yazmalarını takip eden bir okumaya karşı herhangi bir şeyi silmeyi reddeder. Deezer onarımı tamamen atlar ve her zaman sona ekler: konumsal ekleme desteği de yoktur, bu nedenle yansıtamadığı bir sırayı zorlamak hedefe yönelik riske değmez. Aktarım formu oradaki sıralama seçeneğini devre dışı bırakır ve nedenini açıklar.
- **Net kayıp koruması** — söz konusu serviste eşleşmesi olmayan, kaynak parçaya benzeyen hedef taraftaki parça silinmez, bekletilir.
- Herhangi bir sağlayıcı kimlik doğrulama hatası, sağlayıcının geçişini anında iptal eder; süresi dolmuş belirteçlerde kısmi silme işlemi yapılmaz.
- Bir birleştirme işi, hedefinden silmeden önce her bileşen kaynağının okunmasını bitirmelidir; salt ekleme davranışına geçen herhangi bir kısmi/başarısız kaynak anlık görüntüsü kuvveti.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Önbellek ve şarkı arşivi

Çözümlenebilir olan her şey önbelleğe alınır, böylece kararlı durumdaki geçişler neredeyse anlık tamamlanır: servis başına çözümleme önbellekleri (ISRC + arama, kaçırılanlar dahil), `snapshot_id` anahtarlı parça listesi önbelleği, SQLite'de tam tanımlayıcı bağlantılar ve çift başına anlık görüntü atlama (`unchanged since last clean sync`).

Her geçiş aynı zamanda karşılaştığı her parçanın meta verilerini `song_cache.db` dosyasına arşivler; bu, sürekli büyüyen bir SQLite veritabanıdır. Kaldırılan parçalar; ad, sanatçı, albüm, süre, ISRC, ham anlık görüntü JSON'ı ve ilk/son görülme zaman damgalarıyla birlikte arşivlenir:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Eşlemeleri çözümle

Her servis, normalleştirilmiş bir `title|artist` anahtarını o serviste eşleştiği katalog kimliğiyle eşleştirerek kendi çözümleme önbelleğini tutar. Bir eşleşme sonsuza kadar yeniden kullanılır; aynı durum "eşleşme yok" sonucu için de geçerlidir, bu da bir kez eşleşmeyen parçanın sonraki her geçişte eşleşmemiş kalmasını sağlar.

Web kullanıcı arayüzündeki **Eşlemeler** sayfası, bu önbellekleri servis başına doğrudan gösterir:

- önbelleğin tamamında başlığa, sanatçıya veya çözümlenen kimliğe göre arama yapın
- **elle ayarlanan** girişleri (aktarım çakışması düzenleyicisinde seçtiğiniz bir eşleşme) veya **eşleşme yok** girişlerini filtreleyin
- doğru parçanın bağlantısını yapıştırarak yanlış bir kimliği düzeltin veya bir sonraki geçişte tekrar aranması için eşlemeyi silin
- bir servise ait tüm "eşleşme yok" girişlerini tek bir işlemle temizleyerek başarısız aramaların topluca yeniden denenmesini sağlayın

Giderilen bir eksiklik daha sonra çözümlendiğinde, bunun eklenmesi eski şarkının en yeniymiş gibi görünmesine yol açabilir. Çalma listesi hedefleri için SongMirror bunun yerine o şarkıyı ve listede zaten mevcut olan yeni parçaları en eskiden en yeniye doğru yeniden çalar, ardından eski kopyaları kaldırır. Servisler istemcilerin orijinal zaman damgalarını geri yüklemesine izin vermez, ancak bu yöntem şarkıların bağıl **Son Eklenenler** sırasını korur. Yerel beğenilen/favori koleksiyonları yalnızca üyelik listesi olarak kalır ve asla yeniden oynatılmaz.

Senkronizasyon çalışırken önbellek bellekte tutulduğundan ve tamamlandığında üzerine yazılacağından, bu sırada yapılan düzenlemeler açıklayıcı bir mesajla reddedilir.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Proje düzeni

CLI girişi: `uv run main.py` (ince dolgu) veya `python -m songmirror`. Web girişi: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

**Başka bir servis ekleme**: `MirrorTarget` alt sınıfı oluşturun, ~8 yöntemi uygulayın, oluşturucusunu `engine/targets`' `_REGISTRY`'ye ve sınıfını `_CLASSES`'ye ekleyin ve `services/accounts` altına eşleşen bir `Connector` ekleyin. Tüm uzlaştırma mantığı (fark, sıralama, Güvenlik önlemleri, günlük kaydı, anlık görüntü atlama) otomatik olarak devralınır.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Sorun giderme

- **`Missing required environment variable`** — `.env` (CLI) dosyasını doldurun veya servisi kullanıcı arayüzüne bağlayın.
- **TIDAL raporlar `Expired`** — `listen.tidal.com` adresinden çıkış yapıp tekrar giriş yapın; ardından hem `oauth2/token` istek yükündeki `client_id` değerini hem de tam yanıt JSON'ını Hesaplar'a yapıştırın. Kopyalanan bir OpenAPI isteği yalnızca kısa ömürlü Bearer taşır ve yenilenemez.
- **TIDAL raporlar HTTP 429** — bu geçici bir istek hızı sınırıdır, süresi dolmuş bir oturum açma değildir. SongMirror sağlayıcının yeniden deneme gecikmesini onurlandırır ve API'yi tekrar tekrar sorgulamak yerine hesap durumu kontrollerini önbelleğe alır.
- **Qobuz veya Apple raporları `Expired` / `401` / `403`** — yapıştırılan bu oturumların yenilenebilir bir sırrı yoktur; Hesaplar'da yeni oturum açılmış bir istek veya belirteç yakalayın.
- **TIDAL, jetonun beğenilen parça erişimine sahip olmadığını söylüyor** — `r_usr` ve `w_usr` taşıyan yeni oturum açılmış bir web oynatıcı jetonu yanıtı yakalayın.
- **Deezer yenileme başarısız oluyor** — yeni bir `auth.deezer.com/login/renew` isteği (veya onun `refresh-token` çerezi) yakalayın. Geçerli bir Pipe Bearer tek başına yalnızca geçici bir başlangıçtır.
- **Amazon Music yenileme başarısız oluyor** — tam `User-Agent`, `Referer` ve `Cookie` üstbilgileriyle yeni oturum açılmış bir `POST /config.json?skipToken=false` isteği yakalayın. JSON yanıtı isteğe bağlıdır.
- **YouTube Music tarayıcı modunun süresi dolar** — yeni tarayıcı istek başlıklarını dışa aktarın. En dayanıklı, gözetimsiz kurulum için üretim ortamı onay ekranıyla Data API OAuth kullanın.
- **Spotify raporların Süresi Doldu** — `open.spotify.com` adresinden tekrar oturum açın ve Hesaplar'a yeni bir `sp_dc` çerezi yapıştırın.
- **Bir çalma listesi senkronize edilmiyor** — listenin senkronizasyon kapsamında olduğunu ve kaynakta mevcut olduğunu doğrulayın (hedefler gerçek bir geçişte otomatik olarak oluşturulur).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Lisans

Telif Hakkı © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Bu proje [MIT](../../LICENSE) lisanslıdır.

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
