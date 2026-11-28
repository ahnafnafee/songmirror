<div align="center"><a name="readme-top"></a>

<img src="../../.github/assets/mark.png" alt="" height="72">

# SongMirror

**अपनी प्लेलिस्ट सिंक रखें।**<br>
अपने सर्वर पर शेड्यूल के अनुसार सिंक करें, किसी प्लेलिस्ट को एक बार कॉपी करें या Jellyfin के लिए संगीत की स्थानीय प्रति रखें। मुफ़्त और ओपन सोर्स।

[![Docker से चलाएँ][docker-start-badge]](#quick-start)
[![GHCR][registry-badge]][registry-link]
[![Ko-fi पर समर्थन करें][kofi-badge]][kofi-link]

[निर्देशित इंस्टॉलेशन](#guided-install) · [समर्थित सेवाएँ](#supported-services) · [विशेषताएँ](#features) · [स्क्रीनशॉट](guide.hi.md#screenshots) · [SongMirror का समर्थन करें](#support) · [वेबसाइट][website-link]

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

<a href="guide.hi.md#screenshots"><img src="../../.github/assets/songmirror-preview.webp" alt="SongMirror — डैशबोर्ड · प्लेलिस्ट" width="100%"></a>

[![CI][ci-shield]][ci-link]
[![MIT][license-shield]](../../LICENSE)
[![GitHub पर स्टार दें][stars-shield]][stars-link]

</div>

<a id="quick-start"></a>

## 🚀 त्वरित शुरुआत

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose up -d
```

**http://localhost:8888** खोलें। **खाते** में अपनी सेवाएँ जोड़ें। एक बार कॉपी करने के लिए **स्थानांतरण**, या तय समय पर सूचियाँ अपडेट करने के लिए **सिंक** चुनें।

<a id="guided-install"></a>

### निर्देशित इंस्टॉलेशन

[Render](https://render.com/) · [CapRover](https://caprover.com/) · [Portainer](https://www.portainer.io/) · [इस्तेमाल की मार्गदर्शिका](guide.hi.md#guided-install)

<a id="app-language"></a>

### ऐप भाषा

**सेटिंग्स → सामान्य → भाषा** में भाषा बदलें। ब्राउज़र की भाषा इस्तेमाल करने के लिए **स्वचालित (ब्राउज़र)** चुनें।

<a id="supported-services"></a>

## समर्थित सेवाएँ

**खाते → खाता जोड़ें** खोलें और कोई सेवा खोजें।

| सेवा | सिंक और ट्रांसफ़र का समर्थन |
| --- | --- |
| [Spotify](https://open.spotify.com/), [TIDAL](https://tidal.com/), [Qobuz](https://play.qobuz.com/), [Deezer](https://www.deezer.com/), [Amazon Music](https://music.amazon.com/), [Apple Music](https://music.apple.com/), [YouTube Music](https://music.youtube.com/), [Navidrome](https://www.navidrome.org/), [Subsonic](https://www.subsonic.org/) | प्लेलिस्ट और पसंदीदा ट्रैक |
| [SoundCloud](https://soundcloud.com/), [Anghami](https://play.anghami.com/), [Audiomack](https://audiomack.com/), [Gaana](https://gaana.com/), [JioSaavn](https://www.jiosaavn.com/) | प्लेलिस्ट |
| [Jellyfin](https://jellyfin.org/), [Emby](https://emby.media/), [Plex](https://www.plex.tv/media-server-downloads/), [Mopidy](https://mopidy.com/), [Lyrion Music Server](https://lyrion.org/) | सर्वर की प्लेलिस्ट |
| [Last.fm](https://www.last.fm/) | पसंदीदा और सबसे ज़्यादा सुने गए ट्रैक तथा सुनने का इतिहास। पसंदीदा ट्रैक बदलने के लिए अनुमति दें। |
| [ListenBrainz](https://listenbrainz.org/) | प्लेलिस्ट और पसंदीदा रिकॉर्डिंग। बदलाव करने के लिए यूज़र टोकन चाहिए। |
| [QQ Music](https://y.qq.com/), [LINE MUSIC](https://music.line.me/), [Pandora](https://www.pandora.com/), [Naver Vibe](https://vibe.naver.com/), [NetEase Cloud Music](https://music.163.com/) | स्रोत के रूप में सार्वजनिक प्लेलिस्ट लिंक या साइन-इन की गई लाइब्रेरी का इस्तेमाल करें। |

[प्रत्येक सेवा को जोड़ना](guide.hi.md#connecting-each-service) · [प्लेलिस्ट अडैप्टर गाइड](../music-service-adapters.md)

<a id="features"></a>

## ✨ विशेषताएँ

- [एकतरफ़ा, दोतरफ़ा और कई स्रोतों से सिंक](guide.hi.md#how-it-works)
- [एक बार के लिए प्लेलिस्ट स्थानांतरण](guide.hi.md#features) · [इतिहास और बहाली](../transfer-history.md)
- [प्लेलिस्ट मेटाडेटा बैकअप](guide.hi.md#playlist-metadata-backups) · [सेव किए गए एल्बम का स्थानांतरण](../saved-albums.md) · [स्थानीय डाउनलोड मिरर (Jellyfin)](guide.hi.md#local-download-mirror-jellyfin)

[इस्तेमाल की मार्गदर्शिका](guide.hi.md)

<a id="support"></a>

## SongMirror का समर्थन करें

आपकी मदद से अलग-अलग संगीत सेवाओं पर रखरखाव और परीक्षण का खर्च पूरा होता है।

[![Ko-fi पर समर्थन करें][kofi-badge]][kofi-link]
[![GitHub पर प्रायोजित करें][sponsor-badge]][sponsor-link]

[GitHub पर स्टार दें][stars-link] · [ऊपर जाएँ](#readme-top)

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
