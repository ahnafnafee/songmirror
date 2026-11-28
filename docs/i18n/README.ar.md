<div lang="ar" dir="rtl">

<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**حافظ على مزامنة قوائم التشغيل.**<br>
استضف المزامنة المجدولة بنفسك، أو انسخ قائمة تشغيل مرة واحدة، أو احتفظ بنسخة موسيقية محلية لـ Jellyfin. مجاني ومفتوح المصدر.

[![التشغيل باستخدام Docker][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![ادعم على Ko-fi][kofi-badge]][kofi-link]

[التثبيت الموجّه](#guided-install) · [الخدمات المدعومة](#supported-services) · [المميزات](#features) · [لقطات الشاشة](guide.ar.md#screenshots) · [ادعم SongMirror](#support) · [الموقع][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.ar.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — لوحة التحكم · قوائم التشغيل" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![أضف نجمة على GitHub][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 بداية سريعة

<div dir="ltr">

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

</div>

افتح **http://localhost:8888**. من **الحسابات**، اربط الخدمات التي تستخدمها. اختر **نقل القوائم** لنسخ قائمة مرة واحدة، أو **المزامنة** لتحديث القوائم وفق جدول.

<a id="guided-install"></a>

### التثبيت الموجّه

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [دليل المستخدم](guide.ar.md#guided-install)

<a id="app-language"></a>

### لغة التطبيق

غيّر اللغة من **الإعدادات → عام → اللغة**. اختر **تلقائي (المتصفح)** لاستخدام لغة المتصفح.

<a id="supported-services"></a>

## الخدمات المدعومة

افتح **الحسابات → إضافة حساب** وابحث عن خدمة.

| الخدمة | دعم المزامنة والنقل |
| --- | --- |
| [Spotify](https://open.spotify.com/)، [TIDAL](https://tidal.com/)، [Qobuz](https://play.qobuz.com/)، [Deezer](https://www.deezer.com/)، [Amazon Music](https://music.amazon.com/)، [Apple Music](https://music.apple.com/)، [YouTube Music](https://music.youtube.com/)، [Navidrome](https://www.navidrome.org/)، [Subsonic](https://www.subsonic.org/) | قوائم التشغيل والمفضلة |
| [SoundCloud](https://soundcloud.com/)، [Anghami](https://play.anghami.com/)، [Audiomack](https://audiomack.com/)، [Gaana](https://gaana.com/)، [JioSaavn](https://www.jiosaavn.com/) | قوائم التشغيل |
| [Jellyfin](https://jellyfin.org/)، [Emby](https://emby.media/)، [Plex](https://www.plex.tv/media-server-downloads/)، [Mopidy](https://mopidy.com/)، [Lyrion Music Server](https://lyrion.org/) | قوائم تشغيل الخادم |
| [Last.fm](https://www.last.fm/) | المقاطع المحبوبة والأكثر استماعًا وسجل التشغيل. فوّض تعديل المقاطع المحبوبة. |
| [ListenBrainz](https://listenbrainz.org/) | قوائم التشغيل والتسجيلات المحبوبة. يتيح رمز المستخدم التعديل. |
| [QQ Music](https://y.qq.com/)، [LINE MUSIC](https://music.line.me/)، [Pandora](https://www.pandora.com/)، [Naver Vibe](https://vibe.naver.com/)، [NetEase Cloud Music](https://music.163.com/) | استخدم روابط قوائم التشغيل العامة أو مكتبة حسابك المسجّل الدخول إليه كمصدر. |

[ربط كل خدمة](guide.ar.md#connecting-each-service) · [دليل خدمات قوائم التشغيل](../music-service-adapters.md)

<a id="features"></a>

## ✨ المميزات

- [المزامنة أحادية الاتجاه وثنائية الاتجاه ومتعددة المصادر](guide.ar.md#how-it-works)
- [نقل قوائم التشغيل مرة واحدة](guide.ar.md#features) · [السجل والاسترداد](../transfer-history.md)
- [النسخ الاحتياطية للبيانات الوصفية لقائمة التشغيل](guide.ar.md#playlist-metadata-backups) · [نقل الألبومات المحفوظة](../saved-albums.md) · [مرآة التنزيل المحلية (Jellyfin)](guide.ar.md#local-download-mirror-jellyfin)

[دليل المستخدم](guide.ar.md)

<a id="support"></a>

## ادعم SongMirror

يساعد دعمك في تمويل الصيانة والاختبار عبر خدمات الموسيقى.

[![ادعم على Ko-fi][kofi-badge]][kofi-link]
[![ادعم عبر GitHub Sponsors][sponsor-badge]][sponsor-link]

[أضف نجمة على GitHub][stars-link] · [العودة إلى الأعلى](#readme-top)

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

</div>
