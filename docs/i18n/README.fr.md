<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Synchronisation de playlist auto-hébergée et toujours active pour Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music et YouTube Music — plus un miroir audio local prêt pour Jellyfin.<br/>
Une alternative gratuite, open source et auto-hébergée à Soundiiz, TuneMyMusic et FreeYourMusic que vous possédez et exécutez.

**Fusion unidirectionnelle, multi-sources, synchronisation de groupe faisant autorité ou bidirectionnelle complète (N-way) · transferts de listes de lecture uniques · correspondance précise par ISRC · le tout depuis votre navigateur**

[Démarrage rapide](#quick-start) · [Caractéristiques](#features) · [Captures d'écran](#screenshots) · [Toujours en cours d'exécution : Docker](#always-running-docker) · [Comment ça marche](#how-it-works) · [Signaler un bug][github-issues-link] · [Proposer une fonctionnalité][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Partager ce projet**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Configurez-le une fois : chaque liste de lecture que vous organisez reste reflétée sur chaque service, par ordre de date d'ajout.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="Démo SongMirror — révélation du logo, tableau de bord, configuration de synchronisation unidirectionnelle et bidirectionnelle, transferts de listes de lecture en direct et correspondance précise par ISRC sur sept services musicaux" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">Regardez la version 1080p</a></sup>

</div>

> [!NOTE]
> Application Web + sans interface graphique CLI, un seul moteur. Cliquez sur l'interface utilisateur d'un navigateur pour connecter des services, créer des synchronisations et transférer des listes de lecture – ou exécutez-le `.env` + style cron. Les deux pilotent le même noyau de synchronisation.

<details>
<summary><kbd>Table des matières</kbd></summary>

#### Table des matières

- [✨ Caractéristiques](#features)
- [📸 Captures d'écran](#screenshots)
- [🚀 Démarrage rapide](#quick-start)
  - [Langue de l'application](#app-language)
- [🐳 Toujours en cours d'exécution : Docker](#always-running-docker)
- [⚙️ Comment ça marche](#how-it-works)
  - [Correspondance](#matching)
  - [Synchronisation de fusion multi-sources](#multi-source-merge-sync)
  - [Groupes faisant autorité](#authoritative-groups)
  - [Synchronisation bidirectionnelle (N-way)](#bidirectional-n-way-sync)
- [📦 Sauvegardes des métadonnées de la playlist](#playlist-metadata-backups)
- [💿 Miroir de téléchargement local (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Connexion de chaque service](#connecting-each-service)
  - [Renouvellement des informations d'identification](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ sans interface graphique CLI](#headless-cli)
- [🛡️ Mesures de sécurité](#safety-rails)
- [🗃️ Mise en cache et archives de chansons](#caching-song-archive)
  - [Résoudre les mappages](#resolve-mappings)
- [🧱 Disposition du projet](#project-layout)
- [🩺 Dépannage](#troubleshooting)
- [📄 Licence](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Caractéristiques

SongMirror conserve vos listes de lecture identiques partout sans ré-ajout manuel, copie une par une ou service cloud payant contenant votre bibliothèque. Il est multiplateforme, auto-hébergé et open source.

- 🔁 **Véritable mise en miroir, pas seulement ajout** – ajouts et suppressions. Choisissez une source de vérité (Spotify par défaut) et les autres la suivent.
- ⇆ **Groupes faisant autorité **: faites confiance à deux services ou plus (par exemple Spotify + Apple Music) tandis que tous les autres services sélectionnés restent un miroir de destination uniquement.
- ⇄ **Synchronisation bidirectionnelle N-way **: un ajout ou une suppression sur n'importe quel service connecté se propage à tous les autres, sans écho, derrière les protections de suppression.
- ⇉ **Synchronisation de fusion multi-sources **: planifiez l'union dédupliquée des listes de lecture de bibliothèque et des URL de listes de lecture publiques dans une seule destination, sans enregistrer ni suivre les listes publiques.
- ♥ **Pistes aimées et préférées **: synchronisez la collection préférée intégrée de chaque service sur les sept fournisseurs de musique, soit dans les favoris de la destination, soit dans une nouvelle liste de lecture nommée.
- 🎯 **correspondance précise par ISRC** — identité d'enregistrement exacte si disponible, avec des solutions de repli approximatives de titre/artiste/durée compatibles Unicode (différences dans les crédits de l'artiste en vedette, suffixes "- 2015 Remaster", scripts non latins, téléchargements de vidéo uniquement - tous gérés).
- 🎛️ **Synchronisations nommées multiples **: configurez autant de synchronisations indépendantes que vous le souhaitez, chacune avec ses propres services, listes de lecture, calendrier et plafonds de sécurité.
- ↪️ **transferts uniques** — copiez n'importe quelle playlist d'un service à un autre avec une barre de progression en direct ; mettez en pause, reprenez ou arrêtez la copie et résolvez manuellement les pistes sans correspondance.
- 🕒 **Ajoutez des pistes ou conservez l'ordre des pistes** - les copies atterrissent à la fin de la destination par défaut, de manière rapide et additive. Activez l'option Conserver l'ordre récemment ajouté pour réécrire les pistes après la plus ancienne afin que l'ordre des dates ajoutées corresponde à la source.
- 🔗 **Transfert à partir d'un lien **: collez l'URL d'une playlist publique à partir de n'importe quel service connecté et copiez-la directement. Pas besoin de le sauvegarder ou de le suivre au préalable.
- 🌐 **Listes de lecture suivies **: synchronisez et transférez les listes de lecture que vous suivez mais que vous ne possédez pas, pas seulement celles que vous avez créées.
- 📦 **Sauvegardes planifiées des métadonnées **: archivez l'intégralité de la bibliothèque de playlists d'un compte selon son propre calendrier sous les données d'application persistantes, avec JSON/XML, des limites de conservation et un historique de réussite/échec visible. les téléchargements uniques et les fichiers Soundiiz JSON prêts à l'importation restent également disponibles.
- 💿 **Miroir de téléchargement local **: conservez l'audio hors ligne, un dossier par liste de lecture dans la mise en page `AlbumArtist/Album` de Jellyfin, avec des couvertures et un `.m3u8` mis à jour automatiquement.
- 🛡️ **Mesures de sécurité **: simulation par défaut, plafonds d'ajout/suppression par passe, protection contre les pertes nettes, protection contre les instantanés vides, abandon sans écriture à l'expiration des jetons.
- 🗃️ **Archives de chansons en constante évolution** — chaque morceau jamais vu est enregistré dans une base de données locale SQLite (nom, artiste, album, ISRC, métadonnées brutes, première/dernière vue).
- 🧭 **Historique des correspondances modifiable **: parcourez, corrigez et supprimez toutes les correspondances mises en cache par service à partir de la page Mappings, y compris les résultats « aucune correspondance » qui autrement resteraient sans correspondance pour toujours.
- 🐳 **Fonctionne n'importe où** — un `docker compose up -d` pour l'application de navigateur, ou un simple CLI + cron / Task Scheduler.

> [!IMPORTANT]
> Auto-hébergé et privé par conception. Vos données d'écoute et vos informations d'identification ne quittent jamais votre machine. L'interface utilisateur Web n'a pas d'authentification : liez-la à votre LAN et ne la transférez pas vers Internet.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Captures d'écran

<div align="center">

**Un tableau de bord pour chaque bibliothèque : état de synchronisation, tâches, activité en direct et état du service**

<img src="../../.github/assets/dashboard.png" alt="SongMirror tableau de bord affichant l'état de synchronisation, les tâches configurées, l'activité en direct et l'état de santé pour Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music et Jellyfin" width="82%">

**Configurez un nombre illimité de synchronisations (unidirectionnelles, fusion multi-sources, groupe faisant autorité ou bidirectionnelles) dans un court assistant.**

<img src="../../.github/assets/sync-wizard.png" alt="L'assistant de configuration SongMirror sélectionnant les services pour une synchronisation bidirectionnelle entre Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music et YouTube Music" width="82%">

**Connectez tous les services de votre navigateur : OAuth en un clic, collage guidé du jeton ou touche API**

<img src="../../.github/assets/accounts.png" alt="La page Comptes pour connecter Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music et Jellyfin" width="82%">

**Parcourez et associez des listes de lecture sur tous les services**

<img src="../../.github/assets/playlists.png" alt="Parcourir les listes de lecture sur les services connectés avec les pochettes et le nombre de pistes" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Démarrage rapide

Le moyen le plus rapide de l'exécuter est Docker — Compose extrait l'image publiée, sert l'interface utilisateur Web et exécute vos synchronisations dans les délais.

Pour une installation persistante avec redémarrages automatiques :

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Ou essayez l'image publique GHCR directement sans cloner le référentiel :

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Ouvrez ensuite `http://localhost:8888` et connectez vos services dans le navigateur. La configuration Compose n'a pas besoin de `.env` pour démarrer ; tout est configuré dans l'interface utilisateur et enregistré sous `./data`.

L'option directe `docker run` est jetable : `docker stop songmirror` supprime le conteneur et sa configuration. Utilisez Compose pour une installation durable avec des informations d'identification, des caches et des téléchargements persistants, ou consultez le [guide d'image du conteneur](../docker-image.md) pour les balises et l'épinglage de résumé.

Vous préférez l'exécuter sans Docker ?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Nécessite [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Pour le miroir de téléchargement local, également `uv tool install spotdl` et ayez `ffmpeg` sur PATH.

<a id="app-language"></a>

### Langue de l'application

SongMirror prend en charge l'anglais, l'arabe, le turc, l'espagnol, le chinois simplifié, le français, le portugais, l'allemand, le japonais, l'hindi, le bengali, l'indonésien, le coréen, l'italien et le vietnamien. Au premier lancement, les préférences linguistiques du navigateur sont examinées dans l’ordre, y compris les variantes régionales, et la première langue prise en charge est utilisée. Si aucune ne convient, l’anglais est utilisé. Changez la langue dans **Paramètres → Général → Langue** ; votre choix est enregistré dans ce navigateur et conservé après rechargement. Sélectionnez **Automatique (navigateur)** pour suivre à nouveau les préférences du navigateur. L’interface arabe s’affiche de droite à gauche. Les noms de playlists, d’artistes et de services, les identifiants de connexion et les journaux de diagnostic conservent leurs valeurs d’origine.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Toujours en cours d'exécution : Docker

Le conteneur Docker est le déploiement recommandé : il sert l'interface utilisateur Web, exécute vos synchronisations selon leurs planifications et redémarre avec l'hôte. Compose extrait `ghcr.io/ahnafnafee/songmirror:latest`, l'exécute sous le nom `songmirror` et conserve tous les caches d'authentification + dans `./data`.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Pour mettre à jour, exécutez `docker compose up -d --pull always`. Pour créer la caisse actuelle, exécutez `docker compose up -d --build`. Consultez le [guide d'image du conteneur](../docker-image.md) pour les balises, l'épinglage de résumé, les extractions directes, la vérification, les mises à jour et la restauration.

Aucun `.env` n'est nécessaire pour démarrer — tout est configuré dans le navigateur et enregistré sous `./data`. La configuration des clés OAuth, du jeton de partenaire et de la clé API est disponible sur la page Comptes ; chaque assistant explique les conditions préalables spécifiques au service et l'URI de rappel exact. Créez ensuite vos synchronisations sur la page Sync.

L'ouverture de SongMirror depuis un autre ordinateur fonctionne à `http://<server>:8888`. La connexion par défaut Spotify utilise une session Web `sp_dc` collée, elle ne nécessite donc aucune application de développeur ni URL de rappel. Si vous utilisez intentionnellement l'ancienne application de développement OAuth de secours derrière Docker ou un proxy inverse, définissez l'URL de base visible par le navigateur dans `.env` :

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror annoncera alors `https://music.example.com/oauth/spotify/callback` ; enregistrez cet URI exact dans le tableau de bord de l'application Spotify et recréez le conteneur avec `docker compose up -d --force-recreate`. Un chemin de base de proxy inverse est également pris en charge (par exemple, `https://example.com/songmirror`). [Spotify nécessite HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) pour chaque redirection sans bouclage ; le simple HTTP n'est accepté qu'avec des adresses de bouclage littérales telles que `127.0.0.1`, pas une IP LAN ou `localhost`.

| | |
| --- | --- |
| Images | `ghcr.io/ahnafnafee/songmirror:latest` prend en charge AMD64 et ARM64. Chaque build est également publié avec une balise `sha-...` spécifique au commit ; Les balises Git telles que `v1.2.3` publient également `1.2.3`, `1.2` et `1`. Utilisez le [guide d'image du conteneur](../docker-image.md) pour épingler un résumé immuable. |
| Port | L'interface utilisateur est publiée sur l'hôte 8888 (le mappage `8888:8080` dans `docker-compose.yml` ; changez le côté hôte en cas de conflit). LAN uniquement — ne le transférez pas vers Internet ; l'interface utilisateur n'a pas encore d'authentification. |
| Persistance | `./data` contient les informations d'identification, les jetons, les caches, les archives de chansons et les instantanés de playlist programmés sous `playlist_backups/`. Sauvegardez-le pour conserver votre configuration et vos archives lors des reconstructions. |
| Téléchargements | Définissez `DOWNLOAD_DIR` (dans `.env` ou votre shell) sur le répertoire musical de votre hôte (par exemple `F:\Torrent\Music`) ; composer bind-le monte sur `/music`. De Docker, définissez `JELLYFIN_URL` sur `http://host.docker.internal:8096`. |
| Sessions expirées | Les sessions renouvelables sont récupérées lors du prochain passage planifié ou manuel. TIDAL Les sessions du lecteur Web sont renouvelées à partir du jeton d'actualisation capturé ; Les jetons Qobuz et Apple Music doivent toujours être recollés lorsqu'ils sont rejetés. Aucun redémarrage n'est nécessaire. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Comment ça marche

À chaque passage, pour chaque nom de playlist sélectionné qui existe sur la source :

1. Prenez un instantané de la liste de lecture source (pistes, ISRC, dates d'ajout).
2. Réconciliez simultanément la liste de lecture du même nom sur chaque cible sélectionnée et connectée via la liste de lecture autorisée par le compte de ce service API.
3. Les pistes manquantes sont résolues (liens en cache → ISRC → recherche notée) et ajoutées les plus anciennes en premier ; les traces disparues de la source sont supprimées derrière des gardes.
4. En option, [spotDL](https://github.com/spotDL/spotify-downloader) synchronise un dossier audio local par liste de lecture.

La source de vérité par défaut est Spotify, mais le mode unidirectionnel est indépendant du fournisseur : n'importe quel homologue de liste de lecture connecté peut être la source à la place.

<a id="matching"></a>

### Correspondance

Même hiérarchie que celle utilisée par les outils multiservices ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz) : identifiant exact → recherche → score flou.

1. Lien mis en cache : une fois qu'une piste source correspond à l'identifiant de catalogue/à l'identifiant vidéo d'une cible, ce lien est stocké et réutilisé (à l'abri de la dérive du titre).
2. ISRC — identité d'enregistrement exacte là où le service l'expose.
3. Recherche notée — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, sur le titre et l'artiste bruts et romanisés ([anyascii](https://github.com/anyascii/anyascii)), ancrée par la durée. Cela gère, sans codage en dur :
   - Crédits multi-artistes : un service répertorie chaque fonctionnalité, un autre répertorie la principale (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Décoration du titre — `(feat. …)`, `- 2015 Remaster`, `(From "…")`, suffixes supplémentaires "Clip officiel".
   - Translittération — Cyrillique / Bengali / Grec / Arabe (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Pistes vidéo uniquement : la recherche YouTube revient au filtre `videos` pour les pistes indépendantes/OST qui sont diffusées sur YouTube uniquement sous forme de téléchargements.

L'ancre de durée déverrouille la correspondance de titre la plus lâche, donc une version différente (`Runaway - Piano Version`) ou une reprise du mauvais artiste n'est pas acceptée lorsque sa longueur n'est pas d'accord. Les pistes sans correspondance fiable sont signalées et ignorées.

<a id="multi-source-merge-sync"></a>

### Synchronisation de fusion multi-sources

Une tâche Fusionner les sources combine une ou plusieurs listes de lecture explicites dans une destination choisie. Chaque source peut provenir de la bibliothèque d'un compte connecté ou d'une URL de fournisseur public collée ; cette dernière est résolue une fois en un fournisseur et un identifiant de playlist, de sorte que la playlist n'a pas besoin d'être enregistrée ou suivie et les exécutions planifiées ne rejouent pas une URL arbitraire.

- Un syndicat de membres – tous les constituants sont lus avant que la destination ne soit conciliée. Les ISRC partagés constituent un seul enregistrement ; sans un ISRC, un titre exact/conservateur, un artiste, une version et une preuve de durée dédupliquent les chevauchements.
- Ordre déterministe : priorité du descripteur de source en premier, puis ordre renvoyé par chaque liste de lecture source. La première occurrence possède la position de destination et affiche les métadonnées ; les copies ultérieures ne font qu'enrichir les métadonnées d'identité manquantes.
- Suppressions sécurisées pour l'Union : une piste de destination ne peut être supprimée que lorsqu'un passage complet la trouve absente de chaque source constitutive. Une source échouée, tronquée, mal formée, indisponible ou vide de manière inconnaissable désactive chaque suppression pour cette passe, tandis que les ajouts sécurisés à partir de sources lisibles peuvent continuer.
- Ajout uniquement par défaut : laissez Supprimer les pistes absentes de chaque source désactivée pour conserver toutes les pistes de destination uniquement. L'activer permet d'activer le capuchon de suppression normal par passage après le passage de la garde en lecture complète.

Les tâches de fusion ciblent actuellement une liste de lecture de fournisseur ; le miroir séparé de téléchargement local/Jellyfin dirigé par Spotify n'est pas disponible pour une tâche agrégée.

<a id="authoritative-groups"></a>

### Groupes faisant autorité

Utilisez un groupe faisant autorité lorsque vous organisez activement la même liste de lecture logique sur deux services ou plus, mais que vous souhaitez que tous les autres services sélectionnés les suivent. Une configuration typique est Spotify + Apple Music comme autorités, avec TIDAL, Qobuz, Deezer, Amazon Music et YouTube Music comme miroirs.

- L'adhésion provient uniquement des autorités — une piste ajoutée sur Spotify ou Apple Music se propage à l'autre autorité et à chaque miroir. Une trace ajoutée uniquement sur un miroir est une dérive ; il n'est jamais réimporté dans les autorités.
- Une autorité de commande : choisissez quelle autorité fournit les noms des listes de lecture et l'ordre des ajouts. Les autres autorités contribuent toujours aux changements d'adhésion.
- Les suppressions confirmées se propagent à partir de l'une ou l'autre autorité : une absence doit apparaître dans deux lectures complètes consécutives avant de pouvoir supprimer quoi que ce soit. Un ajout simultané du côté de l’autorité l’emporte sur une suppression.
- Les miroirs n'obtiennent jamais de vote : la suppression d'une piste d'un miroir répare ce miroir ; il ne supprime pas la piste de Spotify ou Apple Music.
- Premier passage sécurisé : chaque ensemble d'autorités a sa propre ligne de base. Sa première passe réussie peut ajouter des pistes manquantes, mais conserve toutes les suppressions jusqu'à ce qu'une passe ultérieure prouve que la ligne de base est stable.
- Échec fermé — si une autorité est déconnectée, illisible ou si sa liste de lecture ne peut pas être ouverte/créée, cette liste de lecture logique est ignorée au lieu de revenir silencieusement à moins d'autorités.

Les suppressions nécessitent une activation explicite et restent plafonnées. Activez **Répercuter les suppressions** pour la tâche, ou définissez `MAX_REMOVALS` en mode sans interface graphique, pour retirer des miroirs les morceaux absents de l’ensemble des sources faisant autorité.

<a id="bidirectional-n-way-sync"></a>

### Synchronisation bidirectionnelle (N-way)

Par défaut, un fournisseur est la source de vérité et les modifications s'effectuent dans un sens. En mode N-way, chaque fournisseur sélectionné est un homologue : ajoutez ou supprimez une piste sur l'un d'entre eux et le changement se propage aux autres.

La synchronisation bidirectionnelle est impossible sans état, de sorte que l'appartenance canonique de chaque liste de lecture logique est instantanée après chaque passe propre. Chaque passe compare chaque fournisseur à cet instantané, regroupe les modifications et réconcilie tout le monde avec le résultat :

- Sans écho : un ajout propagé devient partie intégrante de l'instantané et n'est donc jamais renvoyé.
- Add-wins sur les conflits – perdre une chanson est pire que d’en garder une supplémentaire.
- Protection contre l'effondrement de la lecture - si un fournisseur lit soudainement beaucoup moins de pistes que la ligne de base (un hoquet passager API), cette passe est ignorée afin qu'une mauvaise lecture ne puisse pas entraîner une suppression en masse.
- Mêmes garanties que pour un aller simple : les plafonds `MAX_ADDS` / `MAX_REMOVALS` par passage et la protection contre les pertes nettes sont maintenus sur chaque côté d'écriture.
- **Les suppressions sont facultatives** : `MAX_REMOVALS` vaut 0 par défaut. Un morceau qui disparaît d’un service, qu’il y ait été supprimé ou retiré pour des raisons de licence, est conservé sur les autres et le changement est seulement journalisé. Définissez un plafond ou activez **Répercuter les suppressions** dans l’interface pour propager les suppressions.

> Toujours la simulation en premier. Exécutez sans `--execute` (ou utilisez Aperçu dans l'interface utilisateur) et lisez le plan - il imprime chaque ajout/suppression proposé sur chaque fournisseur avant que quoi que ce soit ne soit écrit.

<a id="liked-and-favorite-tracks"></a>

### Pistes aimées et préférées

À l'étape Listes de lecture d'une synchronisation, sélectionnez la collection appréciée intégrée au service source. SongMirror demande ensuite où il doit aller sur chaque destination sélectionnée : directement dans la collection aimé/favori de ce service, ou dans une nouvelle liste de lecture dont vous pouvez modifier le nom suggéré. Une nouvelle sélection est appréciée uniquement ; activez également Synchronisez chaque liste de lecture régulière ou choisissez des listes de lecture individuelles pour inclure les deux.

Cela fonctionne sur Spotify Chansons aimées, TIDAL/Qobuz/Deezer Pistes préférées, Amazon Music Mes goûts, Apple Music Chansons préférées et YouTube Music Musique aimée. Les mêmes chemins de réconciliation et plafonds de sécurité à sens unique, de groupe faisant autorité et à N voies s'appliquent. Comme pour les listes de lecture ordinaires, les suppressions restent désactivées par défaut tant que l’option **Répercuter les suppressions** n’est pas activée.

La subvention de lecteur Web connecté de TIDAL gère à la fois les listes de lecture ordinaires et les morceaux favoris natifs lorsqu'elle contient `r_usr` et `w_usr`. La capture de la réponse complète du jeton de connexion donne SongMirror le jeton d'actualisation ainsi que le Bearer de courte durée, afin que la session puisse se renouveler automatiquement.

Certaines de ces intégrations utilisent les interfaces Web propriétaires des fournisseurs et peuvent changer sans préavis ; le [évaluation de faisabilité](../design/2026-09-01-liked-tracks-sync-feasibility.md) enregistre le API et les contraintes de distribution pour chaque fournisseur.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Sauvegardes des métadonnées de la playlist

Les sauvegardes ne nécessitent pas de deuxième fournisseur ni de tâche de synchronisation :

- Dans Paramètres → Sauvegardes de playlist, utilisez Ajouter une sauvegarde en haut pour ajouter un compte connecté. Choisissez JSON ou XML, puis sélectionnez une fréquence telle que quotidienne ou hebdomadaire. Les intervalles personnalisés utilisent un nombre et une unité. Conserver les sauvegardes propose des préréglages de conservation, un nombre personnalisé ou Toutes les sauvegardes.
- Les sauvegardes sont par défaut `data/playlist_backups/<account-profile-id>/` (ou `/data/playlist_backups/<account-profile-id>/` dans Docker). Cliquez sur Dossier de sauvegarde pour le sélecteur de dossier intégré ou choisissez Entrer le chemin manuellement. Un dossier personnalisé obtient toujours un sous-dossier distinct pour chaque compte. Utiliser le dossier de sauvegarde par défaut restaure la valeur par défaut. Le changement d'emplacement affecte les sauvegardes futures ; les anciens fichiers restent là où ils se trouvent. La conservation et le dernier téléchargement s'appliquent à l'emplacement sélectionné. La suppression d'un planning ne supprime jamais les fichiers enregistrés.
- Paramètres → Téléchargements & Jellyfin → Le dossier de téléchargement utilise le même sélecteur intégré et la même entrée manuelle. Choisissez un dossier accessible à votre bibliothèque Jellyfin. Les téléchargements suivent le calendrier de chaque synchronisation activée dans l'onglet Sync. Le sélecteur affiche les chemins d'hôte configurés (par exemple, `F:\Torrent\Music`) tout en conservant leur mappage Docker (`/music`) en interne. Les montages de téléchargement existants sont inchangés. Les dossiers hôtes supplémentaires doivent d'abord être partagés en tant que montages de liaison Docker ; le choix d'un dossier non monté affiche une erreur et laisse le paramètre actuel inchangé.

- La même carte Paramètres affiche la prochaine exécution, le nombre d'instantanés stockés, le dernier fichier et le nombre de réussites, ainsi que l'échec le plus récent. Sauvegarder maintenant met en file d'attente une exécution sécurisée à la demande ; Télécharger le dernier récupère l’instantané persistant le plus récent.
- Sur la page Playlists, utilisez Exporter sur une carte de service pour télécharger chaque playlist de ce service dans un fichier versionné JSON ou XML.
- Ouvrez une playlist pour exporter uniquement cette playlist. Son option Soundiiz suit [Forme d'importation documentée de Soundiiz JSON](https://soundiiz.com/data/fileExamples/playlistExport.json), de sorte que la liste des pistes téléchargées peut être téléchargée via le flux Importer la liste de lecture → À partir du fichier de Soundiiz.
- SongMirror JSON/XML préserve l'ordre et les noms des listes de lecture ainsi que les identifiants des pistes/occurrences du fournisseur, les ISRC disponibles, les artistes, les albums, les positions des pistes d'album, les durées, les dates ajoutées, les liens d'illustration et les marqueurs d'entrée indisponibles. Les fantômes de catalogue sans ID restent dans la sauvegarde au lieu de disparaître. Les fichiers ne contiennent aucun cookie, jeton, en-tête de requête, aperçu ou URL de fichier de streaming.

Les exportations manuelles sont téléchargées par le navigateur sur l'appareil exécutant l'interface utilisateur. Les exportations planifiées utilisent le volume de données d'application existant, donc aucun deuxième chemin d'hôte ou montage de conteneur n'est requis. La sauvegarde lit la file d'attente derrière les synchronisations et les transferts au lieu d'accéder simultanément aux clients du fournisseur. Le champ `schema_version` permet aux versions futures de faire évoluer le format sans perte sans rendre les anciens instantanés ambigus.

<a id="built-in-folder-picker"></a>

### Sélecteur de dossiers intégré

Cliquez sur un champ de dossier ou Parcourir… pour ouvrir le sélecteur intégré. Utilisez Emplacements, fil d'Ariane cliquable, Précédent, Suivant et Haut d'un dossier pour naviguer. Cliquez sur un dossier pour le sélectionner ; double-cliquez, appuyez sur Entrée ou utilisez sa flèche pour l'ouvrir. La recherche filtre le dossier actuel. Entrez un chemin de dossier et accepte une adresse complète. Le dossier sélectionné met à jour le brouillon ; enregistrez les paramètres ou le calendrier pour l'appliquer. Annuler laisse le brouillon inchangé. Aucune aide de bureau ou processus supplémentaire n'est requis.

Nouveau dossier crée un sous-dossier nommé à l'emplacement actuellement ouvert, puis l'ouvre. Les éléments existants ne sont jamais écrasés. L'annulation de la saisie d'un nom ne crée rien ; l'annulation du sélecteur après la création laisse le nouveau dossier sur le disque. Votre emplacement de sauvegarde ou de téléchargement enregistré ne change qu'après la sélection et l'enregistrement. Dans Docker, le sélecteur explique quels chemins sont partagés et affiche à la fois le chemin du conteneur et son chemin d'ordinateur configuré lorsqu'il est disponible.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Miroir de téléchargement local (Jellyfin)

Conservez une copie audio hors ligne de chaque playlist synchronisée, un dossier par playlist, via [spotDL](https://github.com/spotDL/spotify-downloader). La synchronisation est une véritable mise en miroir : les nouvelles pistes sont téléchargées, les pistes supprimées sont supprimées localement. La mise en page est prête pour Jellyfin — pointez une bibliothèque musicale Jellyfin vers le répertoire de téléchargement et les pistes et les listes de lecture apparaissent, restant mises à jour à chaque passage :

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Activez-le en définissant `DOWNLOAD_DIR` et en installant spotDL + ffmpeg :

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Incrémentiel — après le premier téléchargement complet, seules les pistes nouvellement ajoutées sont récupérées ; les pistes supprimées (et leurs dossiers d'album vidés) sont élagués. Une course interrompue continue au prochain passage.
- Le plus récent en premier `.m3u8` — écrit par ordre de date ajoutée, le plus récent en haut (définissez `LOCAL_MIRROR_ORDER=oldest` pour retourner). Reconstruisez les couvertures/tags/mtimes à partir de fichiers existants avec `uv run main.py --refresh-local`.
- Couvertures de playlist dans Jellyfin — Jellyfin ignore un fichier de couverture à côté d'un m3u, alors définissez `JELLYFIN_URL` + `JELLYFIN_API_KEY` et chaque passe télécharge la véritable couverture de playlist via Jellyfin API.
- Qualité audio : la source est YouTube, donc sans cookie YT Music Premium, le plafond est d'environ 128 à 160 kbps. `LOCAL_MIRROR_FORMAT=opus` conserve le flux natif de YouTube sans réencodage mp3 ; un cookie Premium (`LOCAL_MIRROR_COOKIE_FILE`) déverrouille 256 kbps AAC. La sélection de `flac` modifie le conteneur de sortie mais ne peut pas transformer une source avec perte en audio sans perte.

Le chemin FLAC actuel de Monochrome utilise des ressources de lecture à usage unique, contrôlées par le navigateur, plutôt qu'un fichier d'exportation stable et autorisé par le fournisseur API, donc SongMirror ne l'automatise pas. Utilisez le miroir local uniquement pour le contenu que vous possédez ou que vous êtes autorisé à copier.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Connexion de chaque service

Dans l'application Web, la page Comptes vous guide à travers chaque service et affiche les valeurs exactes à coller. Rien n'est mandaté par un tiers.

<a id="credential-renewal"></a>

### Renouvellement des informations d'identification

SongMirror actualise les informations d'identification juste à temps, et non avec un minuteur d'actualisation de jeton distinct. Chaque passe de synchronisation manuelle ou planifiée valide les connecteurs qu'elle utilise et renouvelle les jetons d'accès pris en charge avant la première demande (ou une fois après un rejet d'authentification). Il est normal qu'un jeton d'accès de courte durée expire entre les passes : ce qui compte, c'est le jeton d'actualisation durable ou le cookie de renouvellement. La page Comptes valide l'état lorsqu'elle se charge ou reprend le focus, mais il ne s'agit pas de la maintenance de session en arrière-plan ; les planifications de synchronisation activées le sont.

| Services | Comportement de renouvellement |
| --- | --- |
| Spotify | La connexion par défaut crée un jeton d'accès au lecteur Web à partir du cookie `sp_dc` enregistré à la demande et réessaye avec un nouveau jeton après un `401` ; la session de connexion sous-jacente peut toujours être révoquée. L'ancienne application de développement OAuth reste prise en charge pour les installations existantes. |
| TIDAL | Le jeton d'accès au lecteur Web importé se renouvelle automatiquement via `auth.tidal.com` à l'aide du jeton d'actualisation de la réponse de connexion. SongMirror conserve le jeton d'actualisation existant lorsqu'une réponse l'omet et conserve un jeton pivoté lorsque TIDAL en renvoie un. La déconnexion ou la révocation nécessite toujours une nouvelle capture. |
| Qobuz | Le `X-User-Auth-Token` collé est utilisé jusqu'à ce que Qobuz le rejette, puis doit être à nouveau capturé. |
| Deezer | Le Pipe de courte durée JWT se renouvelle automatiquement à partir du `refresh-token` enregistré avant utilisation et une fois après un `401/403` ; l’état de renouvellement en rotation est conservé. |
| Amazon Music | Le jeton d'accès Web se renouvelle via `/pandaToken` à l'aide de l'agent utilisateur du navigateur capturé, du référent et des cookies autorisés. Le flux actuel `POST config.json?skipToken=false` amorce le contexte du périphérique lorsque cela est nécessaire et les cookies pivotés sont conservés. La déconnexion, les modifications de sécurité ou la révocation côté serveur nécessitent toujours une nouvelle capture. |
| Apple Music | Les Bearer et Media-User-Token collés ne peuvent pas être renouvelés par SongMirror et doivent être à nouveau capturés après rejet. |
| YouTube Music | Data API OAuth s'actualise automatiquement dans les 60 secondes suivant l'expiration. Le mode navigateur tente la rotation des cookies de Google chaque fois qu'une cible de synchronisation est créée ; une session de navigateur déjà expirée doit être à nouveau exportée. |
| Jellyfin | La clé API n'a pas de cycle de rafraîchissement du jeton d'accès ; remplacez-le uniquement s’il est révoqué ou supprimé. |

<a id="spotify"></a>

### Spotify

1. Connectez-vous à <https://open.spotify.com>.
2. Ouvrez le navigateur DevTools (`F12`) → Application (Chrome/Edge) ou Stockage (Firefox) → Cookies → `https://open.spotify.com`.
3. Copiez la valeur du cookie `sp_dc` et collez-la dans Comptes → Spotify.

Cette session Web à connexion unique gère la navigation dans la bibliothèque, les lectures et écritures de listes de lecture et la recherche dans le catalogue. Il ne nécessite pas d'application de développeur Spotify, de clé API ou de compte Premium. Traitez `sp_dc` comme un mot de passe : SongMirror le stocke dans son répertoire de données privé, mais l'intégration utilise les opérations internes du lecteur Web de Spotify et peut nécessiter une maintenance si Spotify les modifie. Les informations d'identification de l'application de développement existantes OAuth restent une solution de secours compatible.

<a id="tidal"></a>

### TIDAL

1. Ouvrez [Lecteur Web de TIDAL](https://listen.tidal.com), ouvrez DevTools → Réseau et activez Conserver le journal.
2. Déconnectez-vous et reconnectez-vous, puis filtrez la liste des réseaux pour `oauth2/token`.
3. Sélectionnez la demande `auth.tidal.com/v1/oauth2/token` réussie. Dans Payload (Chrome/Edge) ou Request (Firefox), copiez la valeur du formulaire `client_id` dans le champ ID client du lecteur Web de SongMirror.
4. Ouvrez l'onglet Réponse de la demande et copiez son JSON complet dans la réponse du jeton du lecteur Web. Il doit inclure à la fois `access_token` et `refresh_token`.
5. Connectez-vous. SongMirror exerce immédiatement l'autorisation d'actualisation et refuse de signaler le succès si cet ID client ne peut pas le renouveler.

L'ID client OAuth est une métadonnée de demande et n'est pas la revendication numérique `cid` à l'intérieur du jeton d'accès TIDAL. SongMirror extrait uniquement le jeton d'accès, le jeton d'actualisation, l'ID client, les étendues, l'expiration et le pays du catalogue ; les données de réponse sans rapport sont supprimées. Il se renouvelle juste avant l'expiration et une fois après un rejet d'authentification via `https://auth.tidal.com/v1/oauth2/token`, préservant la rotation des jetons d'actualisation. L'ancien collage d'en-tête de requête OpenAPI reste compatible, mais comme il ne contient aucun jeton d'actualisation, il doit toujours être recollé après expiration. Seules les métadonnées du catalogue et les listes de lecture de l'utilisateur connecté sont utilisées : les ressources de lecture restent en dehors de cette intégration.

<a id="qobuz"></a>

### Qobuz

Connectez-vous à <https://play.qobuz.com>, ouvrez DevTools → Réseau et filtrez pour `api.json/0.2`. Choisissez n'importe quelle requête contenant `X-App-Id` et `X-User-Auth-Token`, y compris une requête authentifiée `album/story`, puis copiez ses en-têtes de requête ou copiez-la en tant que cURL et collez-la dans l'assistant. SongMirror conserve uniquement ces deux valeurs, les envoie en utilisant le même flux basé sur l'en-tête que le lecteur Web et supprime les cookies et les métadonnées du navigateur sans rapport. Aucune approbation commerciale API ou identifiant d'utilisateur n'est requis ; Les informations d’identification des partenaires existantes restent un environnement de secours compatible.

L'adaptateur utilise uniquement les points de terminaison de recherche de catalogue et de liste de lecture : il ne demande pas d'URL de flux ou de fichier.

<a id="deezer"></a>

### Deezer

Connectez-vous à <https://www.deezer.com>, ouvrez DevTools → Réseau et rechargez la page. Filtrez pour `auth.deezer.com/login/renew`, copiez les en-têtes de cette demande (ou copiez-la sous forme cURL) et collez-la dans le champ de renouvellement. Firefox peut à la place copier les cookies de demande sous la forme d'un bloc délimité par des points-virgules ; cette forme est également acceptée. SongMirror conserve uniquement le cookie dédié `refresh-token` et l'utilise pour renouveler automatiquement le Pipe JWT de courte durée de Deezer. Vous pouvez également coller une requête `pipe.deezer.com/api` actuelle comme démarrage immédiat, mais cela n'est pas requis lorsque le renouvellement est configuré. Les ajouts et suppressions de playlist utilisent tous deux la session Pipe renouvelable ; aucun cookie `arl` n'est nécessaire. Les jetons de développeur existants OAuth restent une solution de secours pour l'environnement compatible.

<a id="amazon-music"></a>

### Amazon Music

Aucune approbation du développeur n’est requise pour le connecteur par défaut. Il utilise les mêmes routes authentifiées GraphQL et de renouvellement de jetons que le lecteur Web Amazon Music :

1. Connectez-vous à <https://music.amazon.com> et ouvrez DevTools → Réseau.
2. Rechargez la page, filtrez pour `config.json` et sélectionnez la demande connectée. (`pandaToken` fonctionne également lorsqu'il apparaît, mais ce n'est pas obligatoire.)
3. Choisissez Copier les en-têtes de demande ou Copier en tant que cURL, puis collez-le dans le champ de renouvellement. Conservez les en-têtes complets `User-Agent`, `Referer` et `Cookie` afin que SongMirror puisse rejouer le même contexte de navigateur.
4. Copiez éventuellement la réponse `config.json` de connexion dans le champ d'amorçage ; SongMirror peut normalement récupérer le contexte de cet appareil à l'aide de la session de renouvellement.

SongMirror dérive localement la même valeur d'autorisation `AmznMusic` et la rafraîchit via `music.amazon.com/pandaToken` avant l'expiration ou une fois après un rejet d'authentification. Pendant la connexion, il utilise la demande de configuration actuelle de style navigateur lorsque le contexte de l'appareil est nécessaire, nécessite `/pandaToken` pour créer un jeton d'accès et rejette la connexion si Amazon révoque le cookie de renouvellement de musique. Il stocke uniquement l'agent utilisateur du navigateur, la langue, le référent Music, une liste autorisée nommée de cookies d'authentification/de session Amazon et le contexte limité de l'appareil client Music ; les analyses, les expériences, la console AWS, CSRF et autres données de navigateur non liées sont supprimées. Ces cookies conservés sont toujours sensibles, alors gardez SongMirror privé sur votre LAN. Une déconnexion, un changement de mot de passe/de sécurité ou une révocation côté Amazon peuvent toujours nécessiter une nouvelle capture.

Il s'agit d'une interface client Web propriétaire non prise en charge et Amazon peut la modifier sans préavis. Le [Amazon Music Web API](https://developer.amazon.com/docs/music/API_web_overview.html) documenté est toujours une version bêta fermée ; Les informations d'identification du partenaire approuvées restent une solution de secours facultative lorsqu'elles sont configurées via des variables d'environnement.

<a id="apple-music"></a>

### Apple Music

Aucun compte de développeur Apple n'est nécessaire : deux en-têtes de `music.apple.com` suffisent. Ouvrez <https://music.apple.com>, connectez-vous, ouvrez DevTools → Réseau, écoutez une chanson, filtrez pour `amp-api.music.apple.com` et copiez à partir des en-têtes de toute demande :

- Jeton `authorization: Bearer eyJ...` → Bearer (la partie `eyJ...`, sans `Bearer `)
- `media-user-token: ...` → Jeton utilisateur (valeur totale)

L'assistant de connexion vous permet de coller les en-têtes bruts et d'analyser les valeurs pour vous. Jetons les derniers mois ; recollez-les sur la page Comptes lorsqu'ils expirent.

Un identifiant Apple sans abonnement Apple Music actif peut toujours se connecter en mode Catalogue uniquement. Dans ce mode, collez un lien de playlist public Apple Music sur Transferts pour le copier dans un autre service connecté. La navigation dans la bibliothèque Apple, la synchronisation programmée et l'utilisation de Apple Music comme destination de transfert nécessitent toujours le privilège payant CloudLibrary ; SongMirror affiche ces opérations comme indisponibles au lieu de traiter les informations d'identification de catalogue valides comme expirées.

<a id="youtube-music"></a>

### YouTube Music

Parle au officiel [YouTube Data API v3](https://developers.google.com/youtube/v3), dont le jeton d'actualisation OAuth est durable et survit aux redémarrages.

1. Dans le [GoogleConsole cloud](https://console.cloud.google.com), créez un projet, activez YouTube Data API v3 et créez un client OAuth de type téléviseurs et périphériques d'entrée limités.
2. Sur l'écran de consentement OAuth, définissez le statut de publication → En production (le laisser dans « Test » fait expirer le jeton après 7 jours).
3. Dans l'application, collez l'ID client + le secret et complétez le code de l'appareil à l'écran.

> Quota : le Data API autorise 10 000 unités/jour (une recherche coûte 100, un ajout/suppression 50). L’entretien à l’état d’équilibre est bon marché ; un retard important pour la première fois peut atteindre le plafond et reprendre le lendemain.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ sans interface graphique CLI

Vous préférez `.env` + cron / Task Scheduler ? Le même moteur fonctionne sans interface graphique.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Drapeaux utiles :

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Vars d'environnement clés (voir `.env.example`) : les informations d'identification des fournisseurs que vous utilisez, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` et `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Mesures de sécurité

Les déménagements sont destructeurs, ils sont donc gardés :

- la simulation est la valeur par défaut — rien ne change sans `--execute` (ou l'action de synchronisation réelle de l'interface utilisateur).
- Si la source renvoie 0 piste pour une playlist que la cible affiche comme non vide, les suppressions sont ignorées (un échec transitoire API ne peut pas vider une playlist).
- **Les suppressions sont désactivées par défaut** : `MAX_REMOVALS=0` bloque chaque suppression ; elle est journalisée, jamais appliquée. Le retrait d’un morceau pour des raisons de licence sur une plateforme ne peut donc pas entraîner sa suppression sur les autres. Activez **Répercuter les suppressions** pour chaque synchronisation ou définissez `MAX_REMOVALS`. Même après activation, si le nombre de suppressions en attente dépasse le plafond lors d’un passage, elles sont toutes ignorées et journalisées.
- `MAX_ADDS` limite chaque écriture produisant un horodatage lors d'une passe de synchronisation, y compris la réparation de la chronologie. Si une correspondance récupérée plus ancienne nécessite une relecture de suffixe plus grande que celle autorisée par le plafond, SongMirror la reporte à la passe suivante plutôt que de la faire apparaître comme la plus récente ou de provoquer une explosion géante du fournisseur. Un transfert unique n'a pas de passe suivante, il ne diffère donc jamais : il copie chaque piste demandée, en l'ajoutant dans l'ordre source, sauf si vous activez "Conserver l'ordre récemment ajouté" pour ce transfert, qui dépense quels que soient les coûts de réparation.
- Une réparation chronologique étape une copie en double avant de retirer l'original. Sur un service dont la suppression prend chaque copie d'une chanson, ce nombre de gardiens doit être correct, donc Apple Music relit jusqu'à ce que les copies mises en scène soient visibles et refuse de retirer quoi que ce soit contre une lecture qui traîne encore ses propres écritures. Deezer ignore entièrement la réparation et ajoute toujours : il n'a pas non plus d'insertion de position, donc rejouer une commande qu'il ne peut pas exprimer ne vaut pas le risque pour la destination. Le formulaire de transfert grise son commutateur de commande et indique pourquoi.
- Protection contre les pertes nettes : une piste côté cible ressemblant à une piste source qui n'a aucune correspondance sur ce service est conservée et non supprimée.
- Tout échec d'authentification du fournisseur annule immédiatement le laissez-passer de ce fournisseur – aucune suppression partielle sur les jetons expirés.
- Une tâche de fusion doit terminer la lecture de chaque source constitutive avant de la supprimer de sa destination ; toute force d'instantané source partiel/échoué qui passe en comportement d'ajout uniquement.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Mise en cache et archives de chansons

Tout ce qui peut être résolu est mis en cache afin que les passes en état stable soient quasi instantanées : des caches de résolution par service (ISRC + recherche, y compris les échecs), un cache de liste de pistes à clé `snapshot_id`, des liens d'identification exacts dans SQLite et un saut d'instantané par paire (`unchanged since last clean sync`).

Chaque passe archive également les métadonnées de chaque piste qu'il voit dans `song_cache.db` – un fichier SQLite qui ne fait que croître. Les pistes supprimées restent archivées avec le nom, l'artiste, l'album, la durée, ISRC, l'instantané brut JSON et les horodatages du premier/dernier affichage :

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Résoudre les mappages

Chaque service conserve son propre cache de résolution, mappant une clé `title|artist` normalisée à l'identifiant de catalogue auquel elle correspond
ce service. Une correspondance est réutilisée pour toujours, tout comme un résultat « aucune correspondance », ce qui fait qu'une piste a échoué
pour correspondre une fois, rester inégalé à chaque passe ultérieure.

La page Mappages de l'interface utilisateur Web expose ces caches directement, par service :

- rechercher dans tout le cache par titre, artiste ou identifiant résolu
- filtrer les entrées définies manuellement (une correspondance que vous avez choisie dans l'éditeur de conflit de transfert) ou les entrées sans correspondance
- corrigez un mauvais identifiant en collant le lien de la bonne piste, ou supprimez un mappage pour que le prochain passage le recherche à nouveau
- effacer chaque entrée « aucune correspondance » pour un service en une seule action, afin qu'un lot de recherches échouées reçoive un nouvel essai

Lorsqu'un échec résolu est résolu plus tard, le simple fait de l'ajouter fera apparaître l'ancienne chanson comme la plus récente. Pour la liste de lecture
destinations, SongMirror rejoue à la place cette chanson et le suffixe le plus récent déjà présent, du plus ancien au plus récent, puis supprime
les exemplaires les plus anciens. Les fournisseurs ne permettent pas aux clients de restaurer les horodatages d'origine, mais cela préserve leur horodatage relatif.
Commande récemment ajoutée. Les collections natives aimées/favorites restent réservées aux membres et ne sont jamais rejouées.

Les modifications sont refusées avec un message clair pendant qu'une synchronisation est en cours, car une passe conserve le cache en mémoire pour son
toute la durée et les écraserait à la fin.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Disposition du projet

Entrée CLI : `uv run main.py` (cale fine) ou `python -m songmirror`. Entrée Web : `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Ajout d'un autre service : sous-classe `MirrorTarget`, implémentez ~8 méthodes, ajoutez son constructeur à `engine/targets`' `_REGISTRY` et sa classe à `_CLASSES`, et ajoutez un `Connector` correspondant sous `services/accounts`. Tous les rapprochements (diff, classement, mesures de sécurité, journalisation, saut d'instantané) sont hérités.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Dépannage

- `Missing required environment variable` — remplissez `.env` (CLI) ou connectez le service dans l'interface utilisateur.
- TIDAL rapporte `Expired` — déconnectez-vous et reconnectez-vous à `listen.tidal.com`, puis collez à la fois le `client_id` de la charge utile de la demande `oauth2/token` et sa réponse complète JSON dans les comptes. Une demande OpenAPI copiée n'a que le Bearer de courte durée et ne peut pas être renouvelée.
- TIDAL rapporte HTTP 429 — il s'agit d'une limite de débit temporaire, pas d'une connexion expirée. SongMirror respecte le délai de nouvelle tentative du fournisseur et met en cache les vérifications de l'état du compte au lieu de sonder à plusieurs reprises le API.
- Qobuz ou Apple rapporte `Expired` / `401` / `403` — ces sessions collées n'ont pas de secret renouvelable ; capturez une nouvelle demande de connexion ou un jeton dans les comptes.
- TIDAL indique que le jeton n'a pas d'accès à la piste appréciée - capturez une nouvelle réponse de jeton de lecteur Web connecté portant `r_usr` et `w_usr`.
- Le renouvellement Deezer échoue : capturez une nouvelle demande `auth.deezer.com/login/renew` (ou son cookie `refresh-token`). Un Pipe actuel Bearer à lui seul n'est qu'un bootstrap temporaire.
- Le renouvellement Amazon Music échoue : capturez une nouvelle demande `POST /config.json?skipToken=false` connectée avec ses en-têtes complets `User-Agent`, `Referer` et `Cookie`. La réponse JSON est facultative.
- Le mode navigateur YouTube Music expire : exportez les nouveaux en-têtes de requête du navigateur. Pour la configuration sans surveillance la plus durable, utilisez Data API OAuth avec un écran de consentement en production.
- Spotify rapports expirés — reconnectez-vous à `open.spotify.com` et collez un nouveau cookie `sp_dc` dans Comptes.
- Une playlist ne se synchronise pas : confirmez qu'elle se trouve dans la portée de la playlist de synchronisation et qu'elle existe sur la source (les cibles sont créées automatiquement lors d'une passe réelle).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Licence

Droits d'auteur © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Ce projet est sous licence [MIT](../../LICENSE).

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
