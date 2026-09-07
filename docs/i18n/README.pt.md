<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Sincronização de playlist auto-hospedada e sempre ativa para Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music e YouTube Music — além de um espelho de áudio local pronto para Jellyfin.<br/>
Uma alternativa gratuita, de código aberto e auto-hospedada para Soundiiz, TuneMyMusic e FreeYourMusic que você possui e administra.

**Sincronização unidirecional, de várias fontes, de grupo autoritativo ou totalmente bidirecional (N-way) · transferências únicas de listas de reprodução · correspondência precisa por ISRC · tudo a partir do seu navegador**

[Início rápido](#quick-start) · [Recursos](#features) · [Capturas de tela](#screenshots) · [Sempre em execução: Docker](#always-running-docker) · [Como funciona](#how-it-works) · [Relatar um erro][github-issues-link] · [Sugerir uma funcionalidade][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**Compartilhe este projeto**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>Configure uma vez – cada playlist que você seleciona permanece espelhada em todos os serviços, na ordem de adição de data.</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror demonstração — revelação do logotipo, painel, configuração de sincronização unidirecional e bidirecional, transferências de listas de reprodução ao vivo e correspondência precisa por ISRC em sete serviços de música" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">Assistir à versão 1080p</a></sup>

</div>

> [!NOTE]
> Aplicativo Web + sem interface gráfica CLI, um mecanismo. Clique na interface do navegador para conectar serviços, criar sincronizações e transferir playlists — ou execute-o `.env` + estilo cron. Ambos conduzem o mesmo núcleo de sincronização.

<details>
<summary><kbd>Índice</kbd></summary>

#### Índice

- [✨ Recursos](#features)
- [📸 Capturas de tela](#screenshots)
- [🚀 Início rápido](#quick-start)
  - [Idioma do aplicativo](#app-language)
- [🐳 Sempre em execução: Docker](#always-running-docker)
- [⚙️ Como funciona](#how-it-works)
  - [Correspondência](#matching)
  - [Sincronização de mesclagem de várias fontes](#multi-source-merge-sync)
  - [Grupos autorizados](#authoritative-groups)
  - [Sincronização bidirecional (N-way)](#bidirectional-n-way-sync)
- [📦 Backups de metadados de listas de reprodução](#playlist-metadata-backups)
- [💿 Espelho de download local (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 Conectando cada serviço](#connecting-each-service)
  - [Renovação de credencial](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ sem interface gráfica CLI](#headless-cli)
- [🛡️ Salvaguardas de segurança](#safety-rails)
- [🗃️ Cache e arquivo de músicas](#caching-song-archive)
  - [Resolver mapeamentos](#resolve-mappings)
- [🧱 Layout do projeto](#project-layout)
- [🩺 Solução de problemas](#troubleshooting)
- [📄 Licença](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ Recursos

SongMirror mantém suas listas de reprodução idênticas em todos os lugares, sem adição manual, cópia uma por uma ou um serviço de nuvem pago que mantém sua biblioteca. É multiplataforma, auto-hospedado e de código aberto.

- 🔁 **Espelhamento verdadeiro, não apenas acréscimos** - adições e remoções. Escolha uma fonte de verdade (Spotify por padrão) e os outros a seguem.
- ⇆ **Grupos autoritativos** — confiam em dois ou mais serviços (por exemplo Spotify + Apple Music) enquanto todos os outros serviços selecionados permanecem um espelho somente de destino.
- ⇄ **Sincronização N-way bidirecional** — uma adição ou remoção em qualquer serviço conectado se propaga para todos os outros, sem eco, atrás de proteções de remoção.
- ⇉ **Sincronização de mesclagem de várias fontes** — agende a união desduplicada de playlists de bibliotecas e URLs de playlists públicas em um único destino, sem salvar ou seguir as listas públicas.
- ♥ **Faixas curtidas e favoritas** — sincronize a coleção de curtidas integrada de cada serviço em todos os sete provedores de música, seja nos favoritos do próprio destino ou em uma nova lista de reprodução nomeada.
- 🎯 **correspondência precisa por ISRC** - identidade de gravação exata quando disponível, com substitutos aproximados de título/artista/duração compatíveis com Unicode (diferenças nos créditos do artista em destaque, sufixos "- 2015 Remaster", scripts não latinos, uploads apenas de vídeo - todos manipulados).
- 🎛️ **Sincronizações com vários nomes** — configure quantas sincronizações independentes desejar, cada uma com seus próprios serviços, playlists, programação e limites de segurança.
- ↪️ **transferências únicas** — copie qualquer playlist de um serviço para outro com uma barra de progresso ao vivo; pause, retome ou pare no meio da cópia e resolva manualmente faixas sem correspondência.
- 🕒 **Anexe trilhas ou preserve a ordem das trilhas** – as cópias chegam ao final do destino por padrão, de forma rápida e aditiva. Ative Preservar ordem adicionada recentemente para reescrever as faixas após a mais antiga, para que a ordem adicionada pela data corresponda à fonte.
- 🔗 **Transferir de um link** – cole o URL de uma lista de reprodução pública de qualquer serviço conectado e copie-o diretamente. Não há necessidade de salvá-lo ou segui-lo primeiro.
- 🌐 **Playlists seguidas** — sincronize e transfira playlists que você segue, mas não possui, e não apenas aquelas que você criou.
- 📦 **Backups de metadados agendados** — arquive toda a biblioteca de playlists de uma conta de acordo com sua própria programação, em dados persistentes do aplicativo, com JSON/XML, limites de retenção e histórico visível de sucesso/falha. downloads únicos e prontos para importação Soundiiz JSON também permanecem disponíveis.
- 💿 **Espelho de download local** - mantenha o áudio offline, uma pasta por lista de reprodução no layout `AlbumArtist/Album` de Jellyfin, com capas e um `.m3u8` atualizado automaticamente.
- 🛡️ **Proteções de segurança** — simulação por padrão, limites de adição/remoção por passagem, proteção contra perda líquida, proteção de instantâneo vazio, aborto sem gravação quando os tokens expiram.
- 🗃️ **Arquivo de músicas cada vez maior** — cada faixa já vista é gravada em um banco de dados SQLite local (nome, artista, álbum, ISRC, metadados brutos, primeira/última vista).
- 🧭 **Histórico de correspondências editável** — navegue, corrija e exclua todas as correspondências de trilhas em cache por serviço na página Mapeamentos, incluindo os resultados "sem correspondência" que, de outra forma, permaneceriam incomparáveis para sempre.
- 🐳 **Executa em qualquer lugar** — um `docker compose up -d` para o aplicativo do navegador ou CLI simples + cron / Task Scheduler.

> [!IMPORTANT]
> Auto-hospedado e privado por design. Seus dados e credenciais de escuta nunca saem da sua máquina. A UI da web não tem autenticação - vincule-a ao seu LAN e não a encaminhe para a Internet.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 Capturas de tela

<div align="center">

**Um painel para cada biblioteca: status de sincronização, trabalhos, atividades ao vivo e integridade do serviço**

<img src="../../.github/assets/dashboard.png" alt="SongMirror painel mostrando status de sincronização, trabalhos configurados, atividade ao vivo e saúde para Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music e Jellyfin" width="82%">

**Configure qualquer número de sincronizações – unidirecional, mesclagem de várias fontes, grupo autoritativo ou bidirecional – em um breve assistente**

<img src="../../.github/assets/sync-wizard.png" alt="O assistente de configuração SongMirror selecionando serviços para uma sincronização bidirecional entre Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music e YouTube Music" width="82%">

**Conecte todos os serviços em seu navegador - um clique OAuth, colagem de token guiada ou uma chave API**

<img src="../../.github/assets/accounts.png" alt="A página Contas para conectar Spotify, TIDAL, Qobuz, Deezer, Amazon Music, Apple Music, YouTube Music e Jellyfin" width="82%">

**Navegue e emparelhe playlists entre serviços**

<img src="../../.github/assets/playlists.png" alt="Navegando em listas de reprodução em serviços conectados com capas e contagens de faixas" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 Início rápido

A maneira mais rápida de executá-lo é Docker — Compose extrai a imagem publicada, veicula a interface da web e executa suas sincronizações dentro do cronograma.

Para uma instalação persistente com reinicializações automáticas:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

Ou experimente a imagem pública do GHCR diretamente, sem clonar o repositório:

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

Em seguida, abra `http://localhost:8888` e conecte seus serviços no navegador. A configuração Compose não precisa de `.env` para iniciar; tudo é configurado na UI e salvo em `./data`.

A opção direta `docker run` é descartável: `docker stop songmirror` remove o contêiner e sua configuração. Use Compose para uma instalação durável com credenciais, caches e downloads persistentes, ou consulte [guia de imagem de contêiner](../docker-image.md) para tags e fixação de resumo.

Prefere executá-lo sem Docker?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> Requer [`uv`](https://docs.astral.sh/uv/) (Python 3.13+). Para o espelho de download local, também `uv tool install spotdl` e tenha `ffmpeg` em PATH.

<a id="app-language"></a>

### Idioma do aplicativo

SongMirror suporta inglês, árabe, turco, espanhol, chinês simplificado, francês, português, alemão, japonês, hindi, bengali, indonésio, coreano, italiano e vietnamita. Na primeira execução, as preferências de idioma do navegador são verificadas em ordem, incluindo variantes regionais, e o primeiro idioma compatível é usado. Se nenhum for compatível, o inglês será usado. Altere o idioma em **Configurações → Geral → Idioma**; a escolha fica salva neste navegador e é mantida após recarregar a página. Selecione **Automático (navegador)** para voltar a seguir as preferências do navegador. A interface em árabe é exibida da direita para a esquerda. Nomes de playlists, artistas e serviços, credenciais e registros de diagnóstico mantêm seus valores originais.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 Sempre em execução: Docker

O contêiner Docker é a implantação recomendada: ele atende a UI da web, executa suas sincronizações de acordo com suas programações e reinicia com o host. Compose extrai `ghcr.io/ahnafnafee/songmirror:latest`, executa-o como `songmirror` e persiste todos os caches de autenticação + em `./data`.

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

Para atualizar, execute `docker compose up -d --pull always`. Em vez disso, para construir o checkout atual, execute `docker compose up -d --build`. Consulte [guia de imagem de contêiner](../docker-image.md) para tags, fixação de resumo, pulls diretos, verificação, atualizações e reversão.

Não é necessário `.env` para iniciar — tudo é configurado no navegador e salvo em `./data`. Configuração de OAuth, token de parceiro e chave API, todos ativos na página Contas; cada assistente explica os pré-requisitos específicos do serviço e o URI de retorno de chamada exato. Em seguida, crie suas sincronizações na página Sincronizar.

Abrir SongMirror de outro computador funciona em `http://<server>:8888`. A conexão Spotify padrão usa uma sessão da web `sp_dc` colada, portanto, não precisa de aplicativo de desenvolvedor ou URL de retorno de chamada. Se você usar intencionalmente o aplicativo de desenvolvedor legado OAuth substituto atrás de Docker ou um proxy reverso, defina o URL base visível do navegador em `.env`:

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

SongMirror anunciará então `https://music.example.com/oauth/spotify/callback`; registre esse URI exato no painel do aplicativo Spotify e recrie o contêiner com `docker compose up -d --force-recreate`. Um caminho base de proxy reverso também é suportado (por exemplo, `https://example.com/songmirror`). [Spotify requer HTTPS](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) para cada redirecionamento sem loopback; HTTP simples é aceito apenas com endereços de loopback literais, como `127.0.0.1`, não um IP LAN ou `localhost`.

| | |
| --- | --- |
| Imagem | `ghcr.io/ahnafnafee/songmirror:latest` suporta AMD64 e ARM64. Cada compilação também é publicada com uma tag `sha-...` específica do commit; Tags Git como `v1.2.3` publicam adicionalmente `1.2.3`, `1.2` e `1`. Use [guia de imagem de contêiner](../docker-image.md) para fixar um resumo imutável. |
| Porto | A UI é publicada no host 8888 (o mapeamento `8888:8080` em `docker-compose.yml`; altere o lado do host se houver conflito). Somente LAN — não encaminhe-o para a Internet; a UI ainda não tem autenticação. |
| Persistência | `./data` contém credenciais, tokens, caches, arquivo de músicas e instantâneos de listas de reprodução agendadas em `playlist_backups/`. Faça backup para manter sua configuração e arquivos durante as reconstruções. |
| Transferências | Defina `DOWNLOAD_DIR` (em `.env` ou em seu shell) para o diretório de música do host (por exemplo, `F:\Torrent\Music`); compose bind-monta-o em `/music`. De Docker, defina `JELLYFIN_URL` para `http://host.docker.internal:8096`. |
| Sessões expiradas | As sessões renováveis ​​são recuperadas na próxima passagem agendada ou manual. TIDAL sessões do web player são renovadas a partir do token de atualização capturado; Os tokens Qobuz e Apple Music ainda devem ser colados novamente quando rejeitados. Não é necessário reiniciar. |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ Como funciona

Cada passagem, para cada nome de playlist selecionado que existe na fonte:

1. Faça um instantâneo da lista de reprodução de origem (faixas, ISRCs, datas adicionadas).
2. Reconcilie a lista de reprodução com o mesmo nome em cada destino conectado e selecionado simultaneamente por meio da lista de reprodução autorizada pela conta desse serviço API.
3. As trilhas ausentes são resolvidas (links armazenados em cache → ISRC → pesquisa pontuada) e anexadas as mais antigas primeiro; rastros que saíram da fonte são removidos atrás de guardas.
4. Opcionalmente, [spotDL](https://github.com/spotDL/spotify-downloader) sincroniza uma pasta de áudio local por lista de reprodução.

A fonte da verdade padrão é Spotify, mas o modo unidirecional é independente do provedor – qualquer peer de lista de reprodução conectado pode ser a fonte.

<a id="matching"></a>

### Correspondência

Mesma hierarquia que as ferramentas de serviço cruzado usam ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/), MusicBrainz): identificador exato → pesquisa → pontuação difusa.

1. Link armazenado em cache – uma vez que uma faixa de origem corresponde ao ID de catálogo/ID de vídeo de um destino, esse link é armazenado e reutilizado (imune a desvios de título).
2. ISRC — identidade de gravação exata onde o serviço a expõe.
3. Pesquisa pontuada — [RapidFuzz](https://rapidfuzz.com/) `token_set_ratio` + Jaro-Winkler, tanto no título quanto no artista bruto e romanizado ([anyascii](https://github.com/anyascii/anyascii)), ancorado pela duração. Isso trata, sem codificação:
   - Créditos de vários artistas – um serviço lista todos os recursos, outro lista os principais (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`).
   - Decoração do título - `(feat. …)`, `- 2015 Remaster`, `(From "…")`, sufixos extras de "Vídeo musical oficial".
   - Transliteração — Cirílico / Bengali / Grego / Árabe (`Камин` ↔ `Kamin`, `নেশার বোঝা` ↔ `Neshar Bojha`).
   - Faixas somente de vídeo – a pesquisa YouTube recorre ao filtro `videos` para faixas indie/OST que estão no YT apenas como uploads.

A âncora de duração desbloqueia a correspondência do título mais flexível, portanto, uma versão diferente (`Runaway - Piano Version`) ou uma capa do artista errado não é aceita quando sua duração discorda. Faixas sem correspondência confiável são relatadas e ignoradas.

<a id="multi-source-merge-sync"></a>

### Sincronização de mesclagem de várias fontes

Um trabalho Mesclar fontes combina uma ou mais playlists explícitas em um destino escolhido. Cada fonte pode vir da biblioteca de uma conta conectada ou de um URL de provedor público colado; o último é resolvido para um provedor e ID de lista de reprodução uma vez, portanto, a lista de reprodução não precisa ser salva ou seguida e as execuções agendadas não reproduzem um URL arbitrário.

- Uma união de membros – todos os constituintes são lidos antes que o destino seja reconciliado. ISRCs compartilhados são uma gravação; sem um ISRC, título exato/conservador, artista, versão e evidência de duração desduplica as sobreposições.
- Ordem determinística — primeiro a prioridade do descritor de origem e depois a ordem retornada por cada lista de reprodução de origem. A primeira ocorrência possui a posição de destino e exibe os metadados; cópias posteriores apenas enriquecem os metadados de identidade ausentes.
- Remoções seguras para a União – uma trilha de destino só pode ser removida quando uma passagem completa a encontrar ausente de todas as fontes constituintes. Uma fonte com falha, truncada, malformada, indisponível ou inconscientemente vazia desativa todas as remoções dessa passagem, enquanto as adições seguras de fontes legíveis podem continuar.
- Somente anexar por padrão — deixe a opção Remover trilhas ausentes de todas as fontes desativada para manter todas as trilhas somente de destino. Ativá-lo ativa a tampa de remoção normal por passagem após a passagem da proteção de leitura completa.

As tarefas de mesclagem atualmente têm como alvo uma lista de reprodução de provedor; o espelho de download/Jellyfin local separado liderado por Spotify não está disponível para um trabalho agregado.

<a id="authoritative-groups"></a>

### Grupos autorizados

Use um grupo autoritativo quando você seleciona ativamente a mesma lista de reprodução lógica em dois ou mais serviços, mas deseja que todos os outros serviços selecionados os sigam. Uma configuração típica é Spotify + Apple Music como autoridades, com TIDAL, Qobuz, Deezer, Amazon Music e YouTube Music como espelhos.

- A adesão vem apenas de autoridades - uma faixa adicionada em Spotify ou Apple Music se propaga para a outra autoridade e para todos os espelhos. Uma trilha adicionada apenas em um espelho é um desvio; nunca é importado de volta para as autoridades.
- Uma autoridade de pedido — escolha qual autoridade fornece os nomes das listas de reprodução e a ordem das adições. As outras autoridades ainda contribuem com alterações de membros.
- As remoções confirmadas se propagam de qualquer autoridade – uma ausência deve aparecer em duas leituras completas consecutivas antes de poder excluir qualquer coisa. Uma adição simultânea do lado da autoridade vence uma remoção.
- Os espelhos nunca recebem votação – excluir uma trilha de um espelho repara esse espelho; não exclui a faixa de Spotify ou Apple Music.
- Primeira passagem segura – cada conjunto de autoridades tem sua própria linha de base. Sua primeira passagem bem-sucedida pode adicionar trilhas ausentes, mas retém todas as remoções até que uma passagem posterior prove que a linha de base está estável.
- Falha no fechamento — se alguma autoridade estiver desconectada, ilegível ou sua lista de reprodução não puder ser aberta/criada, essa lista de reprodução lógica será ignorada em vez de retornar silenciosamente para menos autoridades.

As exclusões exigem ativação explícita e continuam sujeitas a um limite. Ative **Sincronizar exclusões** para a tarefa, ou defina `MAX_REMOVALS` ao executar sem interface gráfica, se quiser remover faixas excedentes dos espelhos para que correspondam ao conjunto de fontes de referência.

<a id="bidirectional-n-way-sync"></a>

### Sincronização bidirecional (N-way)

Por padrão, um provedor é a fonte da verdade e as edições fluem em uma direção. No modo N-way, cada provedor selecionado é um par: adicione ou remova uma trilha em qualquer um e a mudança se propaga para os outros.

A sincronização bidirecional é impossível sem estado, portanto, a associação canônica de cada lista de reprodução lógica é capturada após cada passagem limpa. Cada passagem compara cada provedor com aquele instantâneo, une as alterações e reconcilia todos com o resultado:

- Sem eco — uma adição propagada torna-se parte do instantâneo, portanto nunca é devolvida.
- Vitórias adicionais em conflitos - perder uma música é pior do que manter uma música extra.
- Proteção contra colapso de leitura - se um provedor de repente lê muito menos faixas do que a linha de base (um soluço transitório API), essa passagem é ignorada para que uma leitura incorreta não possa causar uma exclusão em massa.
- As mesmas proteções dos limites unidirecionais — por passagem `MAX_ADDS` / `MAX_REMOVALS` e proteção contra perda líquida são mantidas em todos os lados de gravação.
- **As exclusões são opcionais**: `MAX_REMOVALS` vale 0 por padrão. Uma faixa que desaparece de um serviço, seja por exclusão nesse serviço ou por retirada devido a licenciamento, é mantida nos demais e apenas registrada. Defina um limite ou ative **Sincronizar exclusões** na interface para propagar as exclusões.

> Sempre simulação primeiro. Execute sem `--execute` (ou use Visualização na UI) e leia o plano - ele imprime todas as adições/remoções propostas em cada provedor antes que qualquer coisa seja escrita.

<a id="liked-and-favorite-tracks"></a>

### Faixas curtidas e favoritas

Na etapa Listas de reprodução de uma sincronização, selecione a coleção de curtidas integrada do serviço de origem. SongMirror então pergunta onde ele deve ir em cada destino selecionado: diretamente na coleção de curtidas/favoritos do próprio serviço ou em uma nova lista de reprodução cujo nome sugerido você pode editar. Uma nova seleção é apenas para curtidas; ative Sincronizar também todas as playlists normais ou escolha playlists individuais para incluir ambas.

Isso funciona em Spotify Músicas curtidas, TIDAL/Qobuz/Deezer Faixas favoritas, Amazon Music Minhas curtidas, Apple Music Músicas favoritas e YouTube Music Músicas curtidas. Aplicam-se os mesmos caminhos de reconciliação e limites de segurança unidirecionais, de grupo autoritário e de N vias. Como nas playlists comuns, as exclusões permanecem desativadas por padrão até que **Sincronizar exclusões** seja ativado.

A concessão do web player conectado de TIDAL lida com listas de reprodução comuns e faixas favoritas nativas quando carrega `r_usr` e `w_usr`. A captura da resposta completa do token de login fornece SongMirror o token de atualização, bem como o Bearer de curta duração, para que a sessão possa ser renovada automaticamente.

Algumas dessas integrações usam interfaces web próprias dos provedores e podem mudar sem aviso prévio; o [avaliação de viabilidade](../design/2026-09-01-liked-tracks-sync-feasibility.md) registra o API e as restrições de distribuição para cada provedor.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 Backups de metadados de listas de reprodução

Os backups não exigem um segundo provedor ou uma tarefa de sincronização:

- Em Configurações → Backups de listas de reprodução, use Adicionar backup na parte superior para adicionar uma conta conectada. Escolha JSON ou XML e selecione uma frequência, como diária ou semanal. Os intervalos personalizados usam um número e uma unidade. Manter backups oferece predefinições de retenção, uma contagem personalizada ou Todos os backups.
- O padrão dos backups é `data/playlist_backups/<account-profile-id>/` (ou `/data/playlist_backups/<account-profile-id>/` em Docker). Clique em Pasta de backup para o seletor de pasta integrado ou escolha Inserir caminho manualmente. Uma pasta personalizada ainda recebe uma subpasta separada para cada conta. Usar a pasta de backup padrão restaura o padrão. A alteração de locais afeta backups futuros; arquivos antigos permanecem onde estão. A retenção e o download mais recentes aplicam-se ao local selecionado. A remoção de uma programação nunca exclui os arquivos salvos.
- Configurações → Downloads e Jellyfin → A pasta de download usa o mesmo seletor integrado e entrada manual. Escolha uma pasta acessível à sua biblioteca Jellyfin. Os downloads seguem a programação de cada sincronização ativada na guia Sincronizar. O seletor exibe caminhos de host configurados (por exemplo, `F:\Torrent\Music`) enquanto mantém seu mapeamento Docker (`/music`) internamente. As montagens de download existentes permanecem inalteradas. Pastas adicionais do host devem primeiro ser compartilhadas como montagens de ligação Docker; escolher uma pasta desmontada mostra um erro e deixa a configuração atual inalterada.

- O mesmo cartão Configurações mostra a próxima execução, a contagem de instantâneos armazenados, o último arquivo e contagens bem-sucedidas e a falha mais recente. O backup agora enfileira uma execução segura sob demanda; Baixar mais recente recupera o snapshot persistente mais recente.
- Na página Playlists, use Exportar em um cartão de serviço para baixar todas as playlists desse serviço em um arquivo JSON ou XML com versão.
- Abra uma lista de reprodução para exportar apenas essa lista de reprodução. Sua opção Soundiiz segue [Soundiiz forma de importação JSON documentada](https://soundiiz.com/data/fileExamples/playlistExport.json), então a lista de faixas baixada pode ser carregada através do fluxo Importar lista de reprodução → Do arquivo de Soundiiz.
- SongMirror JSON/XML preserva a ordem e os nomes das listas de reprodução, além dos IDs de faixa/ocorrência do provedor, ISRCs disponíveis, artistas, álbuns, posições das faixas do álbum, durações, datas adicionadas, links de arte e marcadores de entrada indisponíveis. Os fantasmas do catálogo sem ID permanecem no backup em vez de desaparecerem. Os arquivos não contêm cookies, tokens, cabeçalhos de solicitação, visualizações ou URLs de arquivos de streaming.

As exportações manuais são baixadas pelo navegador para o dispositivo que executa a IU. As exportações agendadas usam o volume de dados do aplicativo existente, portanto, nenhum segundo caminho de host ou montagem de contêiner é necessário. O backup lê a fila atrás de sincronizações e transferências em vez de acessar os clientes do provedor simultaneamente. O campo `schema_version` permite que versões futuras evoluam para o formato sem perdas sem tornar ambíguos os instantâneos antigos.

<a id="built-in-folder-picker"></a>

### Seletor de pasta integrado

Clique em um campo de pasta ou em Procurar… para abrir o seletor integrado. Use Locais, localização atual clicável, Voltar, Avançar e Subir uma pasta para navegar. Clique em uma pasta para selecioná-la; clique duas vezes, pressione Enter ou use a seta para abri-lo. A pesquisa filtra a pasta atual. Insira um caminho de pasta que aceite um endereço completo. Selecionar pasta atualiza o rascunho; salve as configurações ou agende para aplicá-lo. Cancelar deixa o rascunho inalterado. Nenhum auxiliar de desktop ou processo adicional é necessário.

A nova pasta cria uma subpasta nomeada no local aberto no momento e a abre. Os itens existentes nunca são substituídos. Cancelar a entrada do nome não cria nada; cancelar o seletor após a criação deixa a nova pasta no disco. O local de backup ou download salvo muda somente após selecionar e salvar. Em Docker, o seletor explica quais caminhos são compartilhados e mostra o caminho do contêiner e o caminho do computador configurado, quando disponível.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 Espelho de download local (Jellyfin)

Mantenha uma cópia de áudio offline de cada playlist sincronizada, uma pasta por playlist, via [spotDL](https://github.com/spotDL/spotify-downloader). A sincronização é um verdadeiro espelhamento: novas faixas são baixadas, faixas removidas são excluídas localmente. O layout está pronto para Jellyfin - aponte uma biblioteca de música Jellyfin para o diretório de download e as faixas e as listas de reprodução aparecem, permanecendo atualizadas a cada passagem:

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

Habilite-o configurando `DOWNLOAD_DIR` e instalando spotDL + ffmpeg:

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- Incremental — após o primeiro download completo, apenas as faixas recém-adicionadas são obtidas; as faixas removidas (e suas pastas de álbuns vazias) são removidas. Uma corrida interrompida continua na próxima passagem.
- Mais recente primeiro `.m3u8` — escrito na ordem de adição da data, mais recente na parte superior (defina `LOCAL_MIRROR_ORDER=oldest` para virar). Reconstrua capas/tags/mtimes de arquivos existentes com `uv run main.py --refresh-local`.
- Capas da lista de reprodução em Jellyfin — Jellyfin ignora um arquivo de capa próximo a um m3u, então defina `JELLYFIN_URL` + `JELLYFIN_API_KEY` e cada passagem carrega a capa da lista de reprodução real através do Jellyfin API.
- Qualidade de áudio - a fonte é YouTube, portanto, sem um cookie Premium do YT Music, o teto é de aproximadamente 128–160 kbps. `LOCAL_MIRROR_FORMAT=opus` mantém o fluxo nativo de YouTube sem uma recodificação de mp3; um cookie Premium (`LOCAL_MIRROR_COOKIE_FILE`) desbloqueia AAC de 256 kbps. Selecionar `flac` altera o contêiner de saída, mas não pode transformar uma fonte com perdas em áudio sem perdas.

O caminho FLAC atual de Monochrome usa recursos de reprodução de uso único e controlados por navegador, em vez de uma exportação de arquivo estável e autorizada pelo provedor API, portanto, SongMirror não o automatiza. Use o espelho local apenas para conteúdo que você possui ou está autorizado a copiar.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 Conectando cada serviço

No aplicativo da web, a página Contas orienta cada serviço e mostra os valores exatos a serem colados. Nada é procurado por terceiros.

<a id="credential-renewal"></a>

### Renovação de credencial

SongMirror atualiza as credenciais na hora certa, não com um cronômetro de atualização de token separado. Cada passagem de sincronização manual ou agendada valida os conectores que utiliza e renova os tokens de acesso suportados antes do primeiro pedido (ou uma vez após uma rejeição de autenticação). É normal que um token de acesso de curta duração expire entre as passagens – o token de atualização durável ou o cookie de renovação é o que importa. A página Contas valida o status quando carrega ou recupera o foco, mas não é a manutenção da sessão em segundo plano; agendas de sincronização habilitadas são.

| Serviço | Comportamento de renovação |
| --- | --- |
| Spotify | A conexão padrão cria um token de acesso do web player do cookie `sp_dc` salvo sob demanda e tenta novamente com um novo token após um `401`; a sessão conectada subjacente ainda pode ser revogada. O aplicativo de desenvolvedor legado OAuth permanece compatível com instalações existentes. |
| TIDAL | O token de acesso do web player importado é renovado automaticamente por meio de `auth.tidal.com` usando o token de atualização da resposta de login. SongMirror mantém o token de atualização existente quando uma resposta o omite e persiste um token girado quando TIDAL retorna um. O logout ou revogação ainda requer uma nova captura. |
| Qobuz | O `X-User-Auth-Token` colado é usado até que Qobuz o rejeite, então deve ser capturado novamente. |
| Deezer | O Pipe de curta duração JWT é renovado automaticamente a partir do `refresh-token` salvo antes do uso e uma vez após um `401/403`; o estado de renovação rotacionado é persistido. |
| Amazon Music | O token de acesso à web é renovado por meio de `/pandaToken` usando o agente de usuário do navegador capturado, o referenciador e os cookies permitidos. O fluxo `POST config.json?skipToken=false` atual inicializa o contexto do dispositivo quando necessário e os cookies girados são persistidos. Logout, alterações de segurança ou revogação do lado do servidor ainda exigem uma nova captura. |
| Apple Music | Os Bearer e Media-User-Token colados não podem ser renovados por SongMirror e devem ser capturados novamente após a rejeição. |
| YouTube Music | Data API OAuth é atualizado automaticamente dentro de 60 segundos após expirar. O modo navegador tenta a rotação de cookies de Google sempre que um destino de sincronização é criado; uma sessão do navegador já expirada deve ser exportada novamente. |
| Jellyfin | A chave API não possui ciclo de atualização do token de acesso; substitua-o somente se for revogado ou excluído. |

<a id="spotify"></a>

### Spotify

1. Faça login em <https://open.spotify.com>.
2. Abra o navegador DevTools (`F12`) → Aplicativo (Chrome/Edge) ou Armazenamento (Firefox) → Cookies → `https://open.spotify.com`.
3. Copie o valor do cookie `sp_dc` e cole-o em Contas → Spotify.

Essa única sessão da web conectada lida com a navegação na biblioteca, leituras e gravações de listas de reprodução e pesquisa de catálogo. Não requer um aplicativo de desenvolvedor Spotify, chave API ou conta Premium. Trate `sp_dc` como uma senha: SongMirror a armazena em seu diretório de dados privado, mas a integração usa as operações internas do web player de Spotify e pode precisar de manutenção se Spotify as alterar. As credenciais existentes do aplicativo de desenvolvedor OAuth permanecem um substituto compatível.

<a id="tidal"></a>

### TIDAL

1. Abra [Web player de TIDAL](https://listen.tidal.com), abra DevTools → Rede e ative Preservar log.
2. Saia e entre novamente e filtre a lista de redes por `oauth2/token`.
3. Selecione a solicitação `auth.tidal.com/v1/oauth2/token` bem-sucedida. Em Payload (Chrome/Edge) ou Solicitação (Firefox), copie o valor do formulário `client_id` no campo de ID do cliente do Web-player de SongMirror.
4. Abra a guia Resposta da solicitação e copie seu JSON completo na resposta do token do player da Web. Deve incluir `access_token` e `refresh_token`.
5. Conecte-se. SongMirror exerce imediatamente a concessão de atualização e se recusa a relatar sucesso se o ID do cliente não puder renová-lo.

O ID do cliente OAuth é metadado de solicitação e não é a declaração numérica `cid` dentro do token de acesso TIDAL. SongMirror extrai apenas o token de acesso, token de atualização, ID do cliente, escopos, expiração e país do catálogo; dados de resposta não relacionados são descartados. Ele é renovado pouco antes de expirar e uma vez após uma rejeição de autenticação por meio de `https://auth.tidal.com/v1/oauth2/token`, preservando a rotação do token de atualização. A pasta de cabeçalho de solicitação OpenAPI mais antiga permanece compatível, mas como não contém nenhum token de atualização, ainda precisa ser colada novamente após expirar. Apenas os metadados do catálogo e as playlists do usuário conectado são usados ​​– os ativos de reprodução ficam fora dessa integração.

<a id="qobuz"></a>

### Qobuz

Faça login em <https://play.qobuz.com>, abra DevTools → Rede e filtre por `api.json/0.2`. Escolha qualquer solicitação contendo `X-App-Id` e `X-User-Auth-Token` — incluindo uma solicitação `album/story` autenticada — e copie seus cabeçalhos de solicitação ou copie-os como cURL e cole-os no assistente. SongMirror persiste apenas esses dois valores, envia-os usando o mesmo fluxo baseado em cabeçalho que o web player e descarta cookies e metadados não relacionados do navegador. Nenhuma aprovação comercial API ou ID de usuário é necessária; as credenciais de parceiros existentes continuam sendo um substituto de ambiente compatível.

O adaptador usa apenas pontos de extremidade de pesquisa de catálogo e lista de reprodução — ele não solicita URLs de fluxo ou de arquivo.

<a id="deezer"></a>

### Deezer

Faça login em <https://www.deezer.com>, abra DevTools → Rede e recarregue a página. Filtre por `auth.deezer.com/login/renew`, copie os cabeçalhos dessa solicitação (ou copie-os como cURL) e cole-os no campo de renovação. Firefox pode, em vez disso, copiar os cookies de solicitação como um bloco delimitado por ponto e vírgula; essa forma também é aceita. SongMirror retém apenas o cookie `refresh-token` dedicado e o usa para renovar o Pipe JWT de curta duração de Deezer automaticamente. Você também pode colar uma solicitação `pipe.deezer.com/api` atual como uma inicialização imediata, mas isso não é necessário quando a renovação é configurada. As adições e remoções da lista de reprodução usam a sessão renovável do Pipe; nenhum cookie `arl` é necessário. Os tokens OAuth de desenvolvedor existentes continuam sendo um substituto de ambiente compatível.

<a id="amazon-music"></a>

### Amazon Music

Nenhuma aprovação do desenvolvedor é necessária para o conector padrão. Ele usa as mesmas rotas autenticadas GraphQL e de renovação de token que o web player Amazon Music:

1. Faça login em <https://music.amazon.com> e abra DevTools → Rede.
2. Recarregue a página, filtre por `config.json` e selecione a solicitação de login. (`pandaToken` também funciona quando aparece, mas não é obrigatório.)
3. Escolha Copiar cabeçalhos de solicitação ou Copiar como cURL e cole-o no campo de renovação. Mantenha os cabeçalhos `User-Agent`, `Referer` e `Cookie` completos para que SongMirror possa reproduzir o mesmo contexto do navegador.
4. Opcionalmente, copie a resposta `config.json` conectada no campo bootstrap; SongMirror normalmente pode buscar o contexto do dispositivo usando a sessão de renovação.

SongMirror deriva o mesmo valor de autorização `AmznMusic` localmente e o atualiza por meio de `music.amazon.com/pandaToken` antes de expirar ou uma vez após uma rejeição de autenticação. Durante a conexão, ele usa a solicitação de configuração atual no estilo do navegador quando o contexto do dispositivo é necessário, exige que `/pandaToken` crie um token de acesso e rejeita a conexão se a Amazon revogar o cookie de renovação do Music. Ele armazena apenas o agente do usuário do navegador, idioma, referenciador de música, uma lista de permissões nomeada de cookies de autenticação/sessão da Amazon e contexto limitado do dispositivo cliente de música; análises, experimentos, console AWS, CSRF e outros dados não relacionados do navegador são descartados. Esses cookies retidos ainda são confidenciais, portanto, mantenha SongMirror privado em seu LAN. Um logout, alteração de senha/segurança ou revogação da Amazon ainda pode exigir uma nova captura.

Esta é uma interface de cliente web original não suportada e a Amazon pode alterá-la sem aviso prévio. O [Amazon Music Rede API](https://developer.amazon.com/docs/music/API_web_overview.html) documentado ainda é uma versão beta fechada; as credenciais de parceiro aprovadas permanecem como alternativa opcional quando configuradas por meio de variáveis ​​de ambiente.

<a id="apple-music"></a>

### Apple Music

Não é necessária uma conta de desenvolvedor Apple – dois cabeçalhos de `music.apple.com` são suficientes. Abra <https://music.apple.com>, faça login, abra DevTools → Rede, reproduza uma música, filtre por `amp-api.music.apple.com` e, a partir dos cabeçalhos de qualquer solicitação, copie:

- `authorization: Bearer eyJ...` → token Bearer (a parte `eyJ...`, sem `Bearer `)
- `media-user-token: ...` → Token do usuário (valor total)

O assistente de conexão permite colar os cabeçalhos brutos e analisar os valores para você. Os tokens duram meses; cole-os novamente na página Contas quando expirarem.

Um ID Apple sem uma assinatura Apple Music ativa ainda pode se conectar no modo somente catálogo. Nesse modo, cole um link de lista de reprodução pública Apple Music em Transferências para copiá-lo para outro serviço conectado. A navegação na biblioteca da Apple, a sincronização agendada e o uso de Apple Music como destino de transferência ainda exigem o privilégio pago CloudLibrary; SongMirror mostra essas operações como indisponíveis em vez de tratar as credenciais de catálogo válidas como expiradas.

<a id="youtube-music"></a>

### YouTube Music

Fala com o [YouTube Data API v3](https://developers.google.com/youtube/v3) oficial, cujo token de atualização OAuth é durável e sobrevive a reinicializações.

1. No [Google Console em nuvem](https://console.cloud.google.com), crie um projeto, habilite YouTube Data API v3 e crie um cliente OAuth do tipo TVs e dispositivos de entrada limitada.
2. Na tela de consentimento OAuth, defina Status de publicação → Em produção (deixar em "Teste" expira o token após 7 dias).
3. No aplicativo, cole o ID do cliente + segredo e preencha o código do dispositivo na tela.

> Cota: o Data API permite 10.000 unidades/dia (uma pesquisa custa 100, uma adição/remoção 50). A manutenção em estado estacionário é barata; um grande acúmulo na primeira vez pode atingir o limite e ser retomado no dia seguinte.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ sem interface gráfica CLI

Prefere `.env` + cron / Task Scheduler? O mesmo mecanismo funciona sem interface gráfica.

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

Sinalizadores úteis:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

Chave env vars (consulte `.env.example`): as credenciais para quaisquer provedores que você usar, `PLAYLISTS`, `SYNC_INTERVAL`, `MAX_ADDS` / `MAX_REMOVALS`, `DOWNLOAD_DIR`, `SYNC_MODE`, `SYNC_SOURCE`, `SYNC_AUTHORITIES` e `PROVIDERS`.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ Salvaguardas de segurança

As remoções são destrutivas, por isso são protegidas:

- simulação é o padrão — nada muda sem `--execute` (ou a ação de sincronização real da UI).
- Se a origem retornar 0 faixas para uma lista de reprodução que o destino mostra como não vazia, as remoções serão ignoradas (uma falha transitória API não pode esvaziar uma lista de reprodução).
- **As exclusões ficam desativadas por padrão**: `MAX_REMOVALS=0` impede todas as exclusões; elas são registradas, mas nunca aplicadas. Assim, uma retirada por licenciamento em uma plataforma não provoca exclusões em cadeia nas demais. Ative **Sincronizar exclusões** em cada sincronização ou defina `MAX_REMOVALS`. Mesmo após a ativação, se o número de exclusões pendentes em uma execução ultrapassar o limite, todas serão ignoradas e registradas.
- `MAX_ADDS` limita cada gravação que produz carimbo de data/hora em uma passagem de sincronização, incluindo reparo de cronologia. Se uma partida recuperada mais antiga precisar de uma repetição de sufixo maior do que o limite permite, SongMirror adia-a para a próxima passagem em vez de fazê-la parecer mais nova ou causar uma explosão gigante do provedor. Uma transferência única não tem próxima passagem, portanto nunca é adiada: ela copia todas as faixas solicitadas, anexando na ordem de origem, a menos que você ative "Preservar pedido adicionado recentemente" para essa transferência, que gasta quaisquer custos de reparo.
- Um reparo de cronologia prepara uma cópia duplicada antes de retirar o original. Em um serviço cuja exclusão leva todas as cópias de uma música, a contagem do detentor deve estar correta, então Apple Music relê até que as cópias preparadas estejam visíveis e se recusa a retirar qualquer coisa contra uma leitura que ainda rastreia suas próprias gravações. Deezer ignora totalmente o reparo e sempre anexa: também não possui inserção posicional, portanto, repetir um pedido que não pode expressar não vale o risco para o destino. O formulário de transferência deixa seu pedido em cinza e diz o porquê.
- Proteção contra perda líquida — uma trilha do lado do destino semelhante a uma trilha de origem que não tem correspondência naquele serviço é mantida e não excluída.
- Qualquer falha na autenticação do provedor anula imediatamente a passagem desse provedor — sem exclusões parciais de tokens expirados.
- Uma tarefa de mesclagem deve concluir cada leitura de origem constituinte antes de ser excluída de seu destino; quaisquer forças de instantâneo de origem parcial/com falha que passam para o comportamento somente de acréscimo.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ Cache e arquivo de músicas

Tudo o que pode ser resolvido é armazenado em cache para que as passagens de estado estacionário sejam quase instantâneas: caches de resolução por serviço (ISRC + pesquisa, incluindo erros), um cache de lista de trilhas com chave `snapshot_id`, links de identificador exatos em SQLite e um salto de instantâneo por par (`unchanged since last clean sync`).

Cada passagem também arquiva os metadados de cada trilha que vê em `song_cache.db` — um arquivo SQLite que só cresce. As faixas removidas permanecem arquivadas com nome, artista, álbum, duração, ISRC, instantâneo bruto JSON e carimbos de data e hora da primeira/última visualização:

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### Resolver mapeamentos

Cada serviço mantém seu próprio cache de resolução, mapeando uma chave `title|artist` normalizada para o ID do catálogo correspondente
esse serviço. Uma correspondência é reutilizada para sempre, assim como um resultado "sem correspondência", que é o que torna uma pista que falhou
para corresponder uma vez, permanece incomparável em cada passagem posterior.

A página Mapeamentos na UI da web expõe esses caches diretamente, por serviço:

- pesquise todo o cache por título, artista ou id resolvido
- filtrar para entradas definidas manualmente (uma correspondência que você escolheu no editor de conflito de transferência) ou para entradas sem correspondência
- corrija um ID errado colando o link da trilha correta ou exclua um mapeamento para que a próxima passagem o procure novamente
- limpe todas as entradas "sem correspondência" de um serviço em uma ação, para que um lote de pesquisas com falha tenha outra tentativa

Quando uma falha resolvida for resolvida posteriormente, simplesmente anexá-la faria a música antiga parecer mais nova. Para lista de reprodução
destinos, SongMirror em vez disso, reproduz essa música e o sufixo mais recente já presente, do mais antigo para o mais recente, e depois remove
as cópias mais antigas. Os provedores não permitem que os clientes restaurem os carimbos de data/hora originais, mas isso preserva sua relativa
Pedido adicionado recentemente. As coleções nativas curtidas/favoritas permanecem apenas para membros e nunca são reproduzidas.

As edições são recusadas com uma mensagem clara enquanto uma sincronização está em execução, porque uma passagem mantém o cache na memória para sua execução.
toda a duração e os substituiria na conclusão.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 Layout do projeto

Entrada CLI: `uv run main.py` (calço fino) ou `python -m songmirror`. Entrada da web: `songmirror.web:app`.

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

Adicionando outro serviço: subclasse `MirrorTarget`, implemente ~ 8 métodos, adicione seu construtor a `engine/targets`' `_REGISTRY` e sua classe a `_CLASSES` e adicione um `Connector` correspondente em `services/accounts`. Toda a reconciliação – comparação, ordenação, salvaguardas de segurança, registro, salto de instantâneo – é herdada.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 Solução de problemas

- `Missing required environment variable` — preencha `.env` (CLI) ou conecte o serviço na IU.
- TIDAL relatórios `Expired` — saia e entre novamente em `listen.tidal.com` e cole o `client_id` da carga útil da solicitação `oauth2/token` e sua resposta completa JSON em Contas. Uma solicitação OpenAPI copiada tem apenas Bearer de curta duração e não pode ser renovada.
- TIDAL relatórios HTTP 429 — este é um limite de taxa temporário, não um login expirado. SongMirror respeita o atraso de nova tentativa do provedor e armazena em cache as verificações de integridade da conta em vez de testar repetidamente o API.
- Qobuz ou relatórios da Apple `Expired` / `401` / `403` — essas sessões coladas não têm segredo renovável; capture uma nova solicitação ou token conectado em Contas.
- TIDAL diz que o token não possui acesso à trilha curtida – capture uma nova resposta de token do player da web conectado carregando `r_usr` e `w_usr`.
- Deezer falha na renovação — capture uma nova solicitação `auth.deezer.com/login/renew` (ou seu cookie `refresh-token`). Um Pipe Bearer atual por si só é apenas um bootstrap temporário.
- Amazon Music falha na renovação — capture uma nova solicitação `POST /config.json?skipToken=false` de login com seus cabeçalhos `User-Agent`, `Referer` e `Cookie` completos. A resposta JSON é opcional.
- YouTube Music o modo do navegador expira — exporte novos cabeçalhos de solicitação do navegador. Para uma configuração autônoma mais durável, use Data API OAuth com uma tela de consentimento em produção.
- Spotify relatórios expirados – faça login novamente em `open.spotify.com` e cole um novo cookie `sp_dc` em Contas.
- Uma playlist não está sincronizando — confirme se ela está no escopo da playlist de sincronização e se existe na origem (os destinos são criados automaticamente em uma passagem real).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄 Licença

Direitos autorais © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
Este projeto é licenciado [MIT](../../LICENSE).

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
