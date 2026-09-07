<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Sincronizzazione playlist self-hosted e sempre attiva per Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music e YouTube Music, oltre a un mirror audio locale pronto per Jellyfin.<br/>
Un'alternativa gratuita, open source e self-hosted a Soundiiz, TuneMyMusic e FreeYourMusic che possiedi e gestisci.

**Unione unidirezionale, multi-sorgente, gruppo autorevole o sincronizzazione bidirezionale completa (a N vie) · trasferimenti di playlist una tantum · corrispondenza accurata per ISRC · tutto dal tuo browser**

[Avvio rapido](#quick-start) · [Caratteristiche](#features) · [Schermate](#screenshots) · [Sempre in funzione: Docker](#always-running-docker) · [Come funziona](#how-it-works) · [Segnala un errore][github-issues-link] · [Proponi una funzionalità][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Condividi questo progetto**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Impostalo una volta: ogni playlist che curi rimane rispecchiata su ogni servizio, in ordine di data di aggiunta.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="Demo di SongMirror: rivelazione del logo, dashboard, configurazione di sincronizzazione unidirezionale e bidirezionale, trasferimenti di playlist dal vivo e corrispondenza accurata di ISRC tra sette servizi musicali" width="88%"></a>

<sup>▲ <a href="../../.github/assets/songmirror-demo.mp4">Guarda la versione 1080p</a></sup>

</div>

> [!NOTE]
> App Web + senza interfaccia grafica CLI, un motore. Fai clic sull'interfaccia utente del browser per connettere servizi, creare sincronizzazioni e trasferire playlist o eseguirlo `.env` + stile cron. Entrambi guidano lo stesso nucleo di sincronizzazione.

<details>
<summary><kbd>Indice</kbd></summary>

#### SOMMARIO

- [✨Caratteristiche](#features)
- [📸 Schermate](#screenshots)
- [🚀Avvio rapido](#quick-start)
  - [Lingua dell'app](#app-language)
- [🐳 Sempre in funzione: Docker](#always-running-docker)
- [⚙️ Come funziona](#how-it-works)
  - [Corrispondenza](#matching)
  - [Sincronizzazione dell'unione multi-origine](#multi-source-merge-sync)
  - [Gruppi autorevoli](#authoritative-groups)
  - [Sincronizzazione bidirezionale (N-vie).](#bidirectional-n-way-sync)
- [📦 Backup dei metadati della playlist](#playlist-metadata-backups)
- [💿 Mirror di download locale (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Collegamento di ogni servizio](#connecting-each-service)
  - [Rinnovo credenziali](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ senza interfaccia grafica CLI](#headless-cli)
- [🛡️Tutele di sicurezza](#safety-rails)
- [🗃️ Memorizzazione nella cache e archivio di brani](#caching-song-archive)
  - [Risolvere le mappature](#resolve-mappings)
- [🧱Impaginazione del progetto](#project-layout)
- [🩺 Risoluzione dei problemi](#troubleshooting)
- [📄 Licenza](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨Caratteristiche

SongMirror mantiene le tue playlist identiche ovunque senza dover aggiungere nuovamente manualmente, copiare uno per uno o un servizio cloud a pagamento che conserva la tua libreria. È multipiattaforma, self-hosted e open source.

- 🔁 **Mirroring vero, non solo aggiunta**: aggiunte e rimozioni. Scegli una fonte di verità (Spotify per impostazione predefinita) e le altre la seguono.
- ⇆ **Gruppi autorevoli**: fidati di due o più servizi (ad esempio Spotify + Apple Music) mentre ogni altro servizio selezionato rimane un mirror solo di destinazione.
- ⇄ **Sincronizzazione bidirezionale a N vie**: un'aggiunta o una rimozione su qualsiasi servizio connesso si propaga a tutti gli altri, senza eco, dietro le protezioni di rimozione.
- ⇉ **Sincronizzazione unione multi-sorgente**: pianifica l'unione deduplicata delle playlist della libreria e degli URL delle playlist pubbliche in un'unica destinazione, senza salvare o seguire gli elenchi pubblici.
- ♥ **Tracce apprezzate e preferite**: sincronizza la raccolta di apprezzamenti integrata di ciascun servizio tra tutti e sette i fornitori di musica, nei preferiti della destinazione o in una playlist con un nuovo nome.
- 🎯 **corrispondenza accurata per ISRC** — identità esatta della registrazione, ove disponibile, con titoli di riserva/artista/durata approssimativamente compatibili con Unicode (differenze nei crediti degli artisti in primo piano, suffissi "- 2015 Remaster", script non latini, caricamenti di soli video: tutto gestito).
- 🎛️ **Sincronizzazioni con nomi multipli**: configura tutte le sincronizzazioni indipendenti che desideri, ciascuna con i propri servizi, playlist, pianificazione e limiti di sicurezza.
- ↪️ **trasferimenti una tantum**: copia qualsiasi playlist da un servizio a un altro con una barra di avanzamento dal vivo; mettere in pausa, riprendere o interrompere la copia durante la copia e risolvere manualmente le tracce senza corrispondenza.
- 🕒 **Aggiungi tracce o conserva l'ordine delle tracce**: le copie arrivano alla fine della destinazione per impostazione predefinita, veloce e additiva. Attiva Conserva ordine aggiunto di recente per riscrivere le tracce dopo quella nuova più vecchia in modo che l'ordine di aggiunta della data corrisponda alla fonte.
- 🔗 **Trasferisci da un collegamento**: incolla l'URL di una playlist pubblica da qualsiasi servizio connesso e copialo direttamente. Non è necessario salvarlo o seguirlo prima.
- 🌐 **Playlist seguite**: sincronizza e trasferisci le playlist che segui ma non possiedi, non solo quelle che hai creato.
- 📦 **Backup dei metadati pianificati**: archivia l'intera libreria di playlist di un account secondo la propria pianificazione sotto i dati persistenti dell'app, con JSON/XML, limiti di conservazione e cronologia visibile di successi/fallimenti. rimangono disponibili anche download una tantum e Soundiiz JSON pronti per l'importazione.
- 💿 **Mirror download locale**: mantieni l'audio offline, una cartella per playlist nel layout `AlbumArtist/Album` di Jellyfin, con copertine e un `.m3u8` aggiornato automaticamente.
- 🛡️ **Misure di sicurezza**: simulazione per impostazione predefinita, limiti di aggiunta/rimozione per passaggio, protezione dalla perdita di rete, protezione dagli snapshot vuoti, interruzioni senza scrittura alla scadenza dei token.
- 🗃️ **Archivio di brani in continua crescita**: ogni traccia mai vista è registrata in un database locale SQLite (nome, artista, album, ISRC, metadati grezzi, primo/ultimo visto).
- 🧭 **Cronologia delle partite modificabile**: sfoglia, correggi ed elimina ogni corrispondenza di traccia memorizzata nella cache per servizio dalla pagina Mapping, inclusi i risultati "nessuna corrispondenza" che altrimenti rimarrebbero senza corrispondenza per sempre.
- 🐳 **Funziona ovunque**: uno `docker compose up -d` per l'app browser o semplice CLI + cron / Task Scheduler.

> [!IMPORTANT]
> Self-hosted e privato per progettazione. I tuoi dati di ascolto e le tue credenziali non lasciano mai la tua macchina. L'interfaccia utente web non ha autenticazione: collegala al tuo LAN e non eseguirne il port forwarding su Internet.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Schermate

<div align="center">

**Una dashboard per ogni biblioteca: sincronizza stato, lavori, attività in tempo reale e integrità del servizio**

<img src="../../.github/assets/dashboard.png" alt="Dashboard SongMirror che mostra lo stato di sincronizzazione, i lavori configurati, l'attività live e l'integrità per Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music e Jellyfin" width="82%">

**Configura un numero qualsiasi di sincronizzazioni (unidirezionale, unione multi-origine, gruppo autorevole o bidirezionale) in una breve procedura guidata**

<img src="../../.github/assets/sync-wizard.png" alt="La procedura guidata di configurazione SongMirror seleziona i servizi per una sincronizzazione bidirezionale tra Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music e YouTube Music" width="82%">

**Connetti tutti i servizi nel tuo browser: OAuth con un clic, incolla token guidato o una chiave API**

<img src="../../.github/assets/accounts.png" alt="La pagina Account per connettere Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music e Jellyfin" width="82%">

**Sfoglia e abbina playlist tra servizi**

<img src="../../.github/assets/playlists.png" alt="Navigazione nelle playlist dei servizi connessi con copertine e conteggi delle tracce" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀Avvio rapido

Il modo più veloce per eseguirlo è Docker — Compose estrae l'immagine pubblicata, fornisce l'interfaccia utente Web ed esegue le sincronizzazioni nei tempi previsti.

Per un'installazione persistente con riavvii automatici:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Oppure prova direttamente l'immagine GHCR pubblica senza clonare il repository:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Quindi apri `http://localhost:8888` e collega i tuoi servizi nel browser. La configurazione Compose non necessita di `.env` per essere avviata; tutto è configurato nell'interfaccia utente e salvato in `./data`.

L'opzione diretta `docker run` è usa e getta: `docker stop songmirror` rimuove il contenitore e la sua configurazione. Utilizza Compose per un'installazione duratura con credenziali, cache e download persistenti oppure consulta [guida alle immagini del contenitore](../docker-image.md) per tag e blocco digest.

Preferisci eseguirlo senza Docker?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Richiede [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Per il mirror di download locale, anche `uv tool install spotdl` e avere `ffmpeg` su PATH.

<a id="app-language"></a>

### Lingua dell'app

SongMirror supporta inglese, arabo, turco, spagnolo, cinese semplificato, francese, portoghese, tedesco, giapponese, hindi, bengalese, indonesiano, coreano, italiano e vietnamita. Al primo avvio vengono esaminate in ordine le preferenze linguistiche del browser, comprese le varianti regionali, e viene usata la prima lingua supportata. Se nessuna è supportata, viene usato l’inglese. Cambia lingua in **Impostazioni → Generali → Lingua**: la scelta viene salvata in questo browser e mantenuta dopo il ricaricamento della pagina. Seleziona **Automatico (browser)** per seguire di nuovo le preferenze del browser. L’interfaccia araba viene visualizzata da destra a sinistra. I nomi di playlist, artisti e servizi, le credenziali e i log diagnostici mantengono i valori originali.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Sempre in funzione: Docker

Il contenitore Docker è la distribuzione consigliata: serve l'interfaccia utente Web, esegue le sincronizzazioni in base alla pianificazione e si riavvia con l'host. Compose estrae `ghcr.io/ahnafnafee/songmirror:latest`, lo esegue come `songmirror` e persiste tutte le auth + cache in `./data`.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Per aggiornare, esegui `docker compose up -d --pull always`. Per creare invece il checkout corrente, esegui `docker compose up -d --build`. Consulta [guida alle immagini del contenitore](../docker-image.md) per tag, blocco digest, pull diretti, verifica, aggiornamenti e rollback.

Per iniziare non è necessario `.env`: tutto è configurato nel browser e salvato in `./data`. OAuth, partner-token e API-key sono tutti disponibili nella pagina Account; ogni procedura guidata spiega i prerequisiti specifici del servizio e l'esatto URI di richiamata. Quindi crea le tue sincronizzazioni nella pagina Sincronizzazione.

L'apertura di SongMirror da un altro computer funziona a `http://<server>:8888`. La connessione predefinita Spotify utilizza una sessione web `sp_dc` incollata, quindi non necessita di app per sviluppatori o URL di richiamata. Se utilizzi intenzionalmente l'app per sviluppatori legacy OAuth fallback dietro Docker o un proxy inverso, imposta l'URL di base visibile dal browser in `.env`:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror pubblicherà quindi `https://music.example.com/oauth/spotify/callback`; registra l'URI esatto nella dashboard dell'app Spotify e ricrea il contenitore con `docker compose up -d --force-recreate`. È supportato anche un percorso di base proxy inverso (ad esempio, `https://example.com/songmirror`). [Spotify richiede HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) per ogni reindirizzamento non di loopback; il semplice HTTP è accettato solo con indirizzi di loopback letterali come `127.0.0.1`, non un IP LAN o `localhost`.

| | |
| --- | --- |
| Immagine | `ghcr.io/ahnafnafee/songmirror:latest` supporta AMD64 e ARM64. Ogni build è inoltre pubblicata con un tag `sha-...` specifico del commit; I tag Git come `v1.2.3` pubblicano inoltre `1.2.3`, `1.2` e `1`. Utilizza [guida alle immagini del contenitore](../docker-image.md) per appuntare un digest immutabile. |
| Porto | L'interfaccia utente è pubblicata sull'host 8888 (la mappatura `8888:8080` in `docker-compose.yml`; cambia il lato host se è in conflitto). LAN-only: non eseguire il port forwarding su Internet; l'interfaccia utente non ha ancora l'autenticazione. |
| Persistenza | `./data` contiene credenziali, token, cache, archivio di brani e istantanee della playlist programmate in `playlist_backups/`. Esegui il backup per mantenere la configurazione e gli archivi durante le ricostruzioni. |
| Download | Imposta `DOWNLOAD_DIR` (in `.env` o nella tua shell) sulla directory della musica host (ad esempio `F:\Torrent\Music`); componi lo collega e lo monta su `/music`. Da Docker, imposta `JELLYFIN_URL` su `http://host.docker.internal:8096`. |
| Sessioni scadute | Le sessioni rinnovabili vengono ripristinate al successivo passaggio programmato o manuale. TIDAL le sessioni del web player si rinnovano dal token di aggiornamento catturato; I token Qobuz e Apple Music devono comunque essere incollati nuovamente quando rifiutati. Non è necessario riavviare. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Come funziona

Ad ogni passaggio, per ogni nome di playlist selezionato esistente nella sorgente:

1. Crea un'istantanea della playlist di origine (tracce, ISRC, date di aggiunta).
2. Riconcilia la playlist con lo stesso nome su ogni destinazione selezionata e connessa contemporaneamente tramite la playlist autorizzata dall'account di quel servizio API.
3. Le tracce mancanti vengono risolte (collegamenti memorizzati nella cache → ISRC → ricerca con punteggio) e aggiunte per prime; le tracce scomparse dalla fonte vengono rimosse dietro le guardie.
4. Facoltativamente, [spotDL](https://github.com/spotDL/spotify-downloader) sincronizza una cartella audio locale per playlist.

La fonte di verità predefinita è Spotify, ma la modalità unidirezionale è indipendente dal provider: qualsiasi peer di playlist connesso può invece essere la fonte.

<a id="matching"></a>

### Corrispondenza

Stessa gerarchia utilizzata dagli strumenti cross-service ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): identificatore esatto → ricerca → punteggio fuzzy.

1. Collegamento memorizzato nella cache: una volta che una traccia sorgente viene abbinata all'ID catalogo/ID video di destinazione, il collegamento viene archiviato e riutilizzato (immune alla deriva del titolo).
2. ISRC — identità esatta della registrazione dove il servizio la espone.
3. Ricerca con punteggio: [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, sia sul titolo grezzo che romanizzato ([anyascii](https://github.com/anyascii/anyascii)) e sull'artista, ancorato alla durata. Questo gestisce, senza hardcoding:
   - Crediti multi-artista: un servizio elenca tutte le funzionalità, un altro elenca le principali (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Decorazione del titolo: `(feat. …)`, `- 2015 Remaster`, `(From "…")`, suffissi extra "Official Music Video".
   - Traslitterazione — cirillico / bengalese / greco / arabo (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Tracce solo video: la ricerca YouTube ricade sul filtro `videos` per le tracce indie/OST che vivono su YT solo come caricamenti.

L'ancoraggio della durata sblocca la corrispondenza del titolo più libera, quindi una versione diversa (`Runaway - Piano Version`) o una copertina con un artista sbagliato non sono accettate quando la sua lunghezza non è d'accordo. Le tracce senza corrispondenza sicura vengono segnalate e saltate.

<a id="multi-source-merge-sync"></a>

### Sincronizzazione dell'unione multi-origine

Un lavoro Unisci origini combina una o più playlist esplicite in una destinazione scelta. Ogni fonte può provenire dalla libreria di un account connesso o dall'URL di un provider pubblico incollato; quest'ultimo viene risolto una volta in un provider e in un ID playlist, quindi non è necessario salvare o seguire la playlist e le esecuzioni pianificate non riproducono un URL arbitrario.

- Un'unione di appartenenza: tutti i componenti vengono letti prima che la destinazione venga riconciliata. Gli ISRC condivisi sono una registrazione; senza ISRC, titolo esatto/conservativo, artista, versione e prova della durata deduplica le sovrapposizioni.
- Ordine deterministico: prima la priorità del descrittore di origine, quindi l'ordine restituito da ciascuna playlist di origine. La prima occorrenza possiede la posizione di destinazione e visualizza i metadati; le copie successive arricchiscono solo i metadati di identità mancanti.
- Rimozioni a tutela dell'Unione: un percorso di destinazione può essere rimosso solo quando un passaggio completo lo trova assente da ogni fonte costituente. Una fonte non riuscita, troncata, non valida, non disponibile o inconoscibilmente vuota disabilita ogni rimozione per quel passaggio, mentre le aggiunte sicure da fonti leggibili possono continuare.
- Solo aggiunta per impostazione predefinita: lascia disattivata l'opzione Rimuovi tracce da ogni origine per mantenere tutte le tracce solo di destinazione. Accendendolo si attiva il normale limite di rimozione per passaggio dopo che la protezione di lettura completa è passata.

Unisci i lavori attualmente hanno come target la playlist di un fornitore; il mirror separato per il download locale/Jellyfin con Spotify non è disponibile per un processo aggregato.

<a id="authoritative-groups"></a>

### Gruppi autorevoli

Utilizza un gruppo autorevole quando curi attivamente la stessa playlist logica su due o più servizi, ma desideri che tutti gli altri servizi selezionati li seguano. Una configurazione tipica è Spotify + Apple Music come autorità, con TIDAL, Qobuz, Deezer, Amazon Music e YouTube Music come specchi.

- L'appartenenza proviene solo dalle autorità: una traccia aggiunta su Spotify o Apple Music si propaga all'altra autorità e ad ogni mirror. Una traccia aggiunta solo su uno specchio è una deriva; non viene mai importato nuovamente nelle autorità.
- Un'autorità di ordine: scegli quale autorità fornisce i nomi delle playlist e l'ordine delle aggiunte. Le altre autorità continuano a contribuire ai cambiamenti di adesione.
- Le rimozioni confermate si propagano da entrambe le autorità: un'assenza deve apparire in due letture complete consecutive prima di poter eliminare qualsiasi cosa. Un’aggiunta simultanea dal lato dell’autorità prevale su una rimozione.
- Gli specchi non ricevono mai un voto: eliminare una traccia da uno specchio ripara quello specchio; non elimina la traccia da Spotify o Apple Music.
- Primo passaggio sicuro: ogni set di autorità ha la propria linea di base. Il suo primo passaggio riuscito può aggiungere tracce mancanti, ma mantiene tutte le rimozioni fino a quando un passaggio successivo non dimostra che la linea di base è stabile.
- Chiusura non riuscita: se un'autorità è disconnessa, illeggibile o la relativa playlist non può essere aperta/creata, la playlist logica viene saltata invece di ricadere silenziosamente su meno autorità.

Le eliminazioni richiedono un’attivazione esplicita e restano soggette a un limite. Abilita **Sincronizza le eliminazioni** per il processo, oppure imposta `MAX_REMOVALS` nell’esecuzione senza interfaccia grafica, se vuoi rimuovere dai mirror i brani in eccesso rispetto all’insieme delle fonti di riferimento.

<a id="bidirectional-n-way-sync"></a>

### Sincronizzazione bidirezionale (N-vie).

Per impostazione predefinita, un fornitore è la fonte della verità e le modifiche fluiscono in un senso. Nella modalità N-way ogni provider selezionato è un peer: aggiungi o rimuovi una traccia su uno qualsiasi e il cambiamento si propaga agli altri.

La sincronizzazione bidirezionale è impossibile senza stato, quindi l'appartenenza canonica di ogni playlist logica viene catturata dopo ogni passaggio pulito. Ogni passaggio differenzia ogni fornitore rispetto a quell'istantanea, unisce le modifiche e riconcilia tutti con il risultato:

- Senza eco: un'aggiunta propagata diventa parte dell'istantanea, quindi non viene mai restituita.
- Vantaggi aggiuntivi in caso di conflitto: perdere una canzone è peggio che mantenerne una in più.
- Protezione dal collasso delle letture: se un provider legge improvvisamente molte meno tracce rispetto alla linea di base (un singhiozzo transitorio API), viene saltato quel passaggio in modo che una lettura errata non possa provocare un'eliminazione di massa.
- Stesse garanzie del metodo unidirezionale: limiti per passaggio `MAX_ADDS` / `MAX_REMOVALS` e protezione contro le perdite nette su ogni lato di scrittura.
- **Le eliminazioni sono facoltative**: `MAX_REMOVALS` vale 0 per impostazione predefinita. Un brano che scompare da un servizio, perché eliminato lì o ritirato per motivi di licenza, resta negli altri e la modifica viene solo registrata. Imposta un limite o abilita **Sincronizza le eliminazioni** nell’interfaccia per propagare le eliminazioni.

> Prima sempre la simulazione. Esegui senza `--execute` (o usa Anteprima nell'interfaccia utente) e leggi il piano: stampa ogni aggiunta/rimozione proposta su ogni provider prima che venga scritto qualsiasi cosa.

<a id="liked-and-favorite-tracks"></a>

### Tracce apprezzate e preferite

Nel passaggio Playlist di una sincronizzazione, seleziona la raccolta Mi piace incorporata del servizio di origine. SongMirror chiede quindi dove dovrebbe andare su ogni destinazione selezionata: direttamente nella raccolta dei preferiti/piaciuti di quel servizio o in una nuova playlist di cui è possibile modificare il nome suggerito. Una nuova selezione riceve solo "Mi piace"; attiva Sincronizza anche tutte le playlist normali o scegli playlist individuali per includerle entrambe.

Funziona con Spotify Brani preferiti, TIDAL/Qobuz/Deezer Tracce preferite, Amazon Music Mi piace, Apple Music Canzoni preferite e YouTube Music Musica piaciuta. Si applicano gli stessi percorsi di riconciliazione unidirezionale, gruppo autorevole e a N vie e limiti di sicurezza. Come per le playlist normali, le eliminazioni restano disattivate per impostazione predefinita finché non si abilita **Sincronizza le eliminazioni**.

La concessione del web player con accesso a TIDAL gestisce sia le playlist ordinarie che le tracce preferite native quando contiene `r_usr` e `w_usr`. L'acquisizione della risposta completa del token di accesso fornisce SongMirror il token di aggiornamento nonché il Bearer di breve durata, in modo che la sessione possa rinnovarsi automaticamente.

Alcune di queste integrazioni utilizzano le interfacce web proprietarie dei fornitori e possono cambiare senza preavviso; il [valutazione di fattibilità](../design/2026-09-01-liked-tracks-sync-feasibility.md) registra il API e i vincoli di distribuzione per ciascun fornitore.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Backup dei metadati della playlist

I backup non richiedono un secondo provider o un processo di sincronizzazione:

- In Impostazioni → Backup della playlist, utilizza Aggiungi backup in alto per aggiungere un account connesso. Scegli JSON o XML, quindi seleziona una frequenza come giornaliera o settimanale. Gli intervalli personalizzati utilizzano un numero e un'unità. Conserva i backup offre preimpostazioni di conservazione, un conteggio personalizzato o Tutti i backup.
- Per impostazione predefinita, i backup sono `data/playlist_backups/<account-profile-id>/` (o `/data/playlist_backups/<account-profile-id>/` in Docker). Fare clic su Cartella di backup per il selettore di cartelle integrato oppure scegliere Immetti percorso manualmente. Una cartella personalizzata riceve comunque una sottocartella separata per ciascun account. Usa la cartella di backup predefinita ripristina l'impostazione predefinita. La modifica delle posizioni influisce sui backup futuri; i vecchi file rimangono dove sono. Conservazione e Download più recente si applicano alla posizione selezionata. La rimozione di una pianificazione non elimina mai i file salvati.
- Impostazioni → Download e Jellyfin → La cartella Download utilizza lo stesso selettore integrato e l'immissione manuale. Scegli una cartella accessibile alla tua libreria Jellyfin. I download seguono la pianificazione di ciascuna sincronizzazione attivata nella scheda Sincronizzazione. Il selettore visualizza i percorsi host configurati (ad esempio, `F:\Torrent\Music`) mantenendo la mappatura Docker (`/music`) internamente. I supporti di download esistenti rimangono invariati. Le cartelle host aggiuntive devono essere prima condivise come montaggi di associazione Docker; la scelta di una cartella non montata mostra un errore e lascia invariata l'impostazione corrente.

- La stessa scheda Impostazioni mostra l'esecuzione successiva, il conteggio degli snapshot archiviati, l'ultimo file e i conteggi riusciti e l'errore più recente. Il backup ora mette in coda un'esecuzione sicura su richiesta; Scarica più recente recupera lo snapshot persistente più recente.
- Nella pagina Playlist, utilizza Esporta su una scheda di servizio per scaricare ogni playlist da quel servizio in un file con versione JSON o XML.
- Apri una playlist per esportare solo quella playlist. La sua opzione Soundiiz segue [La forma di importazione JSON documentata di Soundiiz](https://soundiiz.com/data/fileExamples/playlistExport.json), quindi l'elenco dei brani scaricati può essere caricato tramite il flusso Importa playlist → Da file di Soundiiz.
- SongMirror JSON/XML conserva l'ordine e i nomi della playlist oltre agli ID traccia/occorrenza del fornitore, ISRC disponibili, artisti, album, posizioni delle tracce degli album, durate, date aggiunte, collegamenti alle illustrazioni e indicatori di voci non disponibili. I fantasmi del catalogo senza ID rimangono nel backup invece di scomparire. I file non contengono cookie, token, intestazioni di richiesta, anteprime o URL di file di streaming.

Le esportazioni manuali vengono scaricate dal browser sul dispositivo che esegue l'interfaccia utente. Le esportazioni pianificate utilizzano il volume dei dati dell'applicazione esistente, quindi non è richiesto alcun secondo percorso host o montaggio del contenitore. Il backup legge la coda dietro sincronizzazioni e trasferimenti invece di accedere contemporaneamente ai client del provider. Il campo `schema_version` consente alle versioni future di evolvere il formato lossless senza rendere ambigue le vecchie istantanee.

<a id="built-in-folder-picker"></a>

### Selettore di cartelle integrato

Fare clic sul campo di una cartella o su Sfoglia… per aprire il selettore integrato. Utilizza Posizioni, breadcrumb cliccabili, Indietro, Avanti e Su di una cartella per navigare. Fare clic su una cartella per selezionarla; fai doppio clic, premi Invio o usa la sua freccia per aprirlo. La ricerca filtra la cartella corrente. Inserisci un percorso della cartella che accetta un indirizzo completo. Seleziona la cartella aggiorna la bozza; salvare le impostazioni o programmare per applicarlo. Annulla lascia la bozza invariata. Non è richiesto alcun helper desktop o processo aggiuntivo.

Nuova cartella crea una sottocartella denominata nella posizione attualmente aperta, quindi la apre. Gli elementi esistenti non vengono mai sovrascritti. L'annullamento dell'immissione del nome non crea nulla; l'annullamento del selettore dopo la creazione lascia la nuova cartella sul disco. La posizione di backup o download salvata cambia solo dopo averla selezionata e salvata. In Docker, il selettore spiega quali percorsi sono condivisi e mostra sia il percorso del contenitore che il percorso del computer configurato quando disponibile.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Mirror di download locale (Jellyfin)

Conserva una copia audio offline di ogni playlist sincronizzata, una cartella per playlist, tramite [spotDL](https://github.com/spotDL/spotify-downloader). La sincronizzazione è un vero mirroring: le nuove tracce vengono scaricate, le tracce rimosse vengono eliminate localmente. Il layout è pronto per Jellyfin: punta una libreria musicale Jellyfin nella directory di download e verranno visualizzate sia le tracce che le playlist, rimanendo aggiornate ad ogni passaggio:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Abilitalo impostando `DOWNLOAD_DIR` e installando spotDL + ffmpeg:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Incrementale: dopo il primo download completo, vengono recuperate solo le tracce appena aggiunte; le tracce rimosse (e le cartelle degli album svuotate) vengono eliminate. Una corsa interrotta continua al passaggio successivo.
- Il più recente-prima `.m3u8` — scritto in ordine di data di aggiunta, il più recente in alto (imposta `LOCAL_MIRROR_ORDER=oldest` per capovolgere). Ricostruisci copertine/tag/mtimes da file esistenti con `uv run main.py --refresh-local`.
- Le copertine della playlist in Jellyfin — Jellyfin ignora un file di copertina accanto a un m3u, quindi imposta `JELLYFIN_URL` + `JELLYFIN_API_KEY` e ogni passaggio carica la vera copertina della playlist tramite Jellyfin API.
- Qualità audio: la sorgente è YouTube, quindi senza un cookie YT Music Premium il limite è di ~128–160 kbps. `LOCAL_MIRROR_FORMAT=opus` mantiene il flusso nativo di YouTube senza ricodificare mp3; un cookie Premium (`LOCAL_MIRROR_COOKIE_FILE`) sblocca AAC a 256 kbps. Selezionando `flac` si modifica il contenitore di output ma non è possibile trasformare una sorgente con perdita in audio senza perdita.

L'attuale percorso FLAC di Monochrome utilizza risorse di riproduzione monouso con controllo del browser anziché un'esportazione di file stabile e autorizzata dal provider API, quindi SongMirror non lo automatizza. Utilizza il mirror locale solo per i contenuti che possiedi o che sei altrimenti autorizzato a copiare.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Collegamento di ogni servizio

Nell'app Web, la pagina Account ti guida attraverso ciascun servizio e mostra i valori esatti da incollare. Niente viene proxy tramite terzi.

<a id="credential-renewal"></a>

### Rinnovo credenziali

SongMirror aggiorna le credenziali just in time, non con un timer di aggiornamento token separato. Ogni passaggio di sincronizzazione manuale o pianificato convalida i connettori utilizzati e rinnova i token di accesso supportati prima della prima richiesta (o una volta dopo un rifiuto di autenticazione). È normale che un token di accesso di breve durata scada tra un passaggio e l'altro: ciò che conta è il token di aggiornamento durevole o il cookie di rinnovo. La pagina Account convalida lo stato quando viene caricata o riacquista lo stato attivo, ma non è la manutenzione della sessione in background; le pianificazioni di sincronizzazione abilitate sono.

| Servizio | Comportamento di rinnovo |
| --- | --- |
| Spotify | La connessione predefinita conia un token di accesso del lettore web dal cookie `sp_dc` salvato su richiesta e riprova con un nuovo token dopo un `401`; la sessione di accesso sottostante può ancora essere revocata. L'app per sviluppatori legacy OAuth rimane supportata per le installazioni esistenti. |
| TIDAL | Il token di accesso del lettore Web importato si rinnova automaticamente tramite `auth.tidal.com` utilizzando il token di aggiornamento dalla risposta di accesso. SongMirror mantiene il token di aggiornamento esistente quando una risposta lo omette e persiste un token ruotato quando TIDAL ne restituisce uno. La disconnessione o la revoca richiedono comunque una nuova acquisizione. |
| Qobuz | Il `X-User-Auth-Token` incollato viene utilizzato finché Qobuz lo rifiuta, quindi deve essere catturato nuovamente. |
| Deezer | La pipa di breve durata JWT si rinnova automaticamente dalla `refresh-token` salvata prima dell'uso e una volta dopo una `401/403`; lo stato di rinnovo ruotato viene mantenuto. |
| Amazon Music | Il token di accesso al Web si rinnova tramite `/pandaToken` utilizzando lo user agent, il referer e i cookie consentiti del browser acquisiti. L'attuale flusso `POST config.json?skipToken=false` esegue il bootstrap del contesto del dispositivo quando necessario e i cookie ruotati vengono mantenuti. Il logout, le modifiche alla sicurezza o la revoca lato server richiedono comunque una nuova acquisizione. |
| Apple Music | Gli Bearer e Media-User-Token incollati non possono essere rinnovati entro SongMirror e devono essere acquisiti nuovamente dopo il rifiuto. |
| YouTube Music | Data API OAuth si aggiorna automaticamente entro 60 secondi dalla scadenza. La modalità browser tenta la rotazione dei cookie di Google ogni volta che viene creata una destinazione di sincronizzazione; è necessario esportare nuovamente una sessione del browser già scaduta. |
| Jellyfin | La chiave API non ha ciclo di aggiornamento del token di accesso; sostituirlo solo in caso di revoca o cancellazione. |

<a id="spotify"></a>

### Spotify

1. Accedi a <https://open.spotify.com>.
2. Apri il browser DevTools (`F12`) → Applicazione (Chrome/Edge) o Archiviazione (Firefox) → Cookie → `https://open.spotify.com`.
3. Copia il valore del cookie `sp_dc` e incollalo in Account → Spotify.

Quella singola sessione Web con accesso gestisce la navigazione nella libreria, la lettura e la scrittura delle playlist e la ricerca nel catalogo. Non richiede un'app per sviluppatori Spotify, una chiave API o un account Premium. Tratta `sp_dc` come una password: SongMirror la memorizza nella sua directory di dati privati, ma l'integrazione utilizza le operazioni interne del web player di Spotify e può richiedere manutenzione se Spotify le modifica. Le credenziali esistenti dell'app per sviluppatori OAuth rimangono un fallback compatibile.

<a id="tidal"></a>

### TIDAL

1. Apri [Il web player di TIDAL](https://listen.tidal.com), apri DevTools → Rete e attiva Conserva registro.
2. Esci e accedi nuovamente, quindi filtra l'elenco delle reti per `oauth2/token`.
3. Seleziona la richiesta `auth.tidal.com/v1/oauth2/token` riuscita. In Payload (Chrome/Edge) o Richiesta (Firefox), copia il valore del modulo `client_id` nel campo ID client del lettore Web di SongMirror.
4. Apri la scheda Risposta della richiesta e copia il suo JSON completo nella risposta del token del lettore Web. Dovrebbe includere sia `access_token` che `refresh_token`.
5. Connettiti. SongMirror esercita immediatamente la concessione di aggiornamento e rifiuta di segnalare l'esito positivo se l'ID cliente non può rinnovarla.

L'ID client OAuth è i metadati della richiesta e non è l'attestazione numerica `cid` all'interno del token di accesso di TIDAL. SongMirror estrae solo il token di accesso, il token di aggiornamento, l'ID client, gli ambiti, la scadenza e il paese del catalogo; i dati di risposta non correlati vengono eliminati. Si rinnova poco prima della scadenza e una volta dopo un rifiuto di autenticazione tramite `https://auth.tidal.com/v1/oauth2/token`, preservando la rotazione del token di aggiornamento. Il vecchio incollamento dell'intestazione della richiesta OpenAPI rimane compatibile, ma poiché non contiene alcun token di aggiornamento, deve comunque essere incollato nuovamente dopo la scadenza. Vengono utilizzati solo i metadati del catalogo e le playlist dell'utente che ha effettuato l'accesso: le risorse di riproduzione rimangono esterne a questa integrazione.

<a id="qobuz"></a>

### Qobuz

Accedi a <https://play.qobuz.com>, apri DevTools → Rete e filtra per `api.json/0.2`. Scegli qualsiasi richiesta contenente `X-App-Id` e `X-User-Auth-Token`, inclusa una richiesta `album/story` autenticata, quindi copia le intestazioni della richiesta o copiala come cURL e incollala nella procedura guidata. SongMirror mantiene solo questi due valori, li invia utilizzando lo stesso flusso basato sull'intestazione del lettore Web ed elimina i cookie e i metadati del browser non correlati. Non è richiesta alcuna approvazione aziendale API o ID utente; le credenziali dei partner esistenti rimangono un ambiente di riserva compatibile.

L'adattatore utilizza solo la ricerca nel catalogo e gli endpoint della playlist, non richiede flussi o URL di file.

<a id="deezer"></a>

### Deezer

Accedi a <https://www.deezer.com>, apri DevTools → Rete e ricarica la pagina. Filtra per `auth.deezer.com/login/renew`, copia le intestazioni della richiesta (o copiala come cURL) e incollala nel campo di rinnovo. Firefox può invece copiare i cookie della richiesta come un semplice blocco delimitato da punto e virgola; anche quella forma è accettata. SongMirror conserva solo il cookie `refresh-token` dedicato e lo utilizza per rinnovare automaticamente la Pipe JWT di breve durata di Deezer. Puoi anche incollare una richiesta `pipe.deezer.com/api` corrente come bootstrap immediato, ma non è necessario quando è configurato il rinnovo. Le aggiunte e le rimozioni della playlist utilizzano entrambe la sessione rinnovabile di Pipe; non è necessario alcun cookie `arl`. I token OAuth dello sviluppatore esistente rimangono un ambiente di riserva compatibile.

<a id="amazon-music"></a>

### Amazon Music

Per il connettore predefinito non è richiesta l'approvazione dello sviluppatore. Utilizza gli stessi percorsi autenticati GraphQL e di rinnovo del token del web player Amazon Music:

1. Accedi a <https://music.amazon.com> e apri DevTools → Rete.
2. Ricarica la pagina, filtra per `config.json` e seleziona la richiesta di accesso. (`pandaToken` funziona anche quando appare, ma non è obbligatorio.)
3. Scegli Copia intestazioni richiesta o Copia come cURL, quindi incollalo nel campo di rinnovo. Conserva le intestazioni complete `User-Agent`, `Referer` e `Cookie` in modo che SongMirror possa riprodurre lo stesso contesto del browser.
4. Facoltativamente copiare la risposta `config.json` con accesso nel campo bootstrap; SongMirror normalmente può recuperare il contesto del dispositivo utilizzando la sessione di rinnovo.

SongMirror deriva lo stesso valore di autorizzazione `AmznMusic` localmente e lo aggiorna tramite `music.amazon.com/pandaToken` prima della scadenza o una volta dopo un rifiuto di autenticazione. Durante la connessione utilizza l'attuale richiesta di configurazione in stile browser quando è necessario il contesto del dispositivo, richiede `/pandaToken` per coniare un token di accesso e rifiuta la connessione se Amazon revoca il cookie di rinnovo di Music. Memorizza solo lo user agent del browser, la lingua, il referer musicale, una lista consentita denominata di cookie di autenticazione/sessione di Amazon e un contesto limitato del dispositivo client musicale; analisi, esperimenti, console AWS, CSRF e altri dati del browser non correlati vengono eliminati. I cookie conservati sono comunque sensibili, quindi mantieni SongMirror privato sul tuo LAN. Un logout, una modifica della password/sicurezza o una revoca da parte di Amazon possono comunque richiedere una nuova acquisizione.

Si tratta di un'interfaccia client Web di prima parte non supportata e Amazon può modificarla senza preavviso. La [Amazon Music Web API](https://developer.amazon.com/docs/music/API_web_overview.html) documentata è ancora una beta chiusa; Le credenziali del partner approvato rimangono un fallback facoltativo se configurate tramite variabili di ambiente.

<a id="apple-music"></a>

### Apple Music

Non è necessario alcun account Apple Developer: sono sufficienti due intestazioni da `music.apple.com`. Apri <https://music.apple.com>, accedi, apri DevTools → Rete, riproduci un brano, filtra per `amp-api.music.apple.com` e dalle intestazioni di qualsiasi richiesta copia:

- `authorization: Bearer eyJ...` → Bearer token (la parte `eyJ...`, senza `Bearer `)
- `media-user-token: ...` → Token utente (valore completo)

La procedura guidata di connessione ti consente di incollare le intestazioni non elaborate e di analizzare i valori per te. Gettoni ultimi mesi; incollarli nuovamente nella pagina Account quando scadono.

Un ID Apple senza un abbonamento Apple Music attivo può comunque connettersi in modalità Solo catalogo. In questa modalità, incolla un collegamento alla playlist pubblica Apple Music su Trasferimenti per copiarlo in un altro servizio connesso. La navigazione nella libreria Apple, la sincronizzazione pianificata e l'utilizzo di Apple Music come destinazione di trasferimento richiedono ancora il privilegio CloudLibrary a pagamento; SongMirror mostra tali operazioni come non disponibili invece di considerare le credenziali del catalogo valide come scadute.

<a id="youtube-music"></a>

### YouTube Music

Parla con il funzionario [YouTube Data API v3](https://developers.google.com/youtube/v3), il cui token di aggiornamento OAuth è durevole e sopravvive ai riavvii.

1. In [Google Console cloud](https://console.cloud.google.com), crea un progetto, abilita YouTube Data API v3 e crea un client OAuth di tipo TV e dispositivi a ingresso limitato.
2. Nella schermata di consenso OAuth imposta Stato pubblicazione → In produzione (lasciandolo in “Testing” fa scadere il token dopo 7 giorni).
3. Nell'app, incolla l'ID client + il segreto e completa il codice del dispositivo visualizzato sullo schermo.

> Quota: il Data API consente 10.000 unità/giorno (una ricerca costa 100, un'aggiunta/rimozione 50). Il mantenimento dello stato stazionario è economico; un grosso arretrato per la prima volta può raggiungere il limite e riprendere il giorno successivo.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ senza interfaccia grafica CLI

Preferisci `.env` + cron / Task Scheduler? Lo stesso motore funziona senza interfaccia grafica.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Flag utili:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Vars env chiave (vedi `.env.example`): le credenziali per qualunque provider utilizzi, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` e `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️Tutele di sicurezza

Le rimozioni sono distruttive, quindi sono sorvegliate:

- la simulazione è l'impostazione predefinita: non cambia nulla senza `--execute` (o l'azione di sincronizzazione reale dell'interfaccia utente).
- Se l'origine restituisce 0 tracce per una playlist che la destinazione mostra come non vuota, le rimozioni che passano vengono ignorate (un errore temporaneo API non può svuotare una playlist).
- **Le eliminazioni sono disattivate per impostazione predefinita**: `MAX_REMOVALS=0` blocca ogni eliminazione; viene registrata, mai applicata. Il ritiro di un brano per motivi di licenza su una piattaforma non può quindi provocare eliminazioni a catena sulle altre. Abilita **Sincronizza le eliminazioni** per ogni sincronizzazione oppure imposta `MAX_REMOVALS`. Anche dopo l’attivazione, se le eliminazioni in attesa in un singolo passaggio superano il limite, vengono tutte saltate e registrate.
- `MAX_ADDS` limita ogni scrittura che produce timestamp in un passaggio di sincronizzazione, inclusa la riparazione della cronologia. Se una partita recuperata più vecchia necessita di una riproduzione del suffisso più grande di quella consentita dal limite, SongMirror la rinvia al passaggio successivo anziché farla apparire più nuova o causare un'enorme esplosione del provider. Un trasferimento una tantum non ha un passaggio successivo, quindi non differisce mai: copia ogni traccia richiesta, aggiungendola nell'ordine di origine a meno che non si attivi "Conserva ordine aggiunto di recente" per quel trasferimento, che spende indipendentemente dai costi di riparazione.
- Una riparazione cronologica mette in scena una copia duplicata prima di ritirare l'originale. Su un servizio la cui eliminazione richiede ogni copia di una canzone, il conteggio del custode deve essere corretto, quindi Apple Music rilegge finché le copie messe in scena non sono visibili e si rifiuta di ritirare qualsiasi cosa contro una lettura che trascina ancora le proprie scritture. Deezer salta completamente la riparazione e aggiunge sempre: non ha nemmeno un inserto posizionale, quindi riprodurre un ordine che non può esprimere non vale il rischio per la destinazione. Il modulo di trasferimento in grigio indica il cambio dell'ordine e spiega il motivo.
- Protezione dalla perdita di rete: una traccia sul lato destinazione che assomiglia a una traccia di origine che non ha corrispondenze su quel servizio viene conservata, non eliminata.
- Qualsiasi errore di autenticazione del provider interrompe immediatamente il passaggio del provider: nessuna eliminazione parziale sui token scaduti.
- Un processo di unione deve completare la lettura di ogni origine costituente prima dell'eliminazione dalla destinazione; eventuali forze di snapshot di origine parziali/non riuscite che passano al comportamento di sola aggiunta.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Memorizzazione nella cache e archivio di brani

Tutto ciò che è risolvibile viene memorizzato nella cache, quindi i passaggi allo stato stazionario sono quasi istantanei: cache di risoluzione per servizio (ISRC + ricerca, inclusi gli errori), una cache dell'elenco di tracce con chiave `snapshot_id`, collegamenti identificativi esatti in SQLite e un salto di istantanea per coppia (`unchanged since last clean sync`).

Ogni passaggio archivia anche i metadati di ogni traccia che vede in `song_cache.db` — un file SQLite che cresce sempre e solo. Le tracce rimosse rimangono archiviate con nome, artista, album, durata, ISRC, istantanea grezza JSON e timestamp del primo/ultimo accesso:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Risolvere le mappature

Ogni servizio mantiene la propria cache di risoluzione, mappando una chiave `title|artist` normalizzata all'ID catalogo su cui corrisponde
quel servizio. Una corrispondenza viene riutilizzata per sempre, così come il risultato "nessuna corrispondenza", che è ciò che rende una traccia non riuscita
per corrispondere una volta, rimanere senza corrispondenza a ogni passaggio successivo.

La pagina Mapping nell'interfaccia utente web espone direttamente tali cache, per servizio:

- cerca nell'intera cache per titolo, artista o ID risolto
- filtrare in base alle voci impostate manualmente (una corrispondenza scelta nell'editor dei conflitti di trasferimento) o a tutte le voci che non corrispondono
- correggi un ID sbagliato incollando il collegamento della traccia giusta o elimina una mappatura in modo che il passaggio successivo la cerchi nuovamente
- cancella ogni voce "nessuna corrispondenza" per un servizio in un'unica azione, in modo che un gruppo di ricerche non riuscite riceva un altro tentativo

Quando un errore eliminato si risolve in seguito, semplicemente aggiungendolo la vecchia canzone apparirà più recente. Per la playlist
destinazioni, SongMirror riproduce invece quella canzone e il suffisso più recente già presente dal più vecchio al più nuovo, quindi rimuove
le copie più vecchie. I provider non consentono ai client di ripristinare i timestamp originali, ma ciò preserva il relativo
Ordine aggiunto di recente. Le raccolte native di Mi piace/Preferite rimangono riservate ai membri e non vengono mai riprodotte.

Le modifiche vengono rifiutate con un messaggio in chiaro mentre è in esecuzione una sincronizzazione, perché un passaggio mantiene la cache in memoria per il suo
tutta la durata e li sovrascriverebbe al termine.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱Impaginazione del progetto

Voce CLI: `uv run main.py` (spessore sottile) o `python -m songmirror`. Voce web: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Aggiunta di un altro servizio: sottoclasse `MirrorTarget`, implementa ~8 metodi, aggiungi il suo costruttore a `engine/targets`' `_REGISTRY` e la sua classe a `_CLASSES` e aggiungi un `Connector` corrispondente sotto `services/accounts`. Tutta la riconciliazione (differenza, ordinamento, misure di sicurezza, registrazione, salto di snapshot) viene ereditata.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Risoluzione dei problemi

- `Missing required environment variable`: compila `.env` (CLI) o collega il servizio nell'interfaccia utente.
- TIDAL riporta `Expired`: esci e rientra a `listen.tidal.com`, quindi incolla sia `client_id` dal payload della richiesta `oauth2/token` sia la sua risposta completa JSON in Account. Una richiesta OpenAPI copiata ha solo la breve durata Bearer e non può essere rinnovata.
- TIDAL segnala HTTP 429: si tratta di un limite di velocità temporaneo, non di un accesso scaduto. SongMirror rispetta il ritardo tra i nuovi tentativi del provider e memorizza nella cache i controlli di integrità dell'account invece di sondare ripetutamente API.
- Qobuz o Apple riporta `Expired` / `401` / `403` — queste sessioni incollate non hanno un segreto rinnovabile; acquisire una nuova richiesta o token di accesso in Account.
- TIDAL dice che il token non ha accesso alla traccia dei Mi piace: acquisisci una nuova risposta al token del web player con accesso che trasporta `r_usr` e `w_usr`.
- Il rinnovo Deezer non riesce: acquisisci una nuova richiesta `auth.deezer.com/login/renew` (o il suo cookie `refresh-token`). Un Pipe attuale Bearer da solo è solo un bootstrap temporaneo.
- Il rinnovo Amazon Music non riesce: acquisisci una nuova richiesta `POST /config.json?skipToken=false` con l'accesso completo con le sue intestazioni complete `User-Agent`, `Referer` e `Cookie`. La risposta JSON è facoltativa.
- YouTube Music La modalità browser scade: esporta nuove intestazioni di richiesta del browser. Per una configurazione automatica più duratura, utilizzare Data API OAuth con una schermata di consenso in produzione.
- Spotify rapporti scaduti: accedi nuovamente a `open.spotify.com` e incolla un nuovo cookie `sp_dc` in Account.
- Una playlist non viene sincronizzata: verifica che sia nell'ambito della playlist della sincronizzazione e che esista nell'origine (le destinazioni vengono create automaticamente in un passaggio reale).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Licenza

Copyright © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Questo progetto ha la licenza [MIT](../../LICENSE).

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
