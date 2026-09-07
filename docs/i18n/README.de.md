<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Selbstgehostete, ständig aktive Playlist-Synchronisierung für Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music und YouTube Music – plus ein lokaler Audiospiegel bereit für Jellyfin.<br/>
Eine kostenlose, selbstgehostete Open-Source-Alternative zu Soundiiz, TuneMyMusic und FreeYourMusic, die Sie besitzen und betreiben.

**Synchronisierung in eine Richtung, Zusammenführung mehrerer Quellen, autorisierende Gruppen oder vollständige bidirektionale (N-Wege)-Synchronisierung · einmalige Playlist-Übertragungen · genaue Zuordnung durch ISRC · alles über Ihren Browser**

[Schnellstart](#quick-start) · [Funktionen](#features) · [Screenshots](#screenshots) · [Läuft immer: Docker](#always-running-docker) · [So funktioniert es](#how-it-works) · [Fehler melden][github-issues-link] · [Funktion vorschlagen][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Teilen Sie dieses Projekt**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Einmalige Einrichtung – jede Playlist, die Sie kuratieren, bleibt in der Reihenfolge des hinzugefügten Datums in allen Diensten gespiegelt.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror Demo – Logo-Enthüllung, Dashboard, einseitige und bidirektionale Synchronisierungseinrichtung, Live-Wiedergabelistenübertragungen und genaue Zuordnung durch ISRC über sieben Musikdienste hinweg" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">Sehen Sie sich die 1080p-Version an</a></sup>

</div>

> [!NOTE]
> Web-App + ohne grafische Benutzeroberfläche CLI, eine Engine. Klicken Sie durch eine Browser-Benutzeroberfläche, um Dienste zu verbinden, Synchronisierungen zu erstellen und Wiedergabelisten zu übertragen – oder führen Sie es im `.env` + Cron-Stil aus. Beide steuern denselben Synchronisierungskern.

<details>
<summary><kbd>Inhaltsverzeichnis</kbd></summary>

#### Inhaltsverzeichnis

- [✨ Funktionen](#features)
- [📸 Screenshots](#screenshots)
- [🚀 Schnellstart](#quick-start)
  - [App-Sprache](#app-language)
- [🐳 Läuft immer: Docker](#always-running-docker)
- [⚙️ So funktioniert es](#how-it-works)
  - [Passend](#matching)
  - [Synchronisierung der Zusammenführung mehrerer Quellen](#multi-source-merge-sync)
  - [Maßgebliche Gruppen](#authoritative-groups)
  - [Bidirektionale (N-Wege) Synchronisierung](#bidirectional-n-way-sync)
- [📦 Sicherungen der Playlist-Metadaten](#playlist-metadata-backups)
- [💿 Lokaler Download-Spiegel (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Jeden Dienst verbinden](#connecting-each-service)
  - [Erneuerung des Ausweises](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ ohne grafische Benutzeroberfläche CLI](#headless-cli)
- [🛡️ Sicherheitsvorkehrungen](#safety-rails)
- [🗃️ Caching und Songarchiv](#caching-song-archive)
  - [Zuordnungen auflösen](#resolve-mappings)
- [🧱 Projektlayout](#project-layout)
- [🩺 Fehlerbehebung](#troubleshooting)
- [📄 Lizenz](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Funktionen

SongMirror sorgt dafür, dass Ihre Wiedergabelisten überall identisch sind, ohne dass Sie sie manuell erneut hinzufügen, einzeln kopieren oder einen kostenpflichtigen Cloud-Dienst verwenden müssen, der Ihre Bibliothek speichert. Es ist plattformübergreifend, selbst gehostet und Open Source.

- 🔁 **Echte Spiegelung, nicht nur Anhängen** – Hinzufügungen und Entfernungen. Wählen Sie eine Quelle der Wahrheit (standardmäßig Spotify) und die anderen folgen dieser.
- ⇆ **Autorisierende Gruppen** – vertrauen Sie zwei oder mehr Diensten (zum Beispiel Spotify + Apple Music), während jeder andere ausgewählte Dienst ein reiner Zielspiegel bleibt.
- ⇄ **Bidirektionale N-Wege-Synchronisierung** – ein Hinzufügen oder Entfernen eines verbundenen Dienstes wird echofrei hinter Entfernungsschutz an alle anderen weitergegeben.
- ⇉ **Synchronisierung der Zusammenführung mehrerer Quellen** – Planen Sie die deduplizierte Zusammenführung von Bibliotheks-Playlists und öffentlichen Playlist-URLs an einem Ziel, ohne die öffentlichen Listen zu speichern oder ihnen zu folgen.
- ♥ **Gefällt mir und Lieblingstitel** – synchronisieren Sie die integrierte Like-Sammlung jedes Dienstes über alle sieben Musikanbieter hinweg, entweder in die eigenen Favoriten des Ziels oder in eine neu benannte Playlist.
- 🎯 **genaue Zuordnung nach ISRC** – genaue Aufnahmeidentität, sofern verfügbar, mit ungefähren Unicode-kompatiblen Titel-/Künstler-/Dauer-Fallbacks (Unterschiede bei den Credits der vorgestellten Künstler, „- 2015 Remaster“-Suffixe, nicht-lateinische Skripte, reine Video-Uploads – alles wird behandelt).
- 🎛️ **Mehrere benannte Synchronisierungen** – richten Sie so viele unabhängige Synchronisierungen ein, wie Sie möchten, jede mit eigenen Diensten, Wiedergabelisten, Zeitplänen und Sicherheitsbeschränkungen.
- ↪️ **einmalige Übertragungen** – Kopieren Sie jede Wiedergabeliste von einem Dienst zu einem anderen mit einem Live-Fortschrittsbalken; Sie können den Kopiervorgang anhalten, fortsetzen oder stoppen und nicht übereinstimmende Titel manuell auflösen.
- 🕒 **Tracks anhängen oder Trackreihenfolge beibehalten** – Kopien landen standardmäßig schnell und additiv am Ende des Ziels. Aktivieren Sie „Zuletzt hinzugefügte Reihenfolge beibehalten“, um die Titel nach dem ältesten neuen neu zu schreiben, sodass die Reihenfolge des hinzugefügten Datums mit der Quelle übereinstimmt.
- 🔗 **Von einem Link übertragen** – fügen Sie eine öffentliche Playlist-URL von einem beliebigen verbundenen Dienst ein und kopieren Sie sie direkt rüber. Sie müssen es nicht erst speichern oder befolgen.
- 🌐 **Gefolgte Playlists** – Synchronisieren und übertragen Sie Playlists, denen Sie folgen, die Sie aber nicht besitzen, und nicht nur die, die Sie erstellt haben.
- 📦 **Geplante Metadatensicherungen** – Archivieren Sie die gesamte Playlist-Bibliothek eines Kontos nach eigenem Zeitplan unter persistenten App-Daten, mit JSON/XML, Aufbewahrungsgrenzen und sichtbarem Erfolgs-/Fehlerverlauf. einmalige Downloads und importfähige Soundiiz JSON bleiben ebenfalls verfügbar.
- 💿 **Lokaler Download-Spiegel** – Offline-Audio behalten, ein Ordner pro Playlist im `AlbumArtist/Album`-Layout von Jellyfin, mit Covern und einem automatisch aktualisierten `.m3u8`.
- 🛡️ **Sicherheitsvorkehrungen** – Simulation standardmäßig, Hinzufügen/Entfernen-Obergrenzen pro Durchgang, Netzverlustschutz, Leer-Snapshot-Schutz, Abbruch ohne Schreiben, wenn Token ablaufen.
- 🗃️ **Ständig wachsendes Songarchiv** – jeder jemals gesehene Titel wird in einer lokalen SQLite-Datenbank aufgezeichnet (Name, Künstler, Album, ISRC, rohe Metadaten, zuerst/zuletzt gesehen).
- 🧭 **Bearbeitbarer Übereinstimmungsverlauf** – durchsuchen, korrigieren und löschen Sie alle zwischengespeicherten Track-Übereinstimmungen pro Dienst auf der Seite „Zuordnungen“, einschließlich der „Keine Übereinstimmung“-Ergebnisse, die andernfalls für immer unübertroffen bleiben würden.
- 🐳 **Läuft überall** – ein `docker compose up -d` für die Browser-App oder einfaches CLI + Cron / Task Scheduler.

> [!IMPORTANT]
> Von Natur aus selbst gehostet und privat. Ihre Abhördaten und Zugangsdaten verlassen niemals Ihren Computer. Die Web-Benutzeroberfläche verfügt über keine Authentifizierung – binden Sie sie an Ihre LAN und leiten Sie sie nicht an das Internet weiter.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Screenshots

<div align="center">

**Ein Dashboard für jede Bibliothek – Synchronisierungsstatus, Jobs, Live-Aktivität und Dienstzustand**

<img src="../../.github/assets/dashboard.png" alt="SongMirror Dashboard mit Synchronisierungsstatus, konfigurierten Jobs, Live-Aktivität und Zustand für Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music und Jellyfin" width="82%">

**Richten Sie in einem kurzen Assistenten eine beliebige Anzahl von Synchronisierungen ein – unidirektional, Zusammenführung mehrerer Quellen, autorisierende Gruppe oder bidirektional**

<img src="../../.github/assets/sync-wizard.png" alt="Der SongMirror-Setup-Assistent wählt Dienste für eine bidirektionale Synchronisierung über Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music und aus YouTube Music" width="82%">

**Verbinden Sie jeden Dienst in Ihrem Browser – mit einem Klick OAuth, geführtem Token-Einfügen oder einer API-Taste**

<img src="../../.github/assets/accounts.png" alt="Die Seite „Konten“ zum Verbinden von Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music und Jellyfin" width="82%">

**Durchsuchen und koppeln Sie Wiedergabelisten dienstübergreifend**

<img src="../../.github/assets/playlists.png" alt="Durchsuchen Sie Playlists über verbundene Dienste mit Cover-Art und Titelanzahl" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Schnellstart

Der schnellste Weg, es auszuführen, ist Docker – Compose ruft das veröffentlichte Bild ab, stellt die Web-Benutzeroberfläche bereit und führt Ihre Synchronisierungen termingerecht aus.

Für eine dauerhafte Installation mit automatischen Neustarts:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Oder probieren Sie das öffentliche GHCR-Image direkt aus, ohne das Repository zu klonen:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Öffnen Sie dann `http://localhost:8888` und verbinden Sie Ihre Dienste im Browser. Das Compose-Setup benötigt zum Starten kein `.env`; Alles wird in der Benutzeroberfläche konfiguriert und unter `./data` gespeichert.

Die direkte Option `docker run` ist wegwerfbar: `docker stop songmirror` entfernt den Container und seine Konfiguration. Verwenden Sie Compose für eine dauerhafte Installation mit dauerhaften Anmeldeinformationen, Caches und Downloads, oder sehen Sie sich [Leitfaden für Containerbilder](../docker-image.md) für Tags und Digest-Pinning an.

Möchten Sie es lieber ohne Docker ausführen?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Erfordert [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Für den lokalen Download-Spiegel auch `uv tool install spotdl` und `ffmpeg` im PATH.

<a id="app-language"></a>

### App-Sprache

SongMirror unterstützt Englisch, Arabisch, Türkisch, Spanisch, vereinfachtes Chinesisch, Französisch, Portugiesisch, Deutsch, Japanisch, Hindi, Bengali, Indonesisch, Koreanisch, Italienisch und Vietnamesisch. Beim ersten Start werden die Spracheinstellungen des Browsers der Reihe nach geprüft, einschließlich regionaler Varianten. Die erste unterstützte Sprache wird verwendet; wird keine gefunden, erscheint die Oberfläche auf Englisch. Ändern Sie die Sprache unter **Einstellungen → Allgemein → Sprache**. Ihre Auswahl wird in diesem Browser gespeichert und bleibt nach dem Neuladen erhalten. Mit **Automatisch (Browser)** folgen Sie wieder den Browsereinstellungen. Die arabische Oberfläche wird von rechts nach links dargestellt. Playlist-, Künstler- und Anbieternamen, Zugangsdaten sowie Diagnoseprotokolle behalten ihre ursprünglichen Werte.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Läuft immer: Docker

Der Docker-Container ist die empfohlene Bereitstellung: Er stellt die Web-Benutzeroberfläche bereit, führt Ihre Synchronisierungen nach ihren Zeitplänen aus und startet mit dem Host neu. Compose ruft `ghcr.io/ahnafnafee/songmirror:latest` ab, führt es als `songmirror` aus und behält alle Authentifizierungs- und Caches in `./data` bei.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Führen Sie zum Aktualisieren `docker compose up -d --pull always` aus. Um stattdessen den aktuellen Checkout zu erstellen, führen Sie `docker compose up -d --build` aus. Siehe [Leitfaden für Containerbilder](../docker-image.md) für Tags, Digest-Pinning, direkte Pulls, Verifizierung, Aktualisierungen und Rollback.

Zum Starten ist kein `.env` erforderlich – alles wird im Browser konfiguriert und unter `./data` gespeichert. OAuth, Partner-Token und API-Schlüssel-Setup sind alle live auf der Seite „Konten“ verfügbar. Jeder Assistent erläutert die dienstspezifischen Voraussetzungen und den genauen Rückruf-URI. Erstellen Sie dann Ihre Synchronisierungen auf der Seite „Synchronisierung“.

Das Öffnen von SongMirror von einem anderen Computer aus funktioniert bei `http://<server>:8888`. Die Standardverbindung Spotify verwendet eine eingefügte Websitzung `sp_dc` und benötigt daher keine Entwickler-App oder Rückruf-URL. Wenn Sie absichtlich die Legacy-Entwickler-App OAuth Fallback hinter Docker oder einen Reverse-Proxy verwenden, legen Sie die im Browser sichtbare Basis-URL in `.env` fest:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror wirbt dann für `https://music.example.com/oauth/spotify/callback`; Registrieren Sie genau diesen URI im App-Dashboard Spotify und erstellen Sie den Container mit `docker compose up -d --force-recreate` neu. Ein Reverse-Proxy-Basispfad wird ebenfalls unterstützt (z. B. `https://example.com/songmirror`). [Spotify erfordert HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) für jede Nicht-Loopback-Weiterleitung; Plain HTTP wird nur mit wörtlichen Loopback-Adressen wie `127.0.0.1` akzeptiert, nicht mit einer LAN IP oder `localhost`.

| | |
| --- | --- |
| Bild | `ghcr.io/ahnafnafee/songmirror:latest` unterstützt AMD64 und ARM64. Jeder Build wird außerdem mit einem Commit-spezifischen `sha-...`-Tag veröffentlicht; Git-Tags wie `v1.2.3` veröffentlichen zusätzlich `1.2.3`, `1.2` und `1`. Verwenden Sie [Leitfaden für Containerbilder](../docker-image.md), um einen unveränderlichen Digest anzupinnen. |
| Hafen | Die Benutzeroberfläche wird auf Host 8888 veröffentlicht (die `8888:8080`-Zuordnung in `docker-compose.yml`; bei Konflikten die Hostseite ändern). LAN-only – keine Portweiterleitung ins Internet; Die Benutzeroberfläche verfügt noch über keine Authentifizierung. |
| Beharrlichkeit | `./data` enthält Anmeldeinformationen, Token, Caches, das Songarchiv und geplante Playlist-Snapshots unter `playlist_backups/`. Sichern Sie es, um Ihr Setup und Ihre Archive auch bei Neuerstellungen beizubehalten. |
| Downloads | Setzen Sie `DOWNLOAD_DIR` (in `.env` oder Ihrer Shell) auf Ihr Host-Musikverzeichnis (z. B. `F:\Torrent\Music`); compose bind-mountet es an `/music`. Stellen Sie von Docker `JELLYFIN_URL` auf `http://host.docker.internal:8096` ein. |
| Abgelaufene Sitzungen | Erneuerbare Sitzungen werden beim nächsten geplanten oder manuellen Durchgang wiederhergestellt. TIDAL Web-Player-Sitzungen werden mit dem erfassten Aktualisierungstoken erneuert; Qobuz- und Apple Music-Tokens müssen bei Ablehnung immer noch erneut eingefügt werden. Es ist kein Neustart erforderlich. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ So funktioniert es

Bei jedem Durchgang für jeden ausgewählten Playlist-Namen, der in der Quelle vorhanden ist:

1. Machen Sie einen Snapshot der Quell-Playlist (Titel, ISRCs, Hinzufügungsdaten).
2. Gleichen Sie die gleichnamige Wiedergabeliste auf jedem ausgewählten, verbundenen Ziel gleichzeitig über die kontoautorisierte Wiedergabeliste dieses Dienstes API ab.
3. Fehlende Titel werden aufgelöst (zwischengespeicherte Links → ISRC → bewertete Suche) und die ältesten zuerst angehängt; Von der Quelle verschwundene Spuren werden hinter Wachen entfernt.
4. Optional synchronisiert [spotDL](https://github.com/spotDL/spotify-downloader) einen lokalen Audioordner pro Playlist.

Die Standardquelle der Wahrheit ist Spotify, aber der Einwegmodus ist anbieterunabhängig – stattdessen kann jeder verbundene Playlist-Peer die Quelle sein.

<a id="matching"></a>

### Passend

Dieselbe Hierarchie, die die dienstübergreifenden Tools verwenden ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): genaue Kennung → Suche → Fuzzy-Score.

1. Zwischengespeicherter Link – Sobald ein Quelltitel mit der Katalog-ID/Video-ID eines Ziels abgeglichen wird, wird dieser Link gespeichert und wiederverwendet (immun gegen Titeldrift).
2. ISRC – genaue Aufzeichnungsidentität, wo der Dienst sie offenlegt.
3. Bewertete Suche – [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, sowohl über den rohen als auch den romanisierten ([anyascii](https://github.com/anyascii/anyascii)) Titel und Künstler, verankert nach Dauer. Dies behandelt, ohne Hardcodierung:
   - Credits mehrerer Künstler – ein Dienst listet alle Funktionen auf, ein anderer listet die primären auf (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Titeldekoration – `(feat. …)`, `- 2015 Remaster`, `(From "…")`, zusätzliche Suffixe „Offizielles Musikvideo“.
   - Transliteration – Kyrillisch / Bengali / Griechisch / Arabisch (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Nur-Video-Titel – Die YouTube-Suche greift auf den `videos`-Filter für Indie-/OST-Titel zurück, die nur als Uploads auf YT verfügbar sind.

Der Daueranker schaltet die lockerere Titelübereinstimmung frei, sodass eine andere Version (`Runaway - Piano Version`) oder ein Cover mit falschem Interpreten nicht akzeptiert wird, wenn die Länge nicht übereinstimmt. Titel ohne sichere Übereinstimmung werden gemeldet und übersprungen.

<a id="multi-source-merge-sync"></a>

### Synchronisierung der Zusammenführung mehrerer Quellen

Ein Auftrag zum Zusammenführen von Quellen kombiniert eine oder mehrere explizite Wiedergabelisten in einem ausgewählten Ziel. Jede Quelle kann aus der Bibliothek eines verbundenen Kontos oder einer eingefügten URL eines öffentlichen Anbieters stammen; Letzteres wird einmalig in einen Anbieter und eine Playlist-ID aufgelöst, sodass die Playlist nicht gespeichert oder verfolgt werden muss und geplante Läufe keine beliebige URL wiedergeben.

- Eine Mitgliedschaftsunion – alle Mitgliedsgruppen werden gelesen, bevor das Ziel abgeglichen wird. Geteilte ISRCs sind eine Aufzeichnung; ohne ISRC, genaue/konservative Angaben zu Titel, Interpret, Version und Dauer werden Überlappungen dedupliziert.
- Deterministische Reihenfolge – zuerst die Priorität des Quelldeskriptors, dann die von jeder Quell-Playlist zurückgegebene Reihenfolge. Das erste Vorkommen besitzt die Zielposition und die Anzeigemetadaten; spätere Kopien ergänzen lediglich fehlende Identitätsmetadaten.
- Unionssichere Entfernungen – eine Zielspur kann nur entfernt werden, wenn bei einem vollständigen Durchgang festgestellt wird, dass sie in allen Bestandteilen fehlt. Eine fehlgeschlagene, abgeschnittene, fehlerhafte, nicht verfügbare oder unerkennbar leere Quelle deaktiviert jede Entfernung für diesen Durchgang, während sichere Hinzufügungen aus lesbaren Quellen weiterhin möglich sind.
- Standardmäßig nur „Nur anhängen“ – lassen Sie „Von jeder Quelle entfernte Titel entfernen“ deaktiviert, um alle Nur-Ziel-Titel beizubehalten. Durch Einschalten wird die normale Entfernungskappe pro Durchgang aktiviert, nachdem der Vollleseschutz bestanden wurde.

Merge-Jobs zielen derzeit auf eine Playlist eines Anbieters ab; Der separate Spotify-geführte lokale Download/Jellyfin-Spiegel ist für einen Sammelauftrag nicht verfügbar.

<a id="authoritative-groups"></a>

### Maßgebliche Gruppen

Verwenden Sie eine autorisierende Gruppe, wenn Sie aktiv dieselbe logische Playlist für zwei oder mehr Dienste kuratieren, aber möchten, dass jeder andere ausgewählte Dienst ihnen folgt. Ein typisches Setup ist Spotify + Apple Music als Autoritäten, mit TIDAL, Qobuz, Deezer, Amazon Music und YouTube Music als Spiegel.

- Die Mitgliedschaft kommt nur von Autoritäten – ein auf Spotify oder Apple Music hinzugefügter Track wird an die andere Autorität und jeden Spiegel weitergegeben. Eine Spur, die nur auf einem Spiegel hinzugefügt wird, ist Drift; es wird nie wieder in die Behörden importiert.
- Eine Bestellbehörde – wählen Sie aus, welche Behörde Playlist-Namen und die Reihenfolge der Ergänzungen bereitstellt. Die anderen Behörden tragen weiterhin Änderungen bei der Mitgliedschaft bei.
- Bestätigte Entfernungen werden von beiden Behörden weitergegeben – eine Abwesenheit muss in zwei aufeinanderfolgenden vollständigen Lesevorgängen auftreten, bevor etwas gelöscht werden kann. Eine gleichzeitige Hinzufügung auf Autoritätsseite gewinnt gegenüber einer Entfernung.
- Spiegel bekommen nie eine Stimme – das Löschen eines Tracks von einem Spiegel repariert diesen Spiegel; Der Titel von Spotify oder Apple Music wird nicht gelöscht.
- Sicherer erster Durchgang – jeder Autoritätssatz hat seine eigene Basislinie. Sein erster erfolgreicher Durchgang fügt möglicherweise fehlende Spuren hinzu, hält aber alle Entfernungen zurück, bis ein späterer Durchgang beweist, dass die Grundlinie stabil ist.
- Fehler beim Schließen: Wenn eine Autorität getrennt oder nicht lesbar ist oder ihre Wiedergabeliste nicht geöffnet/erstellt werden kann, wird diese logische Wiedergabeliste übersprungen, anstatt stillschweigend auf weniger Autoritäten zurückzugreifen.

Löschungen müssen ausdrücklich aktiviert werden und unterliegen weiterhin einer Obergrenze. Aktivieren Sie für den Auftrag **Löschungen synchronisieren**, oder setzen Sie `MAX_REMOVALS` beim Betrieb ohne grafische Oberfläche, wenn überzählige Titel aus den Spiegeln entfernt werden sollen, damit sie der maßgeblichen Titelmenge entsprechen.

<a id="bidirectional-n-way-sync"></a>

### Bidirektionale (N-Wege) Synchronisierung

Standardmäßig ist ein Anbieter die Quelle der Wahrheit und Änderungen erfolgen in eine Richtung. Im N-Wege-Modus ist jeder ausgewählte Anbieter ein Peer: Fügen Sie auf einem beliebigen Anbieter einen Track hinzu oder entfernen Sie ihn, und die Änderung wird auf die anderen übertragen.

Eine bidirektionale Synchronisierung ist zustandslos nicht möglich, daher wird die kanonische Mitgliedschaft jeder logischen Wiedergabeliste nach jedem sauberen Durchgang erfasst. Jeder Durchgang vergleicht jeden Anbieter mit diesem Snapshot, vereint die Änderungen und gleicht alle mit dem Ergebnis ab:

- Echofrei – ein propagiertes Hinzufügen wird Teil des Snapshots, sodass es nie zurückgesendet wird.
- Add-wins bei Konflikten – einen Song zu verlieren ist schlimmer, als einen zusätzlichen zu behalten.
- Read-Collapse-Schutz – Wenn ein Anbieter plötzlich weit weniger Titel als die Grundlinie liest (ein vorübergehender API-Schluckauf), wird dieser Durchgang übersprungen, sodass ein fehlerhafter Lesevorgang nicht zu einem Massenlöschvorgang führen kann.
- Gleiche Sicherheitsvorkehrungen wie bei der Einwegausführung – pro Durchgang `MAX_ADDS` / `MAX_REMOVALS` Obergrenzen und Netzverlustschutz auf jeder Schreibseite.
- **Löschungen müssen aktiviert werden**: `MAX_REMOVALS` ist standardmäßig 0. Verschwindet ein Titel bei einem Anbieter, weil er dort gelöscht oder aus Lizenzgründen entfernt wurde, bleibt er bei den anderen erhalten; die Änderung wird nur protokolliert. Legen Sie eine Obergrenze fest oder aktivieren Sie **Löschungen synchronisieren** in der Oberfläche, um Löschungen weiterzugeben.

> Immer zuerst Simulation. Ohne `--execute` ausführen (oder Vorschau in der Benutzeroberfläche verwenden) und den Plan lesen – er druckt jedes vorgeschlagene Hinzufügen/Entfernen für jeden Anbieter aus, bevor etwas geschrieben wird.

<a id="liked-and-favorite-tracks"></a>

### Gefallene und Lieblingstitel

Wählen Sie im Schritt „Wiedergabelisten“ einer Synchronisierung die integrierte „Gefällt mir“-Sammlung des Quelldienstes aus. SongMirror fragt dann, wo es an jedem ausgewählten Ziel abgelegt werden soll: direkt in die eigene Lieblings-/Lieblingssammlung dieses Dienstes oder in eine neue Playlist, deren vorgeschlagener Name Sie bearbeiten können. Eine neue Auswahl ist nur mit „Gefällt mir“ gekennzeichnet; Aktivieren Sie „Auch jede reguläre Playlist synchronisieren“ oder wählen Sie einzelne Playlists aus, um beide einzuschließen.

Das funktioniert mit den als „Gefällt mir“ markierten Songs bei Spotify, den Lieblingstiteln bei TIDAL/Qobuz/Deezer, den mit „Gefällt mir“ markierten Songs bei Amazon Music, den Lieblingssongs bei Apple Music und der mit „Gefällt mir“ markierten Musik bei YouTube Music. Es gelten dieselben Abgleichverfahren für einseitige Synchronisierung, Gruppen maßgeblicher Quellen und N-Wege-Synchronisierung sowie dieselben Sicherheitsgrenzen. Wie bei gewöhnlichen Wiedergabelisten bleiben Löschungen standardmäßig deaktiviert, bis **Löschungen synchronisieren** aktiviert wird.

TIDALs angemeldeter Web-Player-Zuschuss verwaltet sowohl normale Wiedergabelisten als auch native Lieblingstitel, wenn er `r_usr` und `w_usr` trägt. Durch das Erfassen der vollständigen Antwort auf das Anmeldetoken erhält SongMirror das Aktualisierungstoken sowie das kurzlebige Bearer, sodass die Sitzung automatisch erneuert werden kann.

Einige dieser Integrationen nutzen die Erstanbieter-Webschnittstellen der Anbieter und können ohne Vorankündigung geändert werden; Der [Machbarkeitsbewertung](../design/2026-09-01-liked-tracks-sync-feasibility.md) zeichnet den API und die Verteilungsbeschränkungen für jeden Anbieter auf.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Sicherungen der Playlist-Metadaten

Für Backups ist kein zweiter Anbieter oder Synchronisierungsauftrag erforderlich:

- Klicken Sie unter „Einstellungen“ → „Playlist-Backups“ oben auf „Backup hinzufügen“, um ein verbundenes Konto hinzuzufügen. Wählen Sie JSON oder XML und dann eine Häufigkeit, z. B. täglich oder wöchentlich. Benutzerdefinierte Intervalle verwenden eine Zahl und eine Einheit. „Backups behalten“ bietet Aufbewahrungsvoreinstellungen, eine benutzerdefinierte Anzahl oder „Alle Backups“.
- Sicherungen sind standardmäßig auf `data/playlist_backups/<account-profile-id>/` (oder `/data/playlist_backups/<account-profile-id>/` in Docker) eingestellt. Klicken Sie für die integrierte Ordnerauswahl auf „Sicherungsordner“ oder wählen Sie „Pfad manuell eingeben“. Ein benutzerdefinierter Ordner erhält weiterhin einen separaten Unterordner für jedes Konto. Standardsicherungsordner verwenden stellt die Standardeinstellung wieder her. Das Ändern des Speicherorts wirkt sich auf zukünftige Backups aus. Alte Dateien bleiben dort, wo sie sind. „Aufbewahrung“ und „Neueste Version herunterladen“ gelten für den ausgewählten Speicherort. Durch das Entfernen eines Zeitplans werden gespeicherte Dateien niemals gelöscht.
- Einstellungen → Downloads & Jellyfin → Download-Ordner verwendet die gleiche integrierte Auswahl und manuelle Eingabe. Wählen Sie einen Ordner, auf den Ihre Jellyfin-Bibliothek zugreifen kann. Downloads folgen dem Zeitplan jeder aktivierten Synchronisierung auf der Registerkarte „Synchronisierung“. Der Picker zeigt konfigurierte Hostpfade an (z. B. `F:\Torrent\Music`), während ihre Docker-Zuordnung (`/music`) intern beibehalten wird. Vorhandene Download-Bereitstellungen bleiben unverändert. Zusätzliche Hostordner müssen zunächst als Docker-Bind-Mounts freigegeben werden; Wenn Sie einen nicht gemounteten Ordner auswählen, wird ein Fehler angezeigt und die aktuelle Einstellung bleibt unverändert.

- Auf derselben Einstellungskarte werden der nächste Lauf, die Anzahl der gespeicherten Snapshots, die letzte erfolgreiche Datei und Anzahl sowie der letzte Fehler angezeigt. „Jetzt sichern“ stellt einen sicheren On-Demand-Lauf in die Warteschlange; „Neueste herunterladen“ ruft den neuesten persistenten Snapshot ab.
- Verwenden Sie auf der Seite „Wiedergabelisten“ die Option „Exportieren“ auf einer Dienstkarte, um jede Wiedergabeliste von diesem Dienst in einer versionierten JSON- oder XML-Datei herunterzuladen.
- Öffnen Sie eine Playlist, um nur diese Playlist zu exportieren. Die Option Soundiiz folgt auf [Soundiizs dokumentierte JSON-Importform](https://soundiiz.com/data/fileExamples/playlistExport.json), sodass die heruntergeladene Titelliste über den Fluss „Wiedergabeliste importieren → Aus Datei importieren“ von Soundiiz hochgeladen werden kann.
- SongMirror JSON/XML behält die Reihenfolge und Namen der Wiedergabelisten sowie Titel-/Vorkommens-IDs des Anbieters, verfügbare ISRCs, Künstler, Alben, Albumtitelpositionen, Dauer, hinzugefügte Daten, Bildlinks und Markierungen für nicht verfügbare Einträge bei. Kataloggeister ohne ID bleiben im Backup, anstatt zu verschwinden. Dateien enthalten keine Cookies, Token, Anforderungsheader, Vorschauen oder Streaming-Datei-URLs.

Manuelle Exporte werden vom Browser auf das Gerät heruntergeladen, auf dem die Benutzeroberfläche ausgeführt wird. Geplante Exporte nutzen das vorhandene Anwendungsdatenvolumen, sodass kein zweiter Hostpfad oder Container-Mount erforderlich ist. Backup liest die Warteschlange hinter Synchronisierungen und Übertragungen, anstatt gleichzeitig auf Provider-Clients zuzugreifen. Mit dem Feld `schema_version` können zukünftige Versionen das verlustfreie Format weiterentwickeln, ohne dass alte Snapshots mehrdeutig werden.

<a id="built-in-folder-picker"></a>

### Integrierte Ordnerauswahl

Klicken Sie auf ein Ordnerfeld oder auf „Durchsuchen…“, um die integrierte Auswahl zu öffnen. Verwenden Sie zum Navigieren Orte, anklickbare Breadcrumbs, Zurück, Vorwärts und einen Ordner nach oben. Klicken Sie auf einen Ordner, um ihn auszuwählen. Doppelklicken Sie, drücken Sie die Eingabetaste oder verwenden Sie den Pfeil, um es zu öffnen. Die Suche filtert den aktuellen Ordner. Geben Sie einen Ordnerpfad ein, der eine vollständige Adresse akzeptiert. Ordner auswählen aktualisiert den Entwurf; Speichern Sie die Einstellungen oder planen Sie die Anwendung. Durch Abbrechen bleibt der Entwurf unverändert. Es ist kein Desktop-Helfer oder zusätzlicher Prozess erforderlich.

„Neuer Ordner“ erstellt einen benannten Unterordner am aktuell geöffneten Speicherort und öffnet ihn dann. Vorhandene Elemente werden niemals überschrieben. Das Abbrechen der Namenseingabe führt zu nichts; Wenn Sie die Auswahl nach der Erstellung abbrechen, verbleibt der neue Ordner auf der Festplatte. Ihr gespeicherter Backup- oder Download-Speicherort ändert sich erst nach der Auswahl und dem Speichern. In Docker erklärt der Picker, welche Pfade gemeinsam genutzt werden und zeigt sowohl den Containerpfad als auch den konfigurierten Computerpfad an, sofern verfügbar.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Lokaler Download-Spiegel (Jellyfin)

Behalten Sie über [spotDL](https://github.com/spotDL/spotify-downloader) eine Offline-Audiokopie jeder synchronisierten Wiedergabeliste, einen Ordner pro Wiedergabeliste. Bei der Synchronisierung handelt es sich um echte Spiegelung: Neue Titel werden heruntergeladen, entfernte Titel werden lokal gelöscht. Das Layout ist Jellyfin-ready – richten Sie eine Jellyfin-Musikbibliothek auf das Download-Verzeichnis und sowohl die Titel als auch die Wiedergabelisten werden angezeigt und bleiben bei jedem Durchgang aktualisiert:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Aktivieren Sie es, indem Sie `DOWNLOAD_DIR` einstellen und spotDL + ffmpeg installieren:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Inkrementell – nach dem ersten vollständigen Download werden nur neu hinzugefügte Titel abgerufen; Entfernte Titel (und ihre geleerten Albumordner) werden bereinigt. Ein unterbrochener Lauf wird im nächsten Durchgang fortgesetzt.
- Neueste zuerst `.m3u8` – in der Reihenfolge des hinzugefügten Datums geschrieben, das Neueste oben (stellen Sie `LOCAL_MIRROR_ORDER=oldest` zum Umdrehen ein). Erstellen Sie Cover/Tags/Mtimes aus vorhandenen Dateien mit `uv run main.py --refresh-local` neu.
- Playlist-Cover in Jellyfin – Jellyfin ignorieren eine Coverdatei neben einem m3u, also setzen Sie `JELLYFIN_URL` + `JELLYFIN_API_KEY` und jeder Durchgang lädt das echte Playlist-Cover über Jellyfin API hoch.
- Audioqualität – die Quelle ist YouTube, also ohne ein YT Music Premium-Cookie liegt die Obergrenze bei ~128–160 kbps. `LOCAL_MIRROR_FORMAT=opus` behält den nativen Stream von YouTube ohne eine MP3-Neukodierung; Ein Premium-Cookie (`LOCAL_MIRROR_COOKIE_FILE`) schaltet 256 kbps AAC frei. Durch Auswahl von `flac` wird der Ausgabecontainer geändert, eine verlustbehaftete Quelle kann jedoch nicht in verlustfreies Audio umgewandelt werden.

Der aktuelle FLAC-Pfad von Monochrome verwendet browsergesteuerte, einmal verwendbare Wiedergaberessourcen anstelle eines stabilen, vom Anbieter autorisierten Dateiexports API, sodass SongMirror ihn nicht automatisiert. Verwenden Sie den lokalen Spiegel nur für Inhalte, deren Eigentümer Sie sind oder die Sie anderweitig kopieren dürfen.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Jeden Dienst verbinden

In der Web-App führt Sie die Seite „Konten“ durch die einzelnen Dienste und zeigt die genauen Werte zum Einfügen an. Nichts wird durch Dritte vermittelt.

<a id="credential-renewal"></a>

### Erneuerung des Ausweises

SongMirror aktualisiert Anmeldeinformationen rechtzeitig, nicht mit einem separaten Token-Aktualisierungs-Timer. Jeder manuelle oder geplante Synchronisierungsdurchlauf validiert die verwendeten Connectors und erneuert unterstützte Zugriffstoken vor der ersten Anfrage (oder einmal nach einer Authentifizierungsablehnung). Es ist normal, dass ein kurzlebiges Zugriffstoken zwischen den Durchgängen abläuft – entscheidend ist das dauerhafte Aktualisierungstoken oder das Erneuerungscookie. Die Seite „Konten“ überprüft den Status, wenn sie geladen wird oder den Fokus wiedererlangt, es handelt sich jedoch nicht um die Sitzungswartung im Hintergrund. aktivierte Synchronisierungszeitpläne sind.

| Service | Erneuerungsverhalten |
| --- | --- |
| Spotify | Die Standardverbindung prägt bei Bedarf ein Web-Player-Zugriffstoken aus dem gespeicherten `sp_dc`-Cookie und versucht es nach einem `401` erneut mit einem neuen Token; Die zugrunde liegende Anmeldesitzung kann weiterhin widerrufen werden. Die ältere Entwickler-App OAuth wird weiterhin für bestehende Installationen unterstützt. |
| TIDAL | Das importierte Web-Player-Zugriffstoken erneuert sich automatisch um `auth.tidal.com` unter Verwendung des Aktualisierungstokens aus der Anmeldeantwort. SongMirror behält das vorhandene Aktualisierungstoken bei, wenn eine Antwort es weglässt, und behält ein rotiertes Token bei, wenn TIDAL eines zurückgibt. Beim Abmelden oder Widerrufen ist weiterhin eine erneute Erfassung erforderlich. |
| Qobuz | Das eingefügte `X-User-Auth-Token` wird verwendet, bis Qobuz es ablehnt, dann muss es erneut erfasst werden. |
| Deezer | Die kurzlebige Pipe JWT erneuert sich automatisch von der gespeicherten `refresh-token` vor der Verwendung und einmal nach einer `401/403`; Der gedrehte Erneuerungsstatus wird beibehalten. |
| Amazon Music | Das Webzugriffstoken erneuert sich um `/pandaToken` unter Verwendung des erfassten Browser-Benutzeragenten, des Referrers und der auf der Zulassungsliste aufgeführten Cookies. Der aktuelle `POST config.json?skipToken=false`-Flow führt bei Bedarf einen Bootstrapping-Gerätekontext durch und rotierte Cookies bleiben bestehen. Abmelden, Sicherheitsänderungen oder serverseitige Sperrung erfordern weiterhin eine erneute Erfassung. |
| Apple Music | Die eingefügten Bearer und Media-User-Token können bis SongMirror nicht erneuert werden und müssen nach der Ablehnung erneut erfasst werden. |
| YouTube Music | Data API OAuth wird automatisch innerhalb von 60 Sekunden nach Ablauf aktualisiert. Der Browsermodus versucht, die Cookie-Rotation von Google immer dann durchzuführen, wenn ein Synchronisierungsziel erstellt wird. Eine bereits abgelaufene Browsersitzung muss erneut exportiert werden. |
| Jellyfin | Der Schlüssel API hat keinen Zugriffstoken-Aktualisierungszyklus; Ersetzen Sie es nur, wenn es widerrufen oder gelöscht wird. |

<a id="spotify"></a>

### Spotify

1. Melden Sie sich unter <https://open.spotify.com> an.
2. Öffnen Sie den Browser DevTools (`F12`) → Anwendung (Chrome/Edge) oder Speicher (Firefox) → Cookies → `https://open.spotify.com`.
3. Kopieren Sie den Wert des Cookies `sp_dc` und fügen Sie ihn in Konten → Spotify ein.

Diese einzelne angemeldete Websitzung übernimmt das Durchsuchen der Bibliothek, das Lesen und Schreiben von Wiedergabelisten sowie die Katalogsuche. Es ist keine Spotify-Entwickler-App, kein API-Schlüssel und kein Premium-Konto erforderlich. Behandeln Sie `sp_dc` wie ein Passwort: SongMirror speichert es in seinem privaten Datenverzeichnis, aber die Integration verwendet die internen Web-Player-Vorgänge von Spotify und muss möglicherweise gewartet werden, wenn Spotify diese ändert. Vorhandene Entwickler-App-Anmeldeinformationen OAuth bleiben ein kompatibler Fallback.

<a id="tidal"></a>

### TIDAL

1. Öffnen Sie [TIDALs Webplayer](https://listen.tidal.com), öffnen Sie DevTools → Netzwerk und aktivieren Sie Protokoll beibehalten.
2. Melden Sie sich ab und wieder an und filtern Sie dann die Netzwerkliste nach `oauth2/token`.
3. Wählen Sie die erfolgreiche `auth.tidal.com/v1/oauth2/token`-Anfrage aus. Kopieren Sie in Payload (Chrome/Edge) oder Request (Firefox) den Formularwert `client_id` in das Web-Player-Client-ID-Feld von SongMirror.
4. Öffnen Sie die Registerkarte „Antwort“ der Anfrage und kopieren Sie die vollständige JSON in die Web-Player-Token-Antwort. Es sollte sowohl `access_token` als auch `refresh_token` enthalten.
5. Verbinden. SongMirror übt die Aktualisierungsgewährung sofort aus und weigert sich, den Erfolg zu melden, wenn diese Client-ID sie nicht erneuern kann.

Bei der Client-ID OAuth handelt es sich um Anforderungsmetadaten und nicht um den numerischen Anspruch `cid` im Zugriffstoken von TIDAL. SongMirror extrahiert nur das Zugriffstoken, Aktualisierungstoken, Client-ID, Bereiche, Ablauf und Katalogland; Nicht verwandte Antwortdaten werden verworfen. Es erneuert sich kurz vor Ablauf und einmal nach einer Authentifizierungsablehnung bis `https://auth.tidal.com/v1/oauth2/token`, wobei die Rotation des Aktualisierungstokens erhalten bleibt. Das ältere OpenAPI-Request-Header-Einfügen bleibt kompatibel, aber da es kein Aktualisierungstoken enthält, muss es nach Ablauf dennoch erneut eingefügt werden. Es werden nur Katalogmetadaten und die Playlists des angemeldeten Benutzers verwendet – Playback-Assets bleiben von dieser Integration ausgeschlossen.

<a id="qobuz"></a>

### Qobuz

Melden Sie sich unter <https://play.qobuz.com> an, öffnen Sie DevTools → Netzwerk und filtern Sie nach `api.json/0.2`. Wählen Sie eine beliebige Anfrage aus, die `X-App-Id` und `X-User-Auth-Token` enthält – einschließlich einer authentifizierten `album/story`-Anfrage –, kopieren Sie dann deren Anfrageheader oder kopieren Sie sie als cURL und fügen Sie sie in den Assistenten ein. SongMirror behält nur diese beiden Werte bei, sendet sie mit demselben Header-basierten Fluss wie der Webplayer und verwirft Cookies und nicht verwandte Browser-Metadaten. Es ist keine geschäftliche API-Genehmigung oder Benutzer-ID erforderlich; Vorhandene Partneranmeldeinformationen bleiben ein kompatibler Umgebungs-Fallback.

Der Adapter verwendet nur Endpunkte für die Katalogsuche und Wiedergabelisten – er fordert keine Stream- oder Datei-URLs an.

<a id="deezer"></a>

### Deezer

Melden Sie sich unter <https://www.deezer.com> an, öffnen Sie DevTools → Netzwerk und laden Sie die Seite neu. Filtern Sie nach `auth.deezer.com/login/renew`, kopieren Sie die Header dieser Anfrage (oder kopieren Sie sie als cURL) und fügen Sie sie in das Erneuerungsfeld ein. Firefox kann stattdessen die Anforderungscookies als einfachen, durch Semikolons getrennten Block kopieren; diese Form wird auch akzeptiert. SongMirror behält nur das dedizierte Cookie `refresh-token` und verwendet es, um Deezers kurzlebige Pipe JWT automatisch zu erneuern. Sie können auch eine aktuelle `pipe.deezer.com/api`-Anfrage als sofortigen Bootstrap einfügen, dies ist jedoch nicht erforderlich, wenn die Erneuerung konfiguriert ist. Sowohl das Hinzufügen als auch das Entfernen von Playlists nutzen die erneuerbare Pipe-Sitzung. Es ist kein `arl`-Cookie erforderlich. Vorhandene Entwickler-Token OAuth bleiben ein kompatibler Umgebungs-Fallback.

<a id="amazon-music"></a>

### Amazon Music

Für den Standard-Connector ist keine Entwicklergenehmigung erforderlich. Es verwendet dieselben authentifizierten GraphQL- und Token-Erneuerungsrouten wie der Amazon Music-Webplayer:

1. Melden Sie sich unter <https://music.amazon.com> an und öffnen Sie DevTools → Netzwerk.
2. Laden Sie die Seite neu, filtern Sie nach `config.json` und wählen Sie die Anmeldeanforderung aus. (`pandaToken` funktioniert auch, wenn es angezeigt wird, ist aber nicht erforderlich.)
3. Wählen Sie „Anforderungsheader kopieren“ oder „Als cURL kopieren“ und fügen Sie es dann in das Verlängerungsfeld ein. Behalten Sie die vollständigen Header `User-Agent`, `Referer` und `Cookie` bei, damit SongMirror denselben Browserkontext wiedergeben kann.
4. Kopieren Sie optional die angemeldete `config.json`-Antwort in das Bootstrap-Feld. SongMirror kann diesen Gerätekontext normalerweise mithilfe der Erneuerungssitzung abrufen.

SongMirror leitet den gleichen Autorisierungswert `AmznMusic` lokal ab und aktualisiert ihn bis `music.amazon.com/pandaToken` vor Ablauf oder einmal nach einer Authentifizierungsablehnung. Während der Verbindung verwendet es die aktuelle Browser-Konfigurationsanfrage, wenn Gerätekontext benötigt wird, erfordert `/pandaToken`, um ein Zugriffstoken zu erstellen, und lehnt die Verbindung ab, wenn Amazon das Musik-Erneuerungscookie widerruft. Es speichert nur den Browser-Benutzeragenten, die Sprache, den Musik-Referer, eine benannte Zulassungsliste von Amazon-Authentifizierungs-/Sitzungscookies und einen begrenzten Musik-Client-Gerätekontext. Analysen, Experimente, AWS-Konsole, CSRF und andere nicht verwandte Browserdaten werden verworfen. Diese gespeicherten Cookies sind immer noch vertraulich, also halten Sie SongMirror privat auf Ihrem LAN. Eine Abmeldung, eine Passwort-/Sicherheitsänderung oder ein Widerruf auf Amazon-Seite kann dennoch eine erneute Erfassung erfordern.

Dies ist eine nicht unterstützte Web-Client-Schnittstelle eines Erstanbieters und Amazon kann sie ohne Vorankündigung ändern. Die dokumentierte [Amazon Music Web API](https://developer.amazon.com/docs/music/API_web_overview.html) ist immer noch eine geschlossene Beta; Genehmigte Partneranmeldeinformationen bleiben ein optionaler Fallback, wenn sie über Umgebungsvariablen konfiguriert werden.

<a id="apple-music"></a>

### Apple Music

Kein Apple Developer-Konto erforderlich – zwei Header von `music.apple.com` reichen aus. Öffnen Sie <https://music.apple.com>, melden Sie sich an, öffnen Sie DevTools → Netzwerk, spielen Sie ein Lied ab, filtern Sie nach `amp-api.music.apple.com` und kopieren Sie aus den Headern einer beliebigen Anfrage:

- `authorization: Bearer eyJ...` → Bearer Token (der Teil `eyJ...`, ohne `Bearer `)
- `media-user-token: ...` → Benutzer-Token (vollständiger Wert)

Mit dem Verbindungsassistenten können Sie die Rohheader einfügen und die Werte für Sie analysieren. Tokens der letzten Monate; Fügen Sie sie nach Ablauf erneut auf der Seite „Konten“ ein.

Eine Apple-ID ohne aktives Apple Music-Abonnement kann weiterhin eine Verbindung im Nur-Katalog-Modus herstellen. Fügen Sie in diesem Modus einen öffentlichen Apple Music-Playlist-Link in Transfers ein, um ihn in einen anderen verbundenen Dienst zu kopieren. Durchsuchen der Apple-Bibliothek, geplante Synchronisierung und die Verwendung von Apple Music als Übertragungsziel erfordern weiterhin die kostenpflichtige Berechtigung CloudLibrary; SongMirror zeigt diese Vorgänge als nicht verfügbar an, anstatt die gültigen Kataloganmeldeinformationen als abgelaufen zu behandeln.

<a id="youtube-music"></a>

### YouTube Music

Spricht mit dem offiziellen [YouTube Data API v3](https://developers.google.com/youtube/v3), dessen Aktualisierungstoken OAuth dauerhaft ist und Neustarts übersteht.

1. Erstellen Sie im [Google Cloud-Konsole](https://console.cloud.google.com) ein Projekt, aktivieren Sie YouTube Data API v3 und erstellen Sie einen OAuth-Client vom Typ „TVs“ und „Limited Input Devices“.
2. Legen Sie auf dem Zustimmungsbildschirm OAuth den Veröffentlichungsstatus → In Produktion fest (wenn Sie ihn auf „Testen“ belassen, läuft das Token nach 7 Tagen ab).
3. Fügen Sie in der App die Client-ID + das Geheimnis ein und geben Sie den Gerätecode auf dem Bildschirm ein.

> Kontingent: Data API erlaubt 10.000 Einheiten/Tag (eine Suche kostet 100, ein Hinzufügen/Entfernen 50). Die dauerhafte Wartung ist kostengünstig; Ein großer Rückstand beim ersten Mal kann die Obergrenze erreichen und am nächsten Tag wieder anhalten.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ ohne grafische Benutzeroberfläche CLI

Bevorzugen Sie `.env` + cron / Task Scheduler? Die gleiche Engine läuft ohne grafische Oberfläche.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Nützliche Flags:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Schlüsselumgebungsvariablen (siehe `.env.example`): die Anmeldeinformationen für die von Ihnen verwendeten Anbieter, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` und `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Sicherheitsvorkehrungen

Entfernungen sind destruktiv und werden daher bewacht:

- Simulation ist die Standardeinstellung – ohne `--execute` (oder die Real-Sync-Aktion der Benutzeroberfläche) ändert sich nichts.
- Wenn die Quelle 0 Titel für eine Wiedergabeliste zurückgibt, die das Ziel als nicht leer anzeigt, werden Entfernungen in diesem Durchgang übersprungen (ein vorübergehender API-Fehler kann eine Wiedergabeliste nicht leeren).
- **Löschungen sind standardmäßig deaktiviert**: `MAX_REMOVALS=0` hält jede Löschung zurück; sie wird protokolliert, aber nie ausgeführt. Eine Entfernung aus Lizenzgründen auf einer Plattform kann dadurch keine Löschkette auf anderen Plattformen auslösen. Aktivieren Sie pro Synchronisierung **Löschungen synchronisieren** oder setzen Sie `MAX_REMOVALS`. Auch danach gilt: Übersteigt die Anzahl ausstehender Löschungen in einem Durchlauf die Obergrenze, werden alle übersprungen und protokolliert.
- `MAX_ADDS` begrenzt jeden zeitstempelerzeugenden Schreibvorgang in einem Synchronisierungsdurchlauf, einschließlich der Chronologiereparatur. Wenn ein älteres wiederhergestelltes Spiel eine größere Suffix-Wiederholung erfordert, als die Obergrenze zulässt, verschiebt SongMirror es auf den nächsten Durchgang, anstatt es als neu erscheinen zu lassen oder einen riesigen Provider-Burst zu verursachen. Bei einer einmaligen Übertragung gibt es keinen nächsten Durchgang, sie wird also nie verschoben: Es wird jeder angeforderte Titel kopiert und in der Reihenfolge der Quelle angehängt, es sei denn, Sie schalten für diese Übertragung die Option „Zuletzt hinzugefügte Reihenfolge beibehalten“ ein, bei der die Reparaturkosten übernommen werden.
- Bei einer chronologischen Reparatur wird eine Duplikatkopie erstellt, bevor das Original gelöscht wird. Bei einem Dienst, dessen Löschvorgang jede Kopie eines Lieds erfordert, muss die Anzahl der Bewahrer stimmen. Deshalb liest Apple Music erneut, bis die bereitgestellten Kopien sichtbar sind, und weigert sich, etwas gegen einen Lesevorgang zurückzuziehen, der seinen eigenen Schreibvorgängen noch nachsteht. Deezer überspringt die Reparatur vollständig und hängt immer Folgendes an: Es gibt auch keine Positionseinfügung, daher ist die Wiederholung eines Befehls, den es nicht ausdrücken kann, das Risiko für das Ziel nicht wert. Auf dem Überweisungsformular wird der Bestellschalter ausgegraut und der Grund angegeben.
- Schutz vor Netzverlusten – ein zielseitiger Track, der einem Quelltrack ähnelt, der mit diesem Dienst nicht übereinstimmt, wird gehalten und nicht gelöscht.
- Bei einem Fehler bei der Anbieterauthentifizierung wird der Durchgang dieses Anbieters sofort abgebrochen – keine teilweisen Löschungen abgelaufener Token.
- Ein Zusammenführungsauftrag muss den Lesevorgang aller einzelnen Quellquellen abschließen, bevor er von seinem Ziel gelöscht werden kann. alle teilweisen/fehlgeschlagenen Quell-Snapshot-Forces, die in ein Nur-Anhängen-Verhalten übergehen.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Caching und Songarchiv

Alles, was auflösbar ist, wird zwischengespeichert, sodass Steady-State-Durchgänge nahezu augenblicklich erfolgen: Auflösungscaches pro Dienst (ISRC + Suche, einschließlich Fehlschlägen), ein Tracklisten-Cache mit `snapshot_id`-Schlüsseln, Links zu genauen Kennungen in SQLite und ein Snapshot-Überspringen pro Paar (`unchanged since last clean sync`).

Jeder Durchgang archiviert auch die Metadaten jedes Titels, den er sieht, in `song_cache.db` – einer SQLite-Datei, die immer größer wird. Entfernte Titel bleiben mit Name, Interpret, Album, Dauer, ISRC, Rohschnappschuss JSON und zuerst/zuletzt gesehenen Zeitstempeln archiviert:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Zuordnungen auflösen

Jeder Dienst behält seinen eigenen Auflösungscache und ordnet einen normalisierten `title|artist`-Schlüssel der Katalog-ID zu, mit der er übereinstimmte
diesen Dienst. Eine Übereinstimmung wird für immer wiederverwendet, ebenso wie ein „Keine Übereinstimmung“-Ergebnis, das dazu führt, dass ein Track fehlschlägt
einmal übereinstimmen, bei jedem späteren Durchlauf unübertroffen bleiben.

Die Seite „Zuordnungen“ in der Web-Benutzeroberfläche stellt diese Caches direkt für jeden Dienst bereit:

- Durchsuchen Sie den gesamten Cache nach Titel, Künstler oder aufgelöster ID
- Filtern Sie nach manuell festgelegten Einträgen (eine Übereinstimmung, die Sie im Übertragungskonflikteditor ausgewählt haben) oder nach Einträgen ohne Übereinstimmung
- Korrigieren Sie eine falsche ID, indem Sie den Link des richtigen Tracks einfügen, oder löschen Sie eine Zuordnung, damit sie beim nächsten Durchgang erneut angezeigt wird
- Löschen Sie jeden „Keine Übereinstimmung“-Eintrag für einen Dienst in einer Aktion, sodass eine Reihe fehlgeschlagener Suchvorgänge einen weiteren Versuch erhält

Wenn ein behobener Fehler später behoben wird, wird durch einfaches Anhängen das alte Lied als neu angezeigt. Für Playlist
Ziele, SongMirror spielt stattdessen dieses Lied und das bereits vorhandene neuere Suffix vom ältesten zum neuesten erneut ab und entfernt es dann
die älteren Exemplare. Die Anbieter gestatten den Kunden nicht, die ursprünglichen Zeitstempel wiederherzustellen, ihre Verwandten bleiben jedoch erhalten
Kürzlich hinzugefügte Bestellung. Native „Gefällt mir“-/Lieblingssammlungen bleiben der Mitgliedschaft vorbehalten und werden nie wiederholt.

Während eine Synchronisierung ausgeführt wird, werden Änderungen mit einer eindeutigen Meldung abgelehnt, da ein Durchgang den Cache für sie im Speicher hält
gesamten Dauer und würde sie nach Abschluss überschreiben.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Projektlayout

CLI-Eintrag: `uv run main.py` (dünne Unterlegscheibe) oder `python -m songmirror`. Webeintrag: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Einen weiteren Dienst hinzufügen: Unterklasse `MirrorTarget`, ~8 Methoden implementieren, seinen Builder zu `engine/targets`' `_REGISTRY` und seine Klasse zu `_CLASSES` hinzufügen und ein passendes `Connector` unter `services/accounts` hinzufügen. Der gesamte Abgleich – Differenz, Reihenfolge, Sicherheitsmaßnahmen, Protokollierung, Snapshot-Überspringen – wird vererbt.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Fehlerbehebung

- `Missing required environment variable` – füllen Sie `.env` (CLI) aus oder verbinden Sie den Dienst in der Benutzeroberfläche.
- TIDAL Berichte `Expired` – Melden Sie sich bei `listen.tidal.com` ab und wieder an und fügen Sie dann sowohl `client_id` aus der Anforderungsnutzlast `oauth2/token` als auch die vollständige Antwort JSON in Konten ein. Eine kopierte OpenAPI-Anfrage hat nur die kurzlebige Bearer und kann nicht verlängert werden.
- TIDAL meldet HTTP 429 – dies ist eine vorübergehende Ratenbegrenzung, keine abgelaufene Anmeldung. SongMirror berücksichtigt die Wiederholungsverzögerung des Anbieters und speichert Kontozustandsprüfungen zwischen, anstatt API wiederholt zu prüfen.
- Qobuz oder Apple-Berichte `Expired` / `401` / `403` – diese eingefügten Sitzungen haben kein erneuerbares Geheimnis; Erfassen Sie eine neue Anmeldeanfrage oder ein neues Token in den Konten.
- TIDAL besagt, dass das Token keinen Like-Track-Zugriff hat – erfassen Sie eine frisch angemeldete Web-Player-Token-Antwort mit `r_usr` und `w_usr`.
- Deezer Erneuerung schlägt fehl – Erfassen Sie eine neue `auth.deezer.com/login/renew`-Anfrage (oder deren `refresh-token`-Cookie). Eine aktuelle Pipe Bearer allein ist nur ein temporärer Bootstrap.
- Amazon Music Erneuerung schlägt fehl – Erfassen Sie eine neu angemeldete `POST /config.json?skipToken=false`-Anfrage mit ihren vollständigen `User-Agent`-, `Referer`- und `Cookie`-Headern. Die Antwort JSON ist optional.
- YouTube Music Browsermodus läuft ab – neue Browser-Anforderungsheader exportieren. Für die dauerhafteste unbeaufsichtigte Einrichtung verwenden Sie Data API OAuth mit einem Zustimmungsbildschirm für die Produktion.
- Spotify meldet abgelaufen – melden Sie sich erneut unter `open.spotify.com` an und fügen Sie ein neues Cookie `sp_dc` in „Konten“ ein.
- Eine Playlist wird nicht synchronisiert. Stellen Sie sicher, dass sie sich im Playlist-Bereich der Synchronisierung befindet und in der Quelle vorhanden ist (Ziele werden bei einem echten Durchgang automatisch erstellt).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Lizenz

Copyright © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Dieses Projekt ist [MIT](../../LICENSE) lizenziert.

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
