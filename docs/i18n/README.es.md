<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Sincronización de listas de reproducción autohospedadas y siempre activas para Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music y YouTube Music, además de un espejo de audio local listo para Jellyfin.<br/>
Una alternativa gratuita, de código abierto y autohospedada a Soundiiz, TuneMyMusic y FreeYourMusic que usted posee y administra.

**Sincronización unidireccional, de fusión de múltiples fuentes, de grupo autorizado o completamente bidireccional (N-direccional) · transferencias de listas de reproducción únicas · coincidencia precisa por ISRC · todo desde su navegador**

[Inicio rápido](#quick-start) · [Características](#features) · [Capturas de pantalla](#screenshots) · [Siempre corriendo: Docker](#always-running-docker) · [Cómo funciona](#how-it-works) · [Informar de un error][github-issues-link] · [Solicitar una función][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Comparte este proyecto**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Configúralo una vez: cada lista de reproducción que seleccionas permanece reflejada en todos los servicios, en orden de fecha de adición.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="Demostración SongMirror: revelación de logotipo, panel de control, configuración de sincronización unidireccional y bidireccional, transferencias de listas de reproducción en vivo y coincidencias precisas mediante ISRC en siete servicios de música" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">Mira la versión 1080p</a></sup>

</div>

> [!NOTE]
> Aplicación web + sin interfaz gráfica CLI, un motor. Haga clic en la interfaz de usuario de un navegador para conectar servicios, crear sincronizaciones y transferir listas de reproducción, o ejecútelo `.env` + estilo cron. Ambos manejan el mismo núcleo de sincronización.

<details>
<summary><kbd>Tabla de contenido</kbd></summary>

#### TOC

- [✨ Características](#features)
- [📸 Capturas de pantalla](#screenshots)
- [🚀 Inicio rápido](#quick-start)
  - [Idioma de la aplicación](#app-language)
- [🐳 Siempre corriendo: Docker](#always-running-docker)
- [⚙️ Cómo funciona](#how-it-works)
  - [Coincidencia](#matching)
  - [Sincronización de fusión de múltiples fuentes](#multi-source-merge-sync)
  - [Grupos autorizados](#authoritative-groups)
  - [Sincronización bidireccional (N-way)](#bidirectional-n-way-sync)
- [📦 Copias de seguridad de metadatos de listas de reproducción](#playlist-metadata-backups)
- [💿 Espejo de descarga local (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Conectando cada servicio](#connecting-each-service)
  - [Renovación de credencial](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ sin interfaz gráfica CLI](#headless-cli)
- [🛡️ Medidas de seguridad](#safety-rails)
- [🗃️ Almacenamiento en caché y archivo de canciones](#caching-song-archive)
  - [Resolver asignaciones](#resolve-mappings)
- [🧱 Diseño del proyecto](#project-layout)
- [🩺 Solución de problemas](#troubleshooting)
- [📄 Licencia](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Características

SongMirror mantiene tus listas de reproducción idénticas en todas partes sin necesidad de volver a agregarlas manualmente, copiarlas una por una o tener un servicio en la nube pago que contenga tu biblioteca. Es multiplataforma, autohospedado y de código abierto.

- 🔁 **Duplicación verdadera, no solo agregar**: adiciones y eliminaciones. Elija una fuente de verdad (Spotify por defecto) y los demás la seguirán.
- ⇆ **Grupos autorizados**: confíe en dos o más servicios (por ejemplo, Spotify + Apple Music), mientras que todos los demás servicios seleccionados siguen siendo un espejo de solo destino.
- ⇄ **Sincronización bidireccional de N vías**: una adición o eliminación en cualquier servicio conectado se propaga a todos los demás, sin eco, detrás de protecciones de eliminación.
- ⇉ **Sincronización de fusión de múltiples fuentes**: programe la unión deduplicada de listas de reproducción de bibliotecas y URL de listas de reproducción públicas en un destino, sin guardar ni seguir las listas públicas.
- ♥ **Pistas que me gustan y favoritas**: sincroniza la colección integrada de Me gusta de cada servicio en los siete proveedores de música, ya sea en los favoritos del destino o en una nueva lista de reproducción con nombre.
- 🎯 **coincidencia precisa por ISRC**: identidad de grabación exacta cuando esté disponible, con reservas aproximadas de título/artista/duración compatibles con Unicode (diferencias en los créditos de los artistas destacados, sufijos "- 2015 Remaster", guiones no latinos, cargas de solo videos, todo manejado).
- 🎛️ **Múltiples sincronizaciones con nombre**: configura tantas sincronizaciones independientes como quieras, cada una con sus propios servicios, listas de reproducción, programación y límites de seguridad.
- ↪️ **transferencias únicas**: copia cualquier lista de reproducción de un servicio a otro con una barra de progreso en vivo; pausar, reanudar o detener la copia y resolver manualmente las pistas no coincidentes.
- 🕒 **Agregar pistas o conservar el orden de las pistas**: las copias llegan al final del destino de forma predeterminada, rápida y aditiva. Active Conservar orden agregado recientemente para reescribir las pistas después de la nueva más antigua, de modo que el orden de fecha agregada coincida con la fuente.
- 🔗 **Transfiera desde un enlace**: pegue la URL de una lista de reproducción pública de cualquier servicio conectado y cópiela directamente. No es necesario guardarlo ni seguirlo primero.
- 🌐 **Listas de reproducción seguidas**: sincroniza y transfiere las listas de reproducción que sigues pero que no te pertenecen, no solo las que creaste.
- 📦 **Copias de seguridad de metadatos programadas**: archiva toda la biblioteca de listas de reproducción de una cuenta según su propia programación con datos persistentes de la aplicación, con JSON/XML, límites de retención e historial visible de éxito/fracaso. Las descargas únicas y las listas para importar Soundiiz JSON también permanecen disponibles.
- 💿 **Espejo de descarga local**: mantenga el audio sin conexión, una carpeta por lista de reproducción en el diseño `AlbumArtist/Album` de Jellyfin, con portadas y un `.m3u8` actualizado automáticamente.
- 🛡️ **Medidas de seguridad**: simulación de forma predeterminada, límites de adición/eliminación por paso, protección contra pérdida neta, protección de instantáneas vacías, cancelaciones sin escritura cuando los tokens caducan.
- 🗃️ **Archivo de canciones en constante crecimiento**: cada pista vista se registra en una base de datos local SQLite (nombre, artista, álbum, ISRC, metadatos sin procesar, primera/última vista).
- 🧭 **Historial de coincidencias editable**: explore, corrija y elimine todas las coincidencias de seguimiento almacenadas en caché por servicio desde la página de Asignaciones, incluidos los resultados "sin coincidencias" que, de otro modo, permanecerían sin coincidencias para siempre.
- 🐳 **Se ejecuta en cualquier lugar**: uno `docker compose up -d` para la aplicación del navegador o CLI + cron / Task Scheduler.

> [!IMPORTANT]
> Autohospedado y privado por diseño. Sus datos de escucha y sus credenciales nunca salen de su máquina. La interfaz de usuario web no tiene autenticación: vincúlela a su LAN y no la reenvíe a Internet.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Capturas de pantalla

<div align="center">

**Un panel para cada biblioteca: estado de sincronización, trabajos, actividad en vivo y estado del servicio**

<img src="../../.github/assets/dashboard.png" alt="SongMirror panel que muestra el estado de sincronización, trabajos configurados, actividad en vivo y estado para Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music y Jellyfin" width="82%">

**Configure cualquier cantidad de sincronizaciones (unidireccionales, de fusión de múltiples fuentes, de grupo autorizado o bidireccionales) en un breve asistente.**

<img src="../../.github/assets/sync-wizard.png" alt="El asistente de configuración SongMirror selecciona servicios para una sincronización bidireccional entre Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music y YouTube Music" width="82%">

**Conecte todos los servicios en su navegador: un clic OAuth, pegado de token guiado o una clave API**

<img src="../../.github/assets/accounts.png" alt="La página Cuentas para conectar Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music y Jellyfin" width="82%">

**Explorar y emparejar listas de reproducción entre servicios**

<img src="../../.github/assets/playlists.png" alt="Explorar listas de reproducción en servicios conectados con portadas y recuentos de pistas" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Inicio rápido

La forma más rápida de ejecutarlo es Docker: Compose extrae la imagen publicada, presenta la interfaz de usuario web y ejecuta las sincronizaciones según lo programado.

Para una instalación persistente con reinicios automáticos:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

O pruebe la imagen pública de GHCR directamente sin clonar el repositorio:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Luego abra `http://localhost:8888` y conecte sus servicios en el navegador. La configuración Compose no necesita `.env` para comenzar; todo se configura en la interfaz de usuario y se guarda en `./data`.

La opción directa `docker run` es desechable: `docker stop songmirror` elimina el contenedor y su configuración. Utilice Compose para una instalación duradera con credenciales, cachés y descargas persistentes, o consulte [guía de imágenes de contenedores](../docker-image.md) para etiquetas y fijación de resúmenes.

¿Prefieres ejecutarlo sin Docker?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Requiere [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Para el espejo de descarga local, también `uv tool install spotdl` y tenga `ffmpeg` en PATH.

<a id="app-language"></a>

### Idioma de la aplicación

SongMirror admite inglés, árabe, turco, español, chino simplificado, francés, portugués, alemán, japonés, hindi, bengalí, indonesio, coreano, italiano y vietnamita. En el primer inicio se revisan las preferencias de idioma del navegador en orden, incluidas las variantes regionales, y se utiliza el primer idioma compatible. Si ninguno es compatible, se utiliza el inglés. Cambie el idioma en **Ajustes → General → Idioma**; la elección se guarda en este navegador y se mantiene al recargar la página. Seleccione **Automático (navegador)** para volver a seguir las preferencias del navegador. La interfaz en árabe se muestra de derecha a izquierda. Los nombres de las listas, los artistas y los proveedores, las credenciales y los registros de diagnóstico conservan sus valores originales.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Siempre corriendo: Docker

El contenedor Docker es la implementación recomendada: sirve a la interfaz de usuario web, ejecuta las sincronizaciones según sus horarios y se reinicia con el host. Compose extrae `ghcr.io/ahnafnafee/songmirror:latest`, lo ejecuta como `songmirror` y conserva todas las cachés de autenticación + en `./data`.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Para actualizar, ejecute `docker compose up -d --pull always`. Para crear el pago actual, ejecute `docker compose up -d --build`. Consulte [guía de imágenes de contenedores](../docker-image.md) para ver etiquetas, fijación de resúmenes, extracción directa, verificación, actualizaciones y reversión.

No se necesita `.env` para comenzar; todo se configura en el navegador y se guarda en `./data`. OAuth, token de socio y configuración de clave API, todos disponibles en la página Cuentas; Cada asistente explica los requisitos previos específicos del servicio y el URI de devolución de llamada exacto. Luego cree sus sincronizaciones en la página Sincronización.

Abrir SongMirror desde otra computadora funciona en `http://<server>:8888`. La conexión Spotify predeterminada utiliza una sesión web `sp_dc` pegada, por lo que no necesita ninguna aplicación de desarrollador ni URL de devolución de llamada. Si utiliza intencionalmente la aplicación de desarrollador heredada OAuth alternativa Docker o un proxy inverso, configure la URL base visible en el navegador en `.env`:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror luego anunciará `https://music.example.com/oauth/spotify/callback`; registre ese URI exacto en el panel de la aplicación Spotify y vuelva a crear el contenedor con `docker compose up -d --force-recreate`. También se admite una ruta base de proxy inverso (por ejemplo, `https://example.com/songmirror`). [Spotify requiere HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) para cada redireccionamiento sin bucle invertido; El HTTP simple se acepta solo con direcciones de bucle invertido literales como `127.0.0.1`, no una LAN IP o `localhost`.

| | |
| --- | --- |
| Imagen | `ghcr.io/ahnafnafee/songmirror:latest` admite AMD64 y ARM64. Cada compilación también se publica con una etiqueta `sha-...` específica de la confirmación; Las etiquetas de Git como `v1.2.3` publican adicionalmente `1.2.3`, `1.2` y `1`. Utilice [guía de imágenes de contenedores](../docker-image.md) para fijar un resumen inmutable. |
| Puerto | La interfaz de usuario se publica en el host 8888 (el mapeo `8888:8080` en `docker-compose.yml`; cambie el lado del host si choca). LAN-only: no lo reenvíe a Internet; la interfaz de usuario aún no tiene autenticación. |
| Persistencia | `./data` contiene credenciales, tokens, cachés, el archivo de canciones e instantáneas de listas de reproducción programadas en `playlist_backups/`. Haga una copia de seguridad para conservar su configuración y archivos durante las reconstrucciones. |
| Descargas | Establezca `DOWNLOAD_DIR` (en `.env` o su shell) en el directorio de música de su host (por ejemplo, `F:\Torrent\Music`); componer bind-lo monta en `/music`. Desde Docker, establezca `JELLYFIN_URL` en `http://host.docker.internal:8096`. |
| Sesiones caducadas | Las sesiones renovables se recuperan en el próximo pase programado o manual. TIDAL las sesiones del reproductor web se renuevan a partir del token de actualización capturado; Los tokens Qobuz y Apple Music aún se deben volver a pegar cuando se rechazan. No es necesario reiniciar. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Cómo funciona

Cada paso, para cada nombre de lista de reproducción seleccionada que existe en la fuente:

1. Capture una instantánea de la lista de reproducción de origen (pistas, ISRC, fechas agregadas).
2. Concilie la lista de reproducción con el mismo nombre en cada objetivo conectado seleccionado simultáneamente a través de la lista de reproducción autorizada por la cuenta de ese servicio API.
3. Las pistas que faltan se resuelven (enlaces almacenados en caché → ISRC → búsqueda puntuada) y se añaden las más antiguas primero; Las huellas desaparecidas de la fuente se eliminan detrás de los guardias.
4. Opcionalmente, [spotDL](https://github.com/spotDL/spotify-downloader) sincroniza una carpeta de audio local por lista de reproducción.

La fuente de verdad predeterminada es Spotify, pero el modo unidireccional es independiente del proveedor: cualquier par de lista de reproducción conectado puede ser la fuente.

<a id="matching"></a>

### Coincidencia

La misma jerarquía que utilizan las herramientas de servicios cruzados ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): identificador exacto → búsqueda → puntuación difusa.

1. Enlace en caché: una vez que una pista de origen coincide con la identificación del catálogo/identificación del video de un destino, ese enlace se almacena y se reutiliza (inmune a la deriva del título).
2. ISRC: identidad de registro exacta donde el servicio la expone.
3. Búsqueda puntuada: [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, sobre el título y el artista sin formato y romanizado ([anyascii](https://github.com/anyascii/anyascii)), anclado por duración. Esto maneja, sin codificación:
   - Créditos para múltiples artistas: un servicio enumera todas las funciones, otro enumera la principal (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Decoración del título: `(feat. …)`, `- 2015 Remaster`, `(From "…")`, sufijos adicionales de "video musical oficial".
   - Transliteración: cirílico / bengalí / griego / árabe (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Pistas de solo video: la búsqueda YouTube vuelve al filtro `videos` para pistas independientes/OST que se encuentran en YT solo como cargas.

El ancla de duración desbloquea la coincidencia de título más flexible, por lo que no se acepta una versión diferente (`Runaway - Piano Version`) o una portada de artista equivocado cuando su duración no coincide. Las pistas que no coinciden con seguridad se informan y se omiten.

<a id="multi-source-merge-sync"></a>

### Sincronización de fusión de múltiples fuentes

Un trabajo de Combinar fuentes combina una o más listas de reproducción explícitas en un destino elegido. Cada fuente puede provenir de la biblioteca de una cuenta conectada o de una URL de proveedor pública pegada; este último se resuelve una vez en un proveedor y una identificación de lista de reproducción, por lo que no es necesario guardar ni seguir la lista de reproducción y las ejecuciones programadas no reproducen una URL arbitraria.

- Un sindicato de membresía: se leen todos los constituyentes antes de conciliar el destino. Los ISRC compartidos son una grabación; sin un ISRC, el título exacto/conservador, el artista, la versión y la evidencia de duración deduplican las superposiciones.
- Orden determinista: primero la prioridad del descriptor de origen y luego el orden devuelto por cada lista de reproducción de origen. La primera aparición posee la posición de destino y muestra los metadatos; Las copias posteriores sólo enriquecen los metadatos de identidad faltantes.
- Eliminaciones seguras para la unión: una ruta de destino se puede eliminar solo cuando un pase completo la encuentra ausente de todas las fuentes constituyentes. Una fuente fallida, truncada, mal formada, no disponible o incognosciblemente vacía deshabilita todas las eliminaciones para ese pase, mientras que las adiciones seguras de fuentes legibles pueden continuar.
- Agregar solo de forma predeterminada: deje desactivada la opción Eliminar pistas ausentes de cada origen para mantener todas las pistas de solo destino. Al encenderlo, se accede a la tapa de extracción normal por pasada después de que pasa el protector de lectura completa.

Actualmente, los trabajos de combinación se dirigen a una lista de reproducción de proveedores; la descarga local independiente dirigida por Spotify/espejo Jellyfin no está disponible para un trabajo agregado.

<a id="authoritative-groups"></a>

### Grupos autorizados

Utilice un grupo autorizado cuando seleccione activamente la misma lista de reproducción lógica en dos o más servicios, pero desee que todos los demás servicios seleccionados los sigan. Una configuración típica es Spotify + Apple Music como autoridades, con TIDAL, Qobuz, Deezer, Amazon Music y YouTube Music como espejos.

- La membresía proviene únicamente de las autoridades: una pista agregada en Spotify o Apple Music se propaga a la otra autoridad y a cada espejo. Una pista agregada sólo en un espejo es deriva; nunca se vuelve a importar a las autoridades.
- Autoridad de un solo pedido: elija qué autoridad proporciona los nombres de las listas de reproducción y el orden de las adiciones. Las demás autoridades todavía aportan cambios de membresía.
- Las eliminaciones confirmadas se propagan desde cualquiera de las autoridades: una ausencia debe aparecer en dos lecturas completas consecutivas antes de que pueda eliminar algo. Una adición simultánea del lado de la autoridad triunfa sobre una eliminación.
- Los espejos nunca obtienen votación: eliminar una pista de un espejo repara ese espejo; no elimina la pista de Spotify o Apple Music.
- Primer paso seguro: cada conjunto de autoridades tiene su propia línea de base. Su primera pasada exitosa puede agregar pistas faltantes, pero mantiene todas las eliminaciones hasta que una pasada posterior demuestre que la línea de base es estable.
- Fallo cerrado: si alguna autoridad está desconectada, es ilegible o su lista de reproducción no se puede abrir/crear, esa lista de reproducción lógica se omite en lugar de recurrir silenciosamente a menos autoridades.

Las eliminaciones requieren activación explícita y están sujetas a un límite. Active **Sincronizar eliminaciones** para el trabajo, o establezca `MAX_REMOVALS` al ejecutarlo sin interfaz gráfica, si desea quitar las pistas sobrantes de los destinos para que coincidan con el conjunto de fuentes autorizadas.

<a id="bidirectional-n-way-sync"></a>

### Sincronización bidireccional (N-way)

De forma predeterminada, un proveedor es la fuente de la verdad y las ediciones fluyen en una dirección. En el modo N-way, cada proveedor seleccionado es un par: agregue o elimine una pista en cualquiera y el cambio se propaga a los demás.

La sincronización bidireccional es imposible sin estado, por lo que se toma una instantánea de la membresía canónica de cada lista de reproducción lógica después de cada pase limpio. Cada paso diferencia a cada proveedor con esa instantánea, une los cambios y reconcilia a todos con el resultado:

- Sin eco: un anuncio propagado pasa a formar parte de la instantánea, por lo que nunca se recupera.
- Los complementos ganan en los conflictos: perder una canción es peor que conservar una extra.
- Protección contra colapso de lectura: si un proveedor de repente lee muchas menos pistas que la línea de base (un contratiempo transitorio API), se omite ese paso para que una mala lectura no pueda generar una eliminación masiva en cascada.
- Mismas salvaguardias que unidireccional: límites por paso `MAX_ADDS` / `MAX_REMOVALS` y protección contra pérdida neta en cada lado de escritura.
- **Las eliminaciones son opcionales**: `MAX_REMOVALS` vale 0 de forma predeterminada. Una pista que desaparezca de un proveedor, ya sea porque se elimine allí o se retire por motivos de licencia, se conserva en los demás y solo se registra. Establezca un límite o active **Sincronizar eliminaciones** en la interfaz para propagar las eliminaciones.

> Siempre la simulación primero. Ejecute sin `--execute` (o use Vista previa en la interfaz de usuario) y lea el plan: imprime cada propuesta de agregar/eliminar en cada proveedor antes de que se escriba algo.

<a id="liked-and-favorite-tracks"></a>

### Pistas que me gustan y favoritas

En el paso Listas de reproducción de una sincronización, seleccione la colección que le gusta incorporada del servicio de origen. SongMirror luego pregunta dónde debe ir en cada destino seleccionado: directamente a la colección de favoritos/me gusta de ese servicio, o a una nueva lista de reproducción cuyo nombre sugerido puedes editar. Una nueva selección sólo gusta; Activa también sincronizar todas las listas de reproducción habituales o elige listas de reproducción individuales para incluir ambas.

Esto funciona en Spotify Canciones que me gustan, TIDAL/Qobuz/Deezer Pistas favoritas, Amazon Music Mis gustos, Apple Music Canciones favoritas y YouTube Music Música que me gusta. Se aplican los mismos límites de seguridad y rutas de reconciliación unidireccionales, de grupo autorizado y de N vías. Al igual que con las listas de reproducción normales, las eliminaciones permanecen desactivadas de forma predeterminada hasta que se active **Sincronizar eliminaciones**.

La concesión de reproductor web registrado de TIDAL maneja tanto listas de reproducción normales como pistas favoritas nativas cuando lleva `r_usr` y `w_usr`. La captura de la respuesta completa del token de inicio de sesión proporciona SongMirror el token de actualización, así como el Bearer de corta duración, para que la sesión pueda renovarse automáticamente.

Algunas de estas integraciones utilizan las interfaces web propias de los proveedores y pueden cambiar sin previo aviso; el [evaluación de viabilidad](../design/2026-09-01-liked-tracks-sync-feasibility.md) registra el API y las restricciones de distribución para cada proveedor.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Copias de seguridad de metadatos de listas de reproducción

Las copias de seguridad no requieren un segundo proveedor ni un trabajo de sincronización:

- En Configuración → Copias de seguridad de listas de reproducción, use Agregar copia de seguridad en la parte superior para agregar una cuenta conectada. Elija JSON o XML, luego seleccione una frecuencia como diaria o semanal. Los intervalos personalizados utilizan un número y una unidad. Mantener copias de seguridad ofrece ajustes preestablecidos de retención, un recuento personalizado o Todas las copias de seguridad.
- Las copias de seguridad están predeterminadas en `data/playlist_backups/<account-profile-id>/` (o `/data/playlist_backups/<account-profile-id>/` en Docker). Haga clic en Carpeta de copia de seguridad para acceder al selector de carpetas integrado o elija Ingresar ruta manualmente. Una carpeta personalizada todavía tiene una subcarpeta separada para cada cuenta. Usar la carpeta de respaldo predeterminada restaura el valor predeterminado. Cambiar de ubicación afecta las copias de seguridad futuras; Los archivos antiguos permanecen donde están. La retención y la descarga más reciente se aplican a la ubicación seleccionada. Eliminar una programación nunca elimina los archivos guardados.
- Configuración → Descargas y Jellyfin → La carpeta de descargas utiliza el mismo selector integrado y entrada manual. Elija una carpeta accesible para su biblioteca Jellyfin. Las descargas siguen el cronograma de cada sincronización habilitada en la pestaña Sincronización. El selector muestra las rutas de host configuradas (por ejemplo, `F:\Torrent\Music`) mientras conserva su asignación Docker (`/music`) internamente. Los soportes de descarga existentes no se modifican. Primero se deben compartir carpetas de host adicionales como Docker montajes de enlace; elegir una carpeta desmontada muestra un error y deja la configuración actual sin cambios.

- La misma tarjeta de Configuración muestra la siguiente ejecución, el recuento de instantáneas almacenadas, el último archivo y recuentos exitosos y el error más reciente. Realizar una copia de seguridad ahora pone en cola una ejecución segura bajo demanda; Descargar la última recupera la instantánea persistente más reciente.
- En la página Listas de reproducción, use Exportar en una tarjeta de servicio para descargar cada lista de reproducción de ese servicio en un archivo versionado JSON o XML.
- Abra una lista de reproducción para exportar solo esa lista de reproducción. Su opción Soundiiz sigue a [Soundiiz está documentada JSON forma de importación](https://soundiiz.com/data/fileExamples/playlistExport.json), por lo que la lista de pistas descargadas se puede cargar a través del flujo Importar lista de reproducción → Desde archivo de Soundiiz.
- SongMirror JSON/XML conserva el orden y los nombres de las listas de reproducción, además de los ID de pistas/ocurrencias del proveedor, ISRC disponibles, artistas, álbumes, posiciones de las pistas de los álbumes, duraciones, fechas agregadas, enlaces de obras de arte y marcadores de entradas no disponibles. Los fantasmas del catálogo sin identificación permanecen en la copia de seguridad en lugar de desaparecer. Los archivos no contienen cookies, tokens, encabezados de solicitud, vistas previas ni URL de archivos de transmisión.

El navegador descarga las exportaciones manuales al dispositivo que ejecuta la interfaz de usuario. Las exportaciones programadas utilizan el volumen de datos de la aplicación existente, por lo que no se requiere una segunda ruta de host ni montaje de contenedor. La copia de seguridad lee la cola detrás de las sincronizaciones y transferencias en lugar de acceder a los clientes del proveedor simultáneamente. El campo `schema_version` permite que las versiones futuras evolucionen al formato sin pérdidas sin que las instantáneas antiguas sean ambiguas.

<a id="built-in-folder-picker"></a>

### Selector de carpetas incorporado

Haga clic en un campo de carpeta o Examinar... para abrir el selector integrado. Utilice Ubicaciones, rutas de navegación en las que se puede hacer clic, Atrás, Adelante y Arriba una carpeta para navegar. Haga clic en una carpeta para seleccionarla; haga doble clic, presione Entrar o use su flecha para abrirlo. La búsqueda filtra la carpeta actual. Ingrese una ruta de carpeta que acepte una dirección completa. Seleccionar carpeta actualiza el borrador; guarde la configuración o programe para aplicarla. Cancelar deja el borrador sin cambios. No se requiere ningún asistente de escritorio ni ningún proceso adicional.

Nueva carpeta crea una subcarpeta con nombre en la ubicación abierta actualmente y luego la abre. Los elementos existentes nunca se sobrescriben. Cancelar la entrada del nombre no crea nada; cancelar el selector después de la creación deja la nueva carpeta en el disco. La ubicación de descarga o copia de seguridad guardada cambia solo después de seleccionarla y guardarla. En Docker, el selector explica qué rutas se comparten y muestra tanto la ruta del contenedor como la ruta de su computadora configurada cuando esté disponible.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Espejo de descarga local (Jellyfin)

Mantenga una copia de audio sin conexión de cada lista de reproducción sincronizada, una carpeta por lista de reproducción, a través de [spotDL](https://github.com/spotDL/spotify-downloader). La sincronización es una verdadera duplicación: se descargan pistas nuevas, las pistas eliminadas se eliminan localmente. El diseño está listo para Jellyfin: apunte una biblioteca de música Jellyfin al directorio de descarga y aparecerán tanto las pistas como las listas de reproducción, manteniéndose actualizadas en cada paso:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Habilítelo configurando `DOWNLOAD_DIR` e instalando spotDL + ffmpeg:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Incremental: después de la primera descarga completa, solo se recuperan las pistas recién agregadas; las pistas eliminadas (y sus carpetas de álbumes vaciadas) se eliminan. Una carrera interrumpida continúa en la siguiente pasada.
- Lo más nuevo primero `.m3u8`: escrito en orden de fecha de adición, lo más nuevo en la parte superior (establecido `LOCAL_MIRROR_ORDER=oldest` para invertir). Reconstruya portadas/etiquetas/mtimes a partir de archivos existentes con `uv run main.py --refresh-local`.
- Las portadas de listas de reproducción en Jellyfin - Jellyfin ignoran un archivo de portada junto a un m3u, así que configure `JELLYFIN_URL` + `JELLYFIN_API_KEY` y cada pasada carga la portada de la lista de reproducción real a través de Jellyfin API.
- Calidad de audio: la fuente es YouTube, por lo que sin una cookie de YT Music Premium el límite máximo es de ~128 a 160 kbps. `LOCAL_MIRROR_FORMAT=opus` mantiene la transmisión nativa de YouTube sin volver a codificar mp3; una cookie Premium (`LOCAL_MIRROR_COOKIE_FILE`) desbloquea AAC de 256 kbps. Al seleccionar `flac` se cambia el contenedor de salida, pero no se puede convertir una fuente con pérdidas en audio sin pérdidas.

La ruta FLAC actual de Monochrome utiliza recursos de reproducción de un solo uso controlados por el navegador en lugar de una exportación de archivos estable y autorizada por el proveedor API, por lo que SongMirror no la automatiza. Utilice la réplica local sólo para contenido que sea de su propiedad o que esté autorizado a copiar.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Conectando cada servicio

En la aplicación web, la página Cuentas lo guía a través de cada servicio y muestra los valores exactos que debe pegar. Nada se representa a través de un tercero.

<a id="credential-renewal"></a>

### Renovación de credencial

SongMirror actualiza las credenciales justo a tiempo, no con un temporizador de actualización de token independiente. Cada paso de sincronización manual o programado valida los conectores que utiliza y renueva los tokens de acceso admitidos antes de la primera solicitud (o una vez después de un rechazo de autenticación). Es normal que un token de acceso de corta duración caduque entre pases; lo que importa es el token de actualización duradero o la cookie de renovación. La página Cuentas valida el estado cuando se carga o recupera el foco, pero no es el mantenimiento de la sesión en segundo plano; Los horarios de sincronización habilitados son.

| Servicio | Comportamiento de renovación |
| --- | --- |
| Spotify | La conexión predeterminada genera un token de acceso al reproductor web a partir de la cookie `sp_dc` guardada a pedido y vuelve a intentarlo con un nuevo token después de un `401`; la sesión de inicio de sesión subyacente aún se puede revocar. La aplicación de desarrollador heredada OAuth sigue siendo compatible con las instalaciones existentes. |
| TIDAL | El token de acceso al reproductor web importado se renueva automáticamente hasta `auth.tidal.com` utilizando el token de actualización de la respuesta de inicio de sesión. SongMirror mantiene el token de actualización existente cuando una respuesta lo omite y conserva un token rotado cuando TIDAL devuelve uno. El cierre de sesión o la revocación aún requieren una nueva captura. |
| Qobuz | El `X-User-Auth-Token` pegado se usa hasta que Qobuz lo rechaza, luego se debe capturar nuevamente. |
| Deezer | La Tubería de corta duración JWT se renueva automáticamente desde el `refresh-token` guardado antes de su uso y una vez después de un `401/403`; El estado de renovación rotado persiste. |
| Amazon Music | El token de acceso web se renueva hasta `/pandaToken` utilizando el agente de usuario del navegador capturado, el referente y las cookies incluidas en la lista de permitidos. El flujo actual `POST config.json?skipToken=false` arranca el contexto del dispositivo cuando es necesario y las cookies rotadas se conservan. El cierre de sesión, los cambios de seguridad o la revocación del lado del servidor aún requieren una captura nueva. |
| Apple Music | Los Bearer y Media-User-Token pegados no se pueden renovar antes del SongMirror y deben capturarse nuevamente después del rechazo. |
| YouTube Music | Data API OAuth se actualiza automáticamente dentro de los 60 segundos posteriores a su vencimiento. El modo de navegador intenta la rotación de cookies de Google cada vez que se crea un objetivo de sincronización; una sesión del navegador que ya haya caducado debe exportarse nuevamente. |
| Jellyfin | La clave API no tiene un ciclo de actualización del token de acceso; reemplácelo sólo si es revocado o eliminado. |

<a id="spotify"></a>

### Spotify

1. Inicie sesión en <https://open.spotify.com>.
2. Abra el navegador DevTools (`F12`) → Aplicación (Chrome/Edge) o Almacenamiento (Firefox) → Cookies → `https://open.spotify.com`.
3. Copie el valor de la cookie `sp_dc` y péguelo en Cuentas → Spotify.

Esa única sesión web iniciada maneja la exploración de la biblioteca, las lecturas y escrituras de listas de reproducción y la búsqueda de catálogos. No requiere una aplicación de desarrollador Spotify, una clave API o una cuenta Premium. Trate `sp_dc` como una contraseña: SongMirror la almacena en su directorio de datos privados, pero la integración utiliza las operaciones internas del reproductor web de Spotify y puede necesitar mantenimiento si Spotify las cambia. Las credenciales existentes de la aplicación de desarrollador OAuth siguen siendo una alternativa compatible.

<a id="tidal"></a>

### TIDAL

1. Abra [Reproductor web de TIDAL](https://listen.tidal.com), abra DevTools → Red y habilite Conservar registro.
2. Cierre sesión y vuelva a iniciar sesión, luego filtre la lista de redes para `oauth2/token`.
3. Seleccione la solicitud `auth.tidal.com/v1/oauth2/token` exitosa. En Carga útil (Chrome/Edge) o Solicitud (Firefox), copie el valor del formulario `client_id` en el campo ID de cliente del reproductor web de SongMirror.
4. Abra la pestaña Respuesta de la solicitud y copie el JSON completo en la respuesta del token del reproductor web. Debe incluir tanto `access_token` como `refresh_token`.
5. Conéctate. SongMirror ejerce inmediatamente la concesión de actualización y se niega a informar el éxito si ese ID de cliente no puede renovarla.

El ID de cliente OAuth son metadatos de solicitud y no es el reclamo numérico `cid` dentro del token de acceso de TIDAL. SongMirror extrae solo el token de acceso, el token de actualización, el ID del cliente, los alcances, la caducidad y el país del catálogo; los datos de respuesta no relacionados se descartan. Se renueva justo antes de la expiración y una vez después de un rechazo de autenticación hasta `https://auth.tidal.com/v1/oauth2/token`, preservando la rotación del token de actualización. El antiguo pegado del encabezado de solicitud OpenAPI sigue siendo compatible, pero debido a que no contiene ningún token de actualización, es necesario volver a pegarlo después de su vencimiento. Solo se utilizan los metadatos del catálogo y las listas de reproducción del usuario que ha iniciado sesión; los recursos de reproducción permanecen fuera de esta integración.

<a id="qobuz"></a>

### Qobuz

Inicie sesión en <https://play.qobuz.com>, abra DevTools → Red y filtre por `api.json/0.2`. Elija cualquier solicitud que contenga `X-App-Id` y `X-User-Auth-Token`, incluida una solicitud `album/story` autenticada, luego copie sus encabezados de solicitud o cópielo como cURL y péguelo en el asistente. SongMirror persiste solo esos dos valores, los envía utilizando el mismo flujo basado en encabezados que el reproductor web y descarta las cookies y los metadatos del navegador no relacionados. No se requiere aprobación comercial API ni identificación de usuario; Las credenciales de socios existentes siguen siendo un entorno compatible de respaldo.

El adaptador utiliza únicamente puntos finales de lista de reproducción y búsqueda de catálogo; no solicita URL de secuencias ni de archivos.

<a id="deezer"></a>

### Deezer

Inicie sesión en <https://www.deezer.com>, abra DevTools → Red y vuelva a cargar la página. Filtre por `auth.deezer.com/login/renew`, copie los encabezados de esa solicitud (o cópielos como cURL) y péguelos en el campo de renovación. Firefox puede, en su lugar, copiar las cookies de solicitud como un bloque delimitado por punto y coma; esa forma también se acepta. SongMirror conserva solo la cookie `refresh-token` dedicada y la utiliza para renovar automáticamente la tubería de corta duración JWT de Deezer. También puede pegar una solicitud `pipe.deezer.com/api` actual como arranque inmediato, pero no es necesario cuando se configura la renovación. Las adiciones y eliminaciones de listas de reproducción utilizan la sesión de Pipe renovable; no se necesita ninguna cookie `arl`. Los tokens de desarrollador OAuth existentes siguen siendo un entorno compatible alternativo.

<a id="amazon-music"></a>

### Amazon Music

No se requiere la aprobación del desarrollador para el conector predeterminado. Utiliza las mismas rutas autenticadas GraphQL y de renovación de tokens que el Amazon Music reproductor web:

1. Inicie sesión en <https://music.amazon.com> y abra DevTools → Red.
2. Vuelva a cargar la página, filtre por `config.json` y seleccione la solicitud iniciada. (`pandaToken` también funciona cuando aparece, pero no es obligatorio).
3. Elija Copiar encabezados de solicitud o Copiar como cURL y luego péguelo en el campo de renovación. Mantenga los encabezados `User-Agent`, `Referer` y `Cookie` completos para que SongMirror pueda reproducir el mismo contexto del navegador.
4. Opcionalmente, copie la respuesta `config.json` iniciada en el campo de arranque; SongMirror normalmente puede recuperar el contexto de ese dispositivo mediante la sesión de renovación.

SongMirror deriva el mismo valor de autorización `AmznMusic` localmente y lo actualiza hasta `music.amazon.com/pandaToken` antes de que expire o una vez después de un rechazo de autenticación. Durante la conexión, utiliza la solicitud de configuración de estilo de navegador actual cuando se necesita el contexto del dispositivo, requiere `/pandaToken` para generar un token de acceso y rechaza la conexión si Amazon revoca la cookie de renovación de Música. Almacena solo el agente de usuario del navegador, el idioma, la referencia de música, una lista permitida de cookies de sesión/autenticación de Amazon y un contexto limitado del dispositivo cliente de música; Se descartan análisis, experimentos, consola AWS, CSRF y otros datos del navegador no relacionados. Esas cookies retenidas siguen siendo confidenciales, así que mantenga SongMirror en privado en su LAN. Un cierre de sesión, un cambio de contraseña/seguridad o una revocación por parte de Amazon aún pueden requerir una nueva captura.

Esta es una interfaz de cliente web propia no compatible y Amazon puede cambiarla sin previo aviso. El [Amazon Music Web API](https://developer.amazon.com/docs/music/API_web_overview.html) documentado sigue siendo una versión beta cerrada; Las credenciales de socio aprobadas siguen siendo un recurso opcional cuando se configuran a través de variables de entorno.

<a id="apple-music"></a>

### Apple Music

No se necesita una cuenta de desarrollador de Apple: dos encabezados de `music.apple.com` son suficientes. Abra <https://music.apple.com>, inicie sesión, abra DevTools → Red, reproduzca una canción, filtre por `amp-api.music.apple.com` y, desde los encabezados de cualquier solicitud, copie:

- `authorization: Bearer eyJ...` → Bearer token (la parte `eyJ...`, sin `Bearer `)
- `media-user-token: ...` → Token de usuario (valor completo)

El asistente de conexión le permite pegar los encabezados sin formato y analiza los valores por usted. Fichas de los últimos meses; Vuelva a pegarlos en la página Cuentas cuando caduquen.

Un ID de Apple sin una suscripción Apple Music activa aún puede conectarse en modo solo catálogo. En ese modo, pegue un enlace de lista de reproducción pública Apple Music en Transferencias para copiarlo en otro servicio conectado. La exploración de la biblioteca de Apple, la sincronización programada y el uso de Apple Music como destino de transferencia aún requieren el privilegio pagado CloudLibrary; SongMirror muestra esas operaciones como no disponibles en lugar de tratar las credenciales válidas del catálogo como vencidas.

<a id="youtube-music"></a>

### YouTube Music

Habla con el oficial [YouTube Data API v3](https://developers.google.com/youtube/v3), cuyo token de actualización OAuth es duradero y sobrevive a los reinicios.

1. En [Google Consola en la nube](https://console.cloud.google.com), cree un proyecto, habilite YouTube Data API v3 y cree un cliente OAuth de tipo TV y dispositivos de entrada limitada.
2. En la pantalla de consentimiento OAuth, configure Estado de publicación → En producción (si lo deja en "Prueba", el token caduca después de 7 días).
3. En la aplicación, pegue el ID del cliente + secreto y complete el código del dispositivo en pantalla.

> Cuota: el Data API permite 10.000 unidades/día (una búsqueda cuesta 100, una adición/eliminación 50). El mantenimiento del estado estacionario es barato; un gran trabajo atrasado por primera vez puede alcanzar el límite y reanudarse al día siguiente.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ sin interfaz gráfica CLI

¿Prefieres `.env` + cron / Task Scheduler? El mismo motor funciona sin interfaz gráfica.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Banderas útiles:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Variables de entorno clave (consulte `.env.example`): las credenciales para los proveedores que utilice, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` y `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Medidas de seguridad

Las mudanzas son destructivas, por eso están cautelosas:

- la simulación es la predeterminada: nada cambia sin `--execute` (o la acción de sincronización real de la interfaz de usuario).
- Si la fuente devuelve 0 pistas para una lista de reproducción que el destino muestra como no vacía, las eliminaciones se omiten en ese paso (una falla transitoria API no puede vaciar una lista de reproducción).
- **Las eliminaciones están desactivadas de forma predeterminada**: `MAX_REMOVALS=0` retiene todas las eliminaciones; se registran, pero nunca se aplican. Así, una retirada por motivos de licencia en una plataforma no provoca eliminaciones en cadena en las demás. Active **Sincronizar eliminaciones** en cada sincronización o establezca `MAX_REMOVALS`. Incluso después de activarlas, si las eliminaciones pendientes de una ejecución superan el límite, se omiten todas y se registran.
- `MAX_ADDS` limita cada escritura que produce marcas de tiempo en un pase de sincronización, incluida la reparación cronológica. Si una partida recuperada más antigua necesita una repetición de sufijo mayor de lo que permite el límite, SongMirror la difiere hasta el siguiente pase en lugar de hacer que parezca más nueva o provocar una explosión gigante del proveedor. Una transferencia única no tiene siguiente paso, por lo que nunca se pospone: copia cada pista solicitada y las agrega en el orden de origen, a menos que active "Conservar orden agregada recientemente" para esa transferencia, lo que gasta los costos de reparación.
- Una reparación cronológica realiza una copia duplicada antes de retirar el original. En un servicio cuya eliminación toma todas las copias de una canción, ese recuento debe ser correcto, por lo que Apple Music vuelve a leer hasta que las copias preparadas sean visibles y se niega a retirar nada de una lectura que aún sigue sus propias escrituras. Deezer omite la reparación por completo y siempre agrega: tampoco tiene inserción posicional, por lo que no vale la pena correr el riesgo de reproducir una orden que no puede expresar hasta el destino. El formulario de transferencia pone en gris su cambio de orden y dice por qué.
- Protección contra pérdidas netas: un seguimiento del lado de destino que se asemeja a un seguimiento de origen que no coincide con ese servicio se retiene, no se elimina.
- Cualquier falla de autenticación del proveedor anula el paso de ese proveedor inmediatamente; no se realizan eliminaciones parciales de tokens vencidos.
- Un trabajo de fusión debe finalizar cada fuente constituyente leída antes de eliminarla de su destino; cualquier instantánea de origen parcial o fallida fuerza que pase al comportamiento de solo agregar.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Almacenamiento en caché y archivo de canciones

Todo lo que se puede resolver se almacena en caché, por lo que los pases de estado estable son casi instantáneos: cachés de resolución por servicio (ISRC + búsqueda, incluidos errores), un caché de lista de pistas con clave `snapshot_id`, enlaces de identificadores exactos en SQLite y un salto de instantáneas por par (`unchanged since last clean sync`).

Cada pase también archiva los metadatos de cada pista que ve en `song_cache.db`, un archivo SQLite que solo crece. Las pistas eliminadas permanecen archivadas con nombre, artista, álbum, duración, ISRC, instantánea sin formato JSON y marcas de tiempo vistas por primera y última vez:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Resolver asignaciones

Cada servicio mantiene su propia caché de resolución, asignando una clave `title|artist` normalizada a la identificación del catálogo con la que coincidió.
ese servicio. Una coincidencia se reutiliza para siempre, al igual que un resultado de "no coincidencia", que es lo que hace que una pista falle.
para igualar una vez permanecer inigualable en cada pase posterior.

La página Asignaciones en la interfaz de usuario web expone esos cachés directamente, por servicio:

- buscar en todo el caché por título, artista o identificación resuelta
- filtrar por entradas configuradas manualmente (una coincidencia que usted eligió en el editor de conflictos de transferencia) o por entradas que no coincidan
- corrija una identificación incorrecta pegando el enlace de la pista correcta, o elimine una asignación para que la siguiente pasada la busque nuevamente
- borre todas las entradas "no coincidentes" para un servicio en una sola acción, de modo que un lote de búsquedas fallidas pueda volver a intentarse

Cuando un error solucionado se resuelve más tarde, simplemente agregarlo hará que la canción anterior parezca más nueva. Para lista de reproducción
destinos, SongMirror en su lugar reproduce esa canción y el sufijo más nuevo ya presente, del más antiguo al más nuevo, luego elimina
las copias más antiguas. Los proveedores no permiten a los clientes restaurar las marcas de tiempo originales, pero esto preserva su relativa
Orden agregada recientemente. Las colecciones nativas que me gustan o favoritas siguen siendo exclusivas para miembros y nunca se repiten.

Las ediciones se rechazan con un mensaje claro mientras se ejecuta una sincronización, porque un pase mantiene el caché en la memoria durante su ejecución.
duración completa y los sobrescribiría al finalizar.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Diseño del proyecto

Entrada CLI: `uv run main.py` (cuña delgada) o `python -m songmirror`. Entrada web: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Agregar otro servicio: subclase `MirrorTarget`, implementar ~8 métodos, agregar su constructor a `engine/targets`' `_REGISTRY` y su clase a `_CLASSES`, y agregar un `Connector` coincidente en `services/accounts`. Toda la conciliación (diferencias, pedidos, medidas de seguridad, registros, omisión de instantáneas) se hereda.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Solución de problemas

- `Missing required environment variable`: complete `.env` (CLI) o conecte el servicio en la interfaz de usuario.
- TIDAL informes `Expired`: cierre sesión y vuelva a iniciar sesión en `listen.tidal.com`, luego pegue tanto el `client_id` de la carga útil de solicitud `oauth2/token` como su respuesta completa JSON en Cuentas. Una solicitud OpenAPI copiada solo tiene una duración corta Bearer y no se puede renovar.
- TIDAL informes HTTP 429: este es un límite de tarifa temporal, no un inicio de sesión vencido. SongMirror respeta el retraso de reintento del proveedor y almacena en caché las comprobaciones de estado de la cuenta en lugar de sondear repetidamente el API.
- Qobuz o informes de Apple `Expired` / `401` / `403`: estas sesiones pegadas no tienen ningún secreto renovable; capturar una nueva solicitud o token de inicio de sesión en Cuentas.
- TIDAL dice que el token carece de acceso al seguimiento de Me gusta: capture una nueva respuesta del token del reproductor web registrado que contenga `r_usr` y `w_usr`.
- Deezer la renovación falla: capture una solicitud `auth.deezer.com/login/renew` nueva (o su cookie `refresh-token`). Una tubería actual Bearer por sí sola es solo un arranque temporal.
- Amazon Music la renovación falla: capture una nueva solicitud `POST /config.json?skipToken=false` iniciada con sus encabezados `User-Agent`, `Referer` y `Cookie` completos. La respuesta JSON es opcional.
- YouTube Music el modo de navegador caduca: exporta encabezados de solicitud de navegador nuevos. Para obtener la configuración desatendida más duradera, utilice Data API OAuth con una pantalla de consentimiento en producción.
- Spotify informes caducados: inicie sesión nuevamente en `open.spotify.com` y pegue una nueva cookie `sp_dc` en Cuentas.
- Una lista de reproducción no se está sincronizando: confirma que está en el alcance de la lista de reproducción de sincronización y que existe en la fuente (los destinos se crean automáticamente en un pase real).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Licencia

Copyright © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Este proyecto tiene licencia [MIT](../../LICENSE).

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
