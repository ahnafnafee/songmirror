<div align="center"><a name="readme-top"></a>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/lockup-dark.png">
  <img src="../../.github/assets/lockup-light.png" alt="SongMirror" width="440">
</picture>

# SongMirror

<!-- LANGUAGE NAVIGATION -->
<p align="center"><a href="../../README.md" lang="en">English</a> · <a href="README.ar.md" lang="ar" dir="rtl">العربية</a> · <a href="README.tr.md" lang="tr">Türkçe</a> · <a href="README.es.md" lang="es">Español</a> · <a href="README.zh.md" lang="zh">简体中文</a> · <a href="README.fr.md" lang="fr">Français</a> · <a href="README.pt.md" lang="pt">Português</a> · <a href="README.de.md" lang="de">Deutsch</a> · <a href="README.ja.md" lang="ja">日本語</a> · <a href="README.hi.md" lang="hi">हिन्दी</a> · <a href="README.bn.md" lang="bn">বাংলা</a> · <a href="README.id.md" lang="id">Bahasa Indonesia</a> · <a href="README.ko.md" lang="ko">한국어</a> · <a href="README.it.md" lang="it">Italiano</a> · <a href="README.vi.md" lang="vi">Tiếng Việt</a></p>
<!-- /LANGUAGE NAVIGATION -->

Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music、YouTube Music の自己ホスト型常時プレイリスト同期 — さらにローカルオーディオミラーJellyfin.<br/> の準備ができました
ユーザーが所有して実行する、Soundiiz、TuneMyMusic、および FreeYourMusic に代わる、無料のオープンソースで自己ホスト型の代替サービス。

**一方向、マルチソースのマージ、権威グループ、または完全な双方向 (N 方向) 同期 · ワンタイム プレイリスト転送 · ISRC による正確なマッチング · すべてブラウザから**

[クイックスタート](#quick-start) · [特徴](#features) · [スクリーンショット](#screenshots) · [常に実行中: Docker](#always-running-docker) · [仕組み](#how-it-works) · [不具合を報告][github-issues-link] · [機能を提案][github-issues-link]

<!-- SHIELD GROUP -->

[![CI][ci-shield]][ci-link]
[![License][license-shield]][license-link]
[![Python][python-shield]][python-link]
[![Docker][docker-shield]][docker-link]<br/>
[![Stars][stars-shield]][stars-link]
[![Forks][forks-shield]][forks-link]
[![Issues][issues-shield]][issues-link]
[![Last commit][last-commit-shield]][last-commit-link]

**このプロジェクトを共有する**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]

<sup>一度設定すれば、キュレートしたすべてのプレイリストが日付の追加順にすべてのサービスにミラーリングされます。</sup>

<a href="../../.github/assets/songmirror-demo.mp4"><img src="../../.github/assets/songmirror-demo.gif" alt="SongMirror デモ — ロゴ公開、ダッシュボード、一方向および双方向同期セットアップ、ライブ プレイリスト転送、および 7 つの音楽サービスにわたる ISRC による正確なマッチング" width="88%"></a>

<sup>▶ <a href="../../.github/assets/songmirror-demo.mp4">1080p バージョンを見る</a></sup>

</div>

> [!NOTE]
> Web アプリ + グラフィカル インターフェイス CLI なし、エンジン 1 つ。ブラウザ UI をクリックしてサービスに接続し、同期を構築し、プレイリストを転送します。または、`.env` + cron スタイルで実行します。どちらも同じ同期コアを駆動します。

<details>
<summary><kbd>目次</kbd></summary>

#### 目次

- [✨ 特徴](#features)
- [📸 スクリーンショット](#screenshots)
- [🚀 クイックスタート](#quick-start)
  - [アプリ言語](#app-language)
- [🐳 常に実行中: Docker](#always-running-docker)
- [⚙️ 仕組み](#how-it-works)
  - [マッチング](#matching)
  - [マルチソースのマージ同期](#multi-source-merge-sync)
  - [権威あるグループ](#authoritative-groups)
  - [双方向 (N 方向) 同期](#bidirectional-n-way-sync)
- [📦 プレイリストのメタデータのバックアップ](#playlist-metadata-backups)
- [💿 ローカル ダウンロード ミラー (Jellyfin)](#local-download-mirror-jellyfin)
- [🔌 各サービスを接続する](#connecting-each-service)
  - [資格の更新](#credential-renewal)
  - [Spotify](#spotify)
  - [TIDAL](#tidal)
  - [Qobuz](#qobuz)
  - [Deezer](#deezer)
  - [Amazon Music](#amazon-music)
  - [Apple Music](#apple-music)
  - [YouTube Music](#youtube-music)
- [🖥️ グラフィカルインターフェイス CLI なし](#headless-cli)
- [🛡️ 安全対策](#safety-rails)
- [🗃️ キャッシュと曲のアーカイブ](#caching-song-archive)
  - [マッピングを解決する](#resolve-mappings)
- [🧱 プロジェクトのレイアウト](#project-layout)
- [🩺 トラブルシューティング](#troubleshooting)
- [📄ライセンス](#license)

####

<br/>

</details>

<a id="features"></a>

## ✨ 特徴

SongMirror は、手動で再追加したり、1 つずつコピーしたり、ライブラリを保持する有料のクラウド サービスを必要とせずに、プレイリストをどこでも同一に保ちます。これはクロスプラットフォーム、自己ホスト型、オープンソースです。

- 🔁 **追加のみではなく、真のミラーリング** - 追加と削除。真実の情報源 (デフォルトでは Spotify) を選択すると、他の情報源はそれに従うようになります。
- ⇆ **権限のあるグループ** — 2 つ以上のサービス (例: Spotify + Apple Music) を信頼しますが、選択された他のすべてのサービスは宛先のみのミラーのままです。
- ⇄ **双方向 N-way 同期** — 接続されているサービスでの追加または削除は、削除ガードの背後でエコーなしで他のすべてのサービスに伝播します。
- ⇉ **マルチソースのマージ同期** — パブリック リストを保存したりフォローしたりせずに、ライブラリ プレイリストとパブリック プレイリスト URL の重複排除された結合を 1 つの宛先にスケジュールします。
- ♥ **お気に入りのトラックとお気に入りのトラック** — 各サービスに組み込まれているお気に入りのコレクションを 7 つの音楽プロバイダーすべてで同期し、送信先独自のお気に入りまたは新しい名前付きプレイリストに同期します。
- 🎯 **ISRC による正確なマッチング** — 利用可能な場合は正確な録音 ID、おおよその Unicode と互換性のあるタイトル/アーティスト/再生時間のフォールバック (注目アーティストのクレジットの違い、「- 2015 Remaster」の接尾辞、非ラテン文字、ビデオのみのアップロード - すべて処理)。
- 🎛️ **複数の名前付き同期** — それぞれに独自のサービス、プレイリスト、スケジュール、安全キャップを備えた独立した同期を好きなだけセットアップします。
- ↪️ **1 回限りの転送** — ライブ進行状況バーを使用して、あるサービスから別のサービスにプレイリストをコピーします。コピー中に一時停止、再開、または停止し、一致しないトラックを手動で解決します。
- 🕒 **トラックを追加するか、トラックの順序を保持します** — コピーはデフォルトで宛先の最後に着地し、高速かつ追加的です。 [最近追加した順序を保存] をオンにすると、最も古い新しいトラックの後にトラックが書き換えられ、日付が追加された順序がソースと一致するようになります。
- 🔗 **リンクから転送** — 接続されているサービスからパブリック プレイリストの URL を貼り付け、それを直接コピーします。最初に保存したりフォローしたりする必要はありません。
- 🌐 **フォローしているプレイリスト** — 自分が作成したプレイリストだけでなく、フォローしているが所有していないプレイリストも同期および転送します。
- 📦 **スケジュールされたメタデータ バックアップ** — JSON/XML、保持制限、および表示される成功/失敗履歴を使用して、アカウントのプレイリスト ライブラリ全体を独自のスケジュールで永続的なアプリ データにアーカイブします。ワンタイムダウンロードとインポート可能な Soundiiz JSON も引き続きご利用いただけます。
- 💿 **ローカル ダウンロード ミラー** — オフライン オーディオを保持します。Jellyfin の `AlbumArtist/Album` レイアウトでプレイリストごとに 1 つのフォルダーがあり、カバーと自動更新される `.m3u8` が含まれます。
- 🛡️ **安全対策** — デフォルトでのシミュレーション、パスごとの追加/削除の上限、純損失保護、空のスナップショット ガード、トークンの有効期限が切れたときに書き込みを行わずに中止します。
- 🗃️ **増え続ける曲アーカイブ** — これまでに見たすべてのトラックは、ローカルの SQLite データベース (名前、アーティスト、アルバム、ISRC、生のメタデータ、最初/最後に見たもの) に記録されます。
- 🧭 **編集可能な一致履歴** — マッピング ページから、サービスごとにキャッシュされたすべてのトラック一致を参照、修正、削除できます。これには、永遠に一致しないままになる「一致なし」結果も含まれます。
- 🐳 **どこでも実行可能** — ブラウザー アプリの場合は 1 つの `docker compose up -d`、またはプレーンな CLI + cron / Task Scheduler。

> [!IMPORTANT]
> 設計により自己ホスト型でプライベートです。リスニング データと認証情報がマシンから流出することはありません。 Web UI には認証がありません。Web UI を LAN にバインドし、インターネットにポート転送しません。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="screenshots"></a>

## 📸 スクリーンショット

<div align="center">

**すべてのライブラリに 1 つのダッシュボード - 同期ステータス、ジョブ、ライブ アクティビティ、およびサービスの健全性**

<img src="../../.github/assets/dashboard.png" alt="SongMirror ダッシュボードには、Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music の同期ステータス、構成されたジョブ、ライブアクティビティ、および健全性が表示されます。 YouTube Music、および Jellyfin" width="82%">

**短いウィザードで、任意の数の同期 (一方向、マルチソースのマージ、権威グループ、または双方向) をセットアップします**

<img src="../../.github/assets/sync-wizard.png" alt="SongMirror セットアップ ウィザードは、Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music、YouTube Music にわたる双方向同期のためのサービスを選択します。" width="82%">

**ブラウザ内のすべてのサービスに接続します — ワンクリック OAuth、ガイド付きトークン貼り付け、または API キー**

<img src="../../.github/assets/accounts.png" alt="Spotify、TIDAL、Qobuz、Deezer、Amazon Music、Apple Music、YouTube Music、Jellyfin を接続するためのアカウント ページ" width="82%">

**サービス間でプレイリストを参照してペアリングする**

<img src="../../.github/assets/playlists.png" alt="接続されたサービス全体でカバー アートとトラック数を含むプレイリストを参照する" width="82%">

</div>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="quick-start"></a>

## 🚀 クイックスタート

これを実行する最も速い方法は Docker — Compose は公開されたイメージをプルし、Web UI を提供し、スケジュールに従って同期を実行します。

自動再起動による永続インストールの場合:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
docker compose up -d
```

または、リポジトリのクローンを作成せずに、パブリック GHCR イメージを直接試してみます。

```bash
docker run --rm -d --name songmirror -p 127.0.0.1:8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

次に、`http://localhost:8888` を開き、ブラウザでサービスに接続します。 Compose セットアップを開始するには、`.env` は必要ありません。すべては UI で設定され、`./data` に保存されます。

直接の `docker run` オプションは使い捨てです: `docker stop songmirror` はコンテナーとその構成を削除します。永続的な認証情報、キャッシュ、ダウンロードを使用した永続的なインストールには Compose を使用するか、タグとダイジェストの固定については [コンテナイメージガイド](../docker-image.md) を参照してください。

Docker なしで実行したいですか?

```bash
uv sync
uv run uvicorn songmirror.web:app --host 0.0.0.0 --port 8080   # then open http://127.0.0.1:8080
```

> [`uv`](https://docs.astral.sh/uv/) (Python 3.13+) が必要です。ローカル ダウンロード ミラーの場合も、`uv tool install spotdl` を指定し、PATH に `ffmpeg` を指定します。

<a id="app-language"></a>

### アプリ言語

SongMirror は、英語、アラビア語、トルコ語、スペイン語、簡体字中国語、フランス語、ポルトガル語、ドイツ語、日本語、ヒンディー語、ベンガル語、インドネシア語、韓国語、イタリア語、ベトナム語をサポートしています。 初回起動時は、地域別の表記を含めてブラウザの言語設定を順番に確認し、最初に対応する言語を使用します。対応する言語がなければ英語を使用します。**設定 → 一般 → 言語** で言語を変更できます。選択はこのブラウザに保存され、再読み込み後も維持されます。**自動（ブラウザー）** を選ぶと、再びブラウザの設定に従います。アラビア語の画面は右から左に表示されます。プレイリスト名、アーティスト名、サービス名、認証情報、診断ログは元の値のままです。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="always-running-docker"></a>

## 🐳 常に実行中: Docker

Docker コンテナは推奨される展開です。Web UI を提供し、スケジュールに従って同期を実行し、ホストとともに再起動します。 Compose は `ghcr.io/ahnafnafee/songmirror:latest` をプルし、`songmirror` として実行し、すべての認証とキャッシュを `./data` に保持します。

```bash
docker compose up -d             # pull the published image + start in the background
# open http://<host>:8888 and connect your services + create syncs in the browser
docker compose logs -f           # watch it work
```

更新するには、`docker compose up -d --pull always` を実行します。代わりに現在のチェックアウトを構築するには、`docker compose up -d --build` を実行します。タグ、ダイジェスト固定、直接プル、検証、更新、ロールバックについては、[コンテナイメージガイド](../docker-image.md) を参照してください。

開始するのに `.env` は必要ありません。すべてはブラウザーで設定され、`./data` に保存されます。 OAuth、パートナー トークン、および API キーの設定はすべて [アカウント] ページに表示されます。各ウィザードでは、サービス固有の前提条件と正確なコールバック URI について説明します。次に、[同期] ページで同期を構築します。

別のコンピューターから SongMirror を開くと、`http://<server>:8888` で動作します。デフォルトの Spotify 接続では、貼り付けられた `sp_dc` Web セッションが使用されるため、開発者アプリやコールバック URL は必要ありません。従来の開発者アプリ OAuth を Docker の背後にフォールバックするか、リバース プロキシを意図的に使用する場合は、ブラウザに表示されるベース URL を `.env` に設定します。

```dotenv
SPOTIFY_AUTH_MODE=oauth
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SONGMIRROR_PUBLIC_URL=https://music.example.com
```

次に、SongMirror は `https://music.example.com/oauth/spotify/callback` をアドバタイズします。その正確な URI を Spotify アプリのダッシュボードに登録し、`docker compose up -d --force-recreate` でコンテナを再作成します。リバースプロキシのベースパスもサポートされています (例: `https://example.com/songmirror`)。非ループバック リダイレクトごとに [Spotify には HTTPS が必要です](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)。プレーン HTTP は、LAN IP や `localhost` ではなく、`127.0.0.1` などのリテラル ループバック アドレスでのみ受け入れられます。

| | |
| --- | --- |
|画像 | `ghcr.io/ahnafnafee/songmirror:latest` は、AMD64 および ARM64 をサポートします。各ビルドは、コミット固有の `sha-...` タグも付けて公開されます。 `v1.2.3` などの Git タグは、`1.2.3`、`1.2`、`1` を追加で公開します。不変ダイジェストを固定するには、[コンテナイメージガイド](../docker-image.md) を使用します。 |
|ポート | UI はホスト 8888 で公開されます (`docker-compose.yml` の `8888:8080` マッピング。衝突する場合はホスト側を変更します)。 LAN のみ — インターネットにポート転送しないでください。 UI にはまだ認証がありません。 |
|永続性 | `./data` は、認証情報、トークン、キャッシュ、曲のアーカイブ、およびスケジュールされたプレイリストのスナップショットを `playlist_backups/` に保持します。バックアップして、再構築後もセットアップとアーカイブを保持します。 |
|ダウンロード | `DOWNLOAD_DIR` (`.env` またはシェル内) をホスト音楽ディレクトリ (例: `F:\Torrent\Music`) に設定します。 compose はそれを `/music` にバインドマウントします。 Docker から、`JELLYFIN_URL` を `http://host.docker.internal:8096` に設定します。 |
|期限切れのセッション |更新可能なセッションは、次回のスケジュールされたパスまたは手動パスで回復します。 TIDAL Web プレーヤー セッションは、取得されたリフレッシュ トークンから更新されます。 Qobuz および Apple Music トークンは、拒否された場合でも再度貼り付ける必要があります。再起動は必要ありません。 |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="how-it-works"></a>

## ⚙️ 仕組み

ソース上に存在する選択されたプレイリスト名ごとのすべてのパス:

1. ソース プレイリスト (トラック、ISRC、追加日) のスナップショットを作成します。
2. サービスのアカウント承認済みプレイリスト API を通じて、選択され接続されているすべてのターゲット上の同じ名前のプレイリストを同時に調整します。
3. 欠落しているトラックは解決され (キャッシュされたリンク → ISRC → スコア付き検索)、古いものから順に追加されます。情報源から消えた痕跡は警備員の後ろで取り除かれます。
4. オプションで、[spotDL](https://github.com/spotDL/spotify-downloader) はプレイリストごとにローカル オーディオ フォルダーを同期します。

デフォルトの信頼できるソースは Spotify ですが、一方向モードはプロバイダーに依存せず、代わりに接続されているプレイリスト ピアをソースにすることができます。

<a id="matching"></a>

### マッチング

クロスサービス ツールが使用するのと同じ階層 ([TuneLink](https://tommcfarlin.com/case-study-tunelink-matching-music-ai/)、MusicBrainz): 正確な識別子 → 検索 → ファジー スコア。

1. キャッシュされたリンク — ソース トラックがターゲットのカタログ ID/ビデオ ID と一致すると、そのリンクは保存され、再利用されます (タイトル ドリフトの影響を受けません)。
2. ISRC — サービスが公開する正確な記録 ID。
3. **類似度による検索** — [RapidFuzz](https://rapidfuzz.com/) の `token_set_ratio` と Jaro-Winkler を使い、元のタイトルとアーティスト名、および [anyascii](https://github.com/anyascii/anyascii) でローマ字に変換した表記の両方を比較します。再生時間を判断の基準にすることで、個別の例外をコードに埋め込まずに次の違いに対応できます。
   - マルチアーティストのクレジット — 1 つのサービスではすべての機能がリストされ、別のサービスでは主要な機能がリストされます (`Arijit Singh, Ved Sharma, …` ↔ `Arijit Singh`)。
   - タイトル装飾 — `(feat. …)`、`- 2015 Remaster`、`(From "…")`、追加の「公式ミュージック ビデオ」の接尾辞。
   - 音訳 — キリル文字 / ベンガル語 / ギリシャ語 / アラビア語 (`Камин` ↔ `Kamin`、`নেশার বোঝা` ↔ `Neshar Bojha`)。
   - ビデオのみのトラック - YouTube 検索は、YT にアップロードとしてのみ存在するインディーズ/OST トラックの `videos` フィルタにフォールバックします。

再生時間を基準にすることで、タイトルの一致条件を緩められます。そのため、別バージョン（`Runaway - Piano Version`）や別のアーティストによるカバーは、長さが一致しなければ採用されません。十分な確信を持って照合できない曲は報告し、スキップします。

<a id="multi-source-merge-sync"></a>

### マルチソースのマージ同期

**ソースを統合**するジョブでは、指定した 1 つ以上のプレイリストを、選択した 1 つの転送先にまとめます。各ソースには、接続済みアカウントのライブラリにあるプレイリスト、または貼り付けた公開プレイリストの URL を使えます。URL は最初にサービスとプレイリスト ID に変換されるため、そのプレイリストを保存・フォローする必要はなく、定期実行時に任意の URL を再び開くこともありません。

- 1 つのメンバーシップ ユニオン - 宛先が調整される前に、すべての構成要素が読み取られます。共有 ISRC は 1 つの記録です。 ISRC がなければ、正確/保守的なタイトル、アーティスト、バージョン、および期間の証拠が重複を排除します。
- 決定的な順序 — 最初にソース記述子の優先順位があり、次に各ソース プレイリストによって返される順序です。最初に出現したものは、宛先の位置と表示メタデータを所有します。後のコピーでは、欠落している ID メタデータのみが強化されます。
- **すべてのソースを確認してから削除** — 転送先の曲を削除できるのは、すべてのソースを完全に読み取り、どこにもその曲がないと確認できた場合だけです。読み取りの失敗、途中で切れた応答、不正なデータ、利用不能、または本当に空か判断できないソースが 1 つでもあれば、その回の削除はすべて無効になります。読み取れたソースからの安全な追加は継続できます。
- デフォルトでは追加のみ — すべての宛先のみのトラックを保持するには、「すべてのソースからトラックが存在しない場合は削除」をオフのままにします。これをオンにすると、完全読み取りガードが通過した後、通常のパスごとの削除キャップがオプトインされます。

マージ ジョブは現在、1 つのプロバイダー プレイリストをターゲットとしています。個別の Spotify-led ローカル ダウンロード/Jellyfin ミラーは、集約ジョブでは使用できません。

<a id="authoritative-groups"></a>

### 権威あるグループ

**基準となるサービスのグループ**は、2 つ以上のサービスで同じプレイリストを編集し、それ以外の選択済みサービスにはその内容を反映させたい場合に使います。例えば、Spotify と Apple Music を基準とし、TIDAL、Qobuz、Deezer、Amazon Music、YouTube Music をミラーに設定できます。

- メンバーシップは権限からのみ取得されます。Spotify または Apple Music に追加されたトラックは、他の権限とすべてのミラーに伝播します。ミラー上にのみ追加されたトラックはドリフトです。当局に逆輸入されることはありません。
- 1 つの順序の権限 — プレイリスト名と追加の順序を提供する権限を選択します。他の当局は依然としてメンバーシップの変更に貢献しています。
- 確認された削除はいずれかの権限から伝播します。何かを削除するには、欠席が 2 回連続する完全な読み取りに表示される必要があります。当局側の同時追加は削除よりも優先されます。
- ミラーには投票がありません。ミラーからトラックを削除すると、そのミラーが修復されます。 Spotify または Apple Music からトラックは削除されません。
- 安全な初回パス — すべての権限セットには独自のベースラインがあります。最初に成功したパスでは欠落しているトラックが追加される可能性がありますが、後のパスでベースラインが安定していることが証明されるまで、すべての削除は保持されます。
- **確認できない場合は処理しない** — 基準となるサービスのいずれかが未接続、読み取り不能、またはプレイリストを開いたり作成したりできない場合は、そのプレイリスト全体をスキップします。利用できる一部の基準サービスだけで処理を続けることはありません。

削除は明示的に有効にする必要があり、件数の上限も適用されます。ミラーから余分な曲を削除して基準となる曲の集合に合わせる場合は、ジョブで **曲の削除を同期** を有効にするか、画面を使わずに実行する場合は `MAX_REMOVALS` を設定してください。

<a id="bidirectional-n-way-sync"></a>

### 双方向 (N 方向) 同期

デフォルトでは、1 つのプロバイダーが信頼できる情報源となり、編集は一方向に行われます。 N-way モードでは、選択されたすべてのプロバイダーがピアになります。いずれかのプロバイダーでトラックを追加または削除すると、変更が他のプロバイダーに反映されます。

双方向同期はステートレスでは不可能であるため、各論理プレイリストの正規メンバーシップはクリーン パスごとにスナップショットが作成されます。各パスでは、すべてのプロバイダーをそのスナップショットと比較し、変更を結合し、全員を結果と照合します。

- エコーフリー — 伝播された追加はスナップショットの一部となるため、跳ね返されることはありません。
- 競合に対するアドウィン — 曲を失うことは、余分な曲を保持することよりも悪いです。
- **読み取り件数の急減を検知** — 一時的な API 障害などで、あるサービスの読み取り件数が基準より大幅に減った場合、その回はそのサービスをスキップします。1 回の不正な読み取りによって、大量の削除が他のサービスに波及するのを防ぎます。
- 一方向と同じ保護手段、つまりパスごとの `MAX_ADDS` / `MAX_REMOVALS` のキャップと純損失保護がすべての書き込み側に適用されます。
- **削除は明示的な有効化が必要** — `MAX_REMOVALS` の既定値は 0 です。あるサービスで曲が削除されたり、ライセンスの都合で配信停止になったりしても、他のサービスでは保持され、変更はログに記録されるだけです。削除を他のサービスにも反映するには、上限を設定するか、画面の **曲の削除を同期** を有効にしてください。

> 必ず最初にシミュレーションを行ってください。 `--execute` を指定せずに実行し (または UI でプレビューを使用し)、プランを読み取ります。何かが書き込まれる前に、すべてのプロバイダーに対して提案されたすべての追加/削除が出力されます。

<a id="liked-and-favorite-tracks"></a>

### 好きな曲とお気に入りの曲

同期の [プレイリスト] ステップで、ソース サービスの組み込みの「いいね！」コレクションを選択します。次に、SongMirror は、選択したすべての宛先のどこに移動するかを尋ねます。そのサービス独自のお気に入り/お気に入りコレクションに直接入れるか、提案された名前が編集できる新しいプレイリストに入れます。新しい選択は「いいね！」のみです。 [すべての通常のプレイリストも同期する] をオンにするか、両方を含める個々のプレイリストを選択します。

これは、Spotify お気に入りの曲、TIDAL/Qobuz/Deezer お気に入りのトラック、Amazon Music 私のお気に入り、Apple Music お気に入りの曲、およびYouTube Music で機能します音楽。同じ一方向、権威グループ、および N 方向の調整パスと安全キャップが適用されます。通常のプレイリストと同様に、**曲の削除を同期** を有効にするまで削除は既定で無効のままです。

TIDAL のサインイン済み Web プレーヤー許可は、`r_usr` と `w_usr` が含まれる場合、通常のプレイリストとネイティブのお気に入りトラックの両方を処理します。完全なサインイン トークン応答をキャプチャすると、SongMirror にリフレッシュ トークンと短期間の Bearer が与えられるため、セッションは自動的に更新されます。

これらの統合の一部はプロバイダーのファーストパーティ Web インターフェイスを使用しており、予告なく変更される可能性があります。 [実現可能性評価](../design/2026-09-01-liked-tracks-sync-feasibility.md) は、API と各プロバイダーの配布制約を記録します。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="playlist-metadata-backups"></a>

## 📦 プレイリストのメタデータのバックアップ

バックアップには 2 番目のプロバイダーや同期ジョブは必要ありません。

- [設定] → [プレイリスト バックアップ] で、上部にある [バックアップの追加] を使用して、接続されているアカウントを追加します。 JSON または XML を選択し、毎日、毎週などの頻度を選択します。カスタム間隔では数値と​​単位を使用します。 [バックアップを保持] では、保持プリセット、カスタム数、またはすべてのバックアップが提供されます。
- バックアップのデフォルトは `data/playlist_backups/<account-profile-id>/` (または Docker の `/data/playlist_backups/<account-profile-id>/`) です。組み込みのフォルダー ピッカーの [バックアップ フォルダー] をクリックするか、[パスを手動で入力] を選択します。カスタム フォルダーには、引き続きアカウントごとに個別のサブフォルダーが作成されます。デフォルトのバックアップ フォルダーを使用すると、デフォルトが復元されます。場所を変更すると、今後のバックアップに影響します。古いファイルはそのまま残ります。保存と最新のダウンロードは、選択した場所に適用されます。スケジュールを削除しても、保存されているファイルは削除されません。
- 「設定」→「ダウンロード」&「Jellyfin」→「ダウンロード」フォルダーでは、同じ組み込みピッカーと手動入力が使用されます。 Jellyfin ライブラリにアクセスできるフォルダーを選択します。ダウンロードは、[同期] タブでオプトインされた各同期のスケジュールに従います。ピッカーは、Docker マッピング (`/music`) を内部的に保持しながら、構成されたホスト パス (例: `F:\Torrent\Music`) を表示します。既存のダウンロード マウントは変更されません。追加のホスト フォルダーは、まず Docker バインド マウントとして共有する必要があります。アンマウントされたフォルダーを選択するとエラーが表示され、現在の設定は変更されません。

- 同じ設定カードには、次回の実行、保存されたスナップショット数、最後に成功したファイルと数、および最新の失敗が表示されます。今すぐバックアップを安全なオンデマンド実行のキューに入れます。最新のダウンロードは、永続化された最新のスナップショットを取得します。
- [プレイリスト] ページで、サービス カードの [エクスポート] を使用して、そのサービスからすべてのプレイリストを 1 つのバージョン付き JSON または XML ファイルにダウンロードします。
- プレイリストを開いて、そのプレイリストのみをエクスポートします。 Soundiiz オプションは [Soundiiz の文書化された JSON インポート形状](https://soundiiz.com/data/fileExamples/playlistExport.json) に続くため、ダウンロードしたトラックリストは、Soundiiz のプレイリストのインポート → ファイルからのフローを通じてアップロードできます。
- SongMirror JSON/XML は、プレイリストの順序と名前に加えて、プロバイダーのトラック/オカレンス ID、利用可能な ISRC、アーティスト、アルバム、アルバム トラックの位置、継続時間、追加された日付、アートワークのリンク、および利用できないエントリ マーカーを保持します。 ID のないカタログのゴーストは、消えるのではなくバックアップに残ります。ファイルには、Cookie、トークン、リクエスト ヘッダー、プレビュー、ストリーミング ファイル URL は含まれません。

手動エクスポートは、ブラウザーによって UI を実行しているデバイスにダウンロードされます。スケジュールされたエクスポートでは既存のアプリケーション データ ボリュームが使用されるため、2 番目のホスト パスやコンテナーのマウントは必要ありません。バックアップ読み取りは、プロバイダー クライアントに同時にアクセスするのではなく、同期と転送の後にキューを読み取ります。 `schema_version` フィールドにより、将来のリリースで古いスナップショットを曖昧にすることなくロスレス形式を進化させることができます。

<a id="built-in-folder-picker"></a>

### Built-in folder picker

フォルダー フィールドをクリックするか、[参照…] をクリックして、組み込みピッカーを開きます。場所、クリック可能なブレッドクラム、戻る、進む、および 1 つ上のフォルダーを使用して移動します。フォルダーをクリックして選択します。ダブルクリックするか、Enter キーを押すか、矢印を使用して開きます。検索は現在のフォルダーをフィルターします。フォルダー パスを入力すると、完全なアドレスが受け入れられます。フォルダーを選択すると下書きが更新されます。設定を保存するか、適用するスケジュールを設定します。キャンセルすると、ドラフトは変更されないままになります。デスクトップヘルパーや追加のプロセスは必要ありません。

新しいフォルダーは、現在開いている場所に名前付きのサブフォルダーを作成し、それを開きます。既存の項目が上書きされることはありません。名前の入力をキャンセルしても何も作成されません。作成後にピッカーをキャンセルすると、新しいフォルダーがディスク上に残ります。保存されたバックアップまたはダウンロードの場所は、選択して保存した後にのみ変更されます。 Docker では、ピッカーはどのパスが共有されているかを説明し、コンテナー パスと、使用可能な場合はその構成済みコンピューター パスの両方を表示します。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="local-download-mirror-jellyfin"></a>

## 💿 ローカル ダウンロード ミラー (Jellyfin)

[spotDL](https://github.com/spotDL/spotify-downloader) 経由で、同期された各プレイリストのオフライン オーディオ コピーを、プレイリストごとに 1 フォルダーずつ保存します。同期は真のミラーリングです。新しいトラックはダウンロードされ、削除されたトラックはローカルに削除されます。レイアウトは Jellyfin 対応です — ダウンロード ディレクトリで Jellyfin 音楽ライブラリをポイントすると、トラックとプレイリストの両方が表示され、パスごとに更新されます。

```text
<DOWNLOAD_DIR>/
  <Playlist>/
    <Playlist>.m3u8          # auto-(re)generated; Jellyfin imports it as a playlist
    cover.jpg                # the source playlist cover, highest resolution
    <AlbumArtist>/
      <Album>/
        Artists - Title.mp3  # tagged + cover art embedded
```

`DOWNLOAD_DIR` を設定し、spotDL + ffmpeg をインストールして有効にします。

```bash
uv tool install spotdl       # isolated CLI; or: pipx install spotdl
# ffmpeg required: winget install ffmpeg   (or: spotdl --download-ffmpeg)
```

- 増分 — 最初の完全なダウンロードの後、新しく追加されたトラックのみがフェッチされます。削除されたトラック (および空になったアルバム フォルダー) は削除されます。中断された走行は次のパスで継続されます。
- 新しい順 `.m3u8` — 日付を追加した順に書かれ、新しいものが一番上になります (反転するには `LOCAL_MIRROR_ORDER=oldest` を設定します)。 `uv run main.py --refresh-local` を使用して、既存のファイルからカバー/タグ/mtimes を再構築します。
- Jellyfin のプレイリスト カバー — Jellyfin は m3u の隣のカバー ファイルを無視するため、`JELLYFIN_URL` + `JELLYFIN_API_KEY` を設定すると、各パスが Jellyfin API を介して実際のプレイリスト カバーをアップロードします。
- オーディオ品質 — ソースは YouTube なので、YT Music Premium Cookie がなければ、上限は ~128 ～ 160 kbps です。 `LOCAL_MIRROR_FORMAT=opus` は、mp3 再エンコードせずに YouTube のネイティブ ストリームを保持します。 Premium Cookie (`LOCAL_MIRROR_COOKIE_FILE`) は 256 kbps AAC のロックを解除します。 `flac` を選択すると出力コンテナが変更されますが、非可逆ソースを可逆オーディオに変換することはできません。

Monochrome の現在の FLAC パスは、安定したプロバイダー承認のファイル エクスポート API ではなく、ブラウザー ゲートの使い捨て再生リソースを使用するため、SongMirror はそれを自動化しません。ローカル ミラーは、自分が所有するコンテンツ、またはコピーが許可されているコンテンツに対してのみ使用してください。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="connecting-each-service"></a>

## 🔌 各サービスを接続する

Web アプリでは、[アカウント] ページに各サービスが表示され、貼り付ける正確な値が表示されます。サードパーティを介してプロキシされることはありません。

<a id="credential-renewal"></a>

### 資格の更新

SongMirror は、別個のトークン更新タイマーを使用するのではなく、ジャストインタイムで資格情報を更新します。すべての手動またはスケジュールされた同期パスは、最初の要求の前に (または認証拒否後に 1 回)、使用するコネクタを検証し、サポートされているアクセス トークンを更新します。有効期間の短いアクセス トークンがパス間で期限切れになるのは通常のことです。重要なのは耐久性のある更新トークンまたは更新 Cookie です。 「アカウント」ページは、ロード時またはフォーカスの再取得時にステータスを検証しますが、バックグラウンドでのセッションのメンテナンスではありません。有効な同期スケジュールは次のとおりです。

|サービス |更新動作 |
| --- | --- |
| Spotify |デフォルトの接続では、保存されている `sp_dc` Cookie から Web プレーヤーのアクセス トークンがオンデマンドで生成され、`401` の後に新しいトークンを使用して再試行されます。基礎となるサインイン セッションは引き続き取り消すことができます。従来の開発者アプリ OAuth は、既存のインストールに対して引き続きサポートされます。 |
| TIDAL |インポートされた Web プレーヤーのアクセス トークンは、サインイン応答の更新トークンを使用して、`auth.tidal.com` まで自動的に更新されます。 SongMirror は、応答で既存のリフレッシュ トークンが省略された場合はそれを保持し、TIDAL がトークンを返した場合はローテーションされたトークンを保持します。ログアウトまたは取り消しには、引き続き新しいキャプチャが必要です。 |
| Qobuz |貼り付けられた `X-User-Auth-Token` は、Qobuz が拒否するまで使用され、拒否された場合は再度キャプチャする必要があります。 |
| Deezer |有効期間の短いパイプ JWT は、使用前と `401/403` の後に 1 回、保存された `refresh-token` から自動的に更新されます。回転された更新状態は保持されます。 |
| Amazon Music | Web アクセス トークンは、キャプチャされたブラウザ ユーザー エージェント、リファラー、およびホワイトリストに登録された Cookie を使用して、`/pandaToken` まで更新されます。現在の `POST config.json?skipToken=false` フローは、必要に応じてデバイス コンテキストをブートストラップし、ローテーションされた Cookie は永続化されます。ログアウト、セキュリティの変更、またはサーバー側の取り消しには、引き続き新しいキャプチャが必要です。 |
| Apple Music |貼り付けられた Bearer と Media-User-Token は SongMirror で更新できず、拒否後に再度キャプチャする必要があります。 |
| YouTube Music | Data API OAuth は有効期限が切れてから 60 秒以内に自動的に更新されます。ブラウザ モードでは、同期ターゲットが構築されるたびに Google の Cookie ローテーションが試行されます。すでに期限切れになっているブラウザ セッションは再度エクスポートする必要があります。 |
| Jellyfin | API キーにはアクセス トークンの更新サイクルがありません。取り消されたり削除された場合にのみ置き換えてください。 |

<a id="spotify"></a>

### Spotify

1. Sign in at <https://open.spotify.com>.
2. ブラウザDevTools (`F12`) → アプリケーション (Chrome/Edge) またはストレージ (Firefox) → Cookie → `https://open.spotify.com` を開きます。
3. `sp_dc` Cookie の値をコピーし、「アカウント」→「Spotify」に貼り付けます。

この 1 つのサインイン Web セッションは、ライブラリの参照、プレイリストの読み取りと書き込み、およびカタログの検索を処理します。 Spotify 開発者アプリ、API キー、または Premium アカウントは必要ありません。 `sp_dc` をパスワードのように扱います。SongMirror はそれをプライベート データ ディレクトリに保存しますが、統合では Spotify の内部 Web プレーヤー操作が使用されるため、Spotify が変更した場合はメンテナンスが必要になる可能性があります。既存の開発者アプリ OAuth 認証情報は互換性のあるフォールバックのままです。

<a id="tidal"></a>

### TIDAL

1. [TIDALのウェブプレーヤー](https://listen.tidal.com) を開き、DevTools → ネットワークを開き、ログの保存を有効にします。
2. サインアウトして再度サインインし、ネットワーク リストを `oauth2/token` でフィルターします。
3. 成功した `auth.tidal.com/v1/oauth2/token` リクエストを選択します。ペイロード (Chrome/Edge) またはリクエスト (Firefox) で、`client_id` フォーム値を SongMirror の Web プレーヤー クライアント ID フィールドにコピーします。
4. リクエストの「応答」タブを開き、その完全な JSON を Web プレーヤー トークンの応答にコピーします。 `access_token` と `refresh_token` の両方を含める必要があります。
5. Connect. SongMirror は、ただちに更新許可を実行し、そのクライアント ID が更新できない場合は成功の報告を拒否します。

OAuth クライアント ID はリクエストのメタデータであり、TIDAL のアクセス トークン内の数値 `cid` クレームではありません。 SongMirror は、アクセス トークン、リフレッシュ トークン、クライアント ID、スコープ、有効期限、カタログの国のみを抽出します。無関係な応答データは破棄されます。有効期限が切れる直前と、`https://auth.tidal.com/v1/oauth2/token` による認証拒否後に 1 回更新され、リフレッシュ トークンのローテーションが維持されます。古い OpenAPI リクエスト ヘッダー ペーストには互換性が残っていますが、リフレッシュ トークンが含まれていないため、有効期限が切れた後に再度ペーストする必要があります。カタログ メタデータとサインイン ユーザーのプレイリストのみが使用されます。再生アセットはこの統合の範囲外にあります。

<a id="qobuz"></a>

### Qobuz

<https://play.qobuz.com> にサインインし、DevTools → **ネットワーク**を開いて `api.json/0.2` で絞り込みます。認証済みの `album/story` など、`X-App-Id` と `X-User-Auth-Token` を含むリクエストを選びます。リクエストヘッダーをコピーするか、cURL としてコピーし、ウィザードに貼り付けてください。SongMirror はこの 2 つの値だけを保存し、ウェブプレーヤーと同じヘッダー方式で送信します。Cookie と無関係なブラウザのメタデータは破棄します。ビジネス API の承認やユーザー ID は不要です。既存のパートナー認証情報も、環境変数を使う代替手段として引き続き利用できます。

アダプターはカタログ検索とプレイリストのエンドポイントのみを使用し、ストリームやファイルの URL は要求しません。

<a id="deezer"></a>

### Deezer

<https://www.deezer.com> でサインインし、DevTools → ネットワークを開き、ページをリロードします。 `auth.deezer.com/login/renew` をフィルターし、そのリクエストのヘッダーをコピー (または cURL としてコピー) して、更新フィールドに貼り付けます。 Firefox は代わりに、リクエスト Cookie をセミコロンで区切られた裸のブロックとしてコピーする場合があります。その形も受け入れられます。 SongMirror は専用の `refresh-token` Cookie のみを保持し、それを使用して Deezer の短期間のパイプ JWT を自動的に更新します。現在の `pipe.deezer.com/api` リクエストを即時ブートストラップとして貼り付けることもできますが、更新が設定されている場合は必須ではありません。プレイリストの追加と削除はどちらも、更新可能な Pipe セッションを使用します。 `arl` Cookie は必要ありません。既存の開発者 OAuth トークンは、互換性のある環境のフォールバックとして残ります。

<a id="amazon-music"></a>

### Amazon Music

デフォルトのコネクタには開発者の承認は必要ありません。これは、Amazon Music Web プレーヤーと同じ認証済みの GraphQL およびトークン更新ルートを使用します。

1. <https://music.amazon.com> でサインインし、DevTools → ネットワークを開きます。
2. ページをリロードし、`config.json` でフィルターし、サインイン要求を選択します。 (`pandaToken` が表示されている場合も機能しますが、必須ではありません。)
3. [リクエスト ヘッダーをコピー] または [cURL としてコピー] を選択し、それを更新フィールドに貼り付けます。 SongMirror が同じブラウザー コンテキストを再生できるように、完全な `User-Agent`、`Referer`、および `Cookie` ヘッダーを保持します。
4. 必要に応じて、サインインした `config.json` 応答をブートストラップ フィールドにコピーします。 SongMirror は通常、更新セッションを使用してそのデバイス コンテキストを取得できます。

SongMirror は同じ `AmznMusic` 認証値をローカルで生成し、有効期限の直前、または認証拒否の後に 1 回、`music.amazon.com/pandaToken` 経由で更新します。接続時にデバイス情報が必要な場合は、現在のブラウザと同じ形式の設定リクエストを使います。アクセストークンは必ず `/pandaToken` で発行し、Amazon が Music の更新用 Cookie を失効させている場合は接続を拒否します。保存するのはブラウザのユーザーエージェント、言語、Music の参照元、明示的に許可した Amazon の認証・セッション Cookie、および限定的な Music クライアントのデバイス情報だけです。分析、実験、AWS コンソール、CSRF などの無関係なブラウザデータは破棄します。保存する Cookie も機密情報なので、SongMirror は LAN 内で非公開にしてください。ログアウト、パスワードやセキュリティの変更、または Amazon 側の失効処理によって、再取得が必要になることがあります。

これはサポートされていないファーストパーティ Web クライアント インターフェイスであり、Amazon は予告なく変更することがあります。文書化された [Amazon Music ウェブ API](https://developer.amazon.com/docs/music/API_web_overview.html) はまだクローズドベータ版です。承認されたパートナーの認証情報は、環境変数を通じて構成された場合、オプションのフォールバックのままになります。

<a id="apple-music"></a>

### Apple Music

Apple 開発者アカウントは必要ありません。`music.apple.com` の 2 つのヘッダーで十分です。 <https://music.apple.com> を開いてサインインし、DevTools → ネットワークを開き、曲を再生し、`amp-api.music.apple.com` でフィルターし、リクエストのヘッダーから次をコピーします。

- `authorization: Bearer eyJ...` → Bearer トークン (`eyJ...` 部分、`Bearer ` なし)
- `media-user-token: ...` → ユーザートークン（完全な値）

接続ウィザードを使用すると、生のヘッダーを貼り付け、値を解析できます。先月のトークン。有効期限が切れたら、アカウント ページに再度貼り付けます。

アクティブな Apple Music サブスクリプションのない Apple ID は、引き続きカタログ専用モードで接続できます。このモードでは、パブリック Apple Music プレイリスト リンクを転送に貼り付けて、接続されている別のサービスにコピーします。 Apple ライブラリの参照、スケジュールされた同期、および転送先として Apple Music を使用するには、引き続き有料の CloudLibrary 権限が必要です。 SongMirror は、有効なカタログ資格情報を期限切れとして扱うのではなく、それらの操作を利用できないものとして表示します。

<a id="youtube-music"></a>

### YouTube Music

公式 [YouTube Data API v3](https://developers.google.com/youtube/v3) と通信します。その OAuth リフレッシュ トークンは耐久性があり、再起動しても存続します。

1. [Google Cloud コンソール](https://console.cloud.google.com)でプロジェクトを作成し、**YouTube Data API v3** を有効にして、種類が **テレビと入力機能が限られたデバイス**の OAuth クライアントを作成します。
2. OAuth 同意画面で、公開ステータス → 運用中 (「テスト」のままにすると、7 日後にトークンの有効期限が切れます) を設定します。
3. アプリで、クライアント ID とシークレットを貼り付け、画面上のデバイス コードを完成させます。

> クォータ: Data API では、1 日あたり 10,000 ユニットが許可されます (検索のコストは 100、追加/削除のコストは 50)。定常状態の維持費は安価です。初回のバックログが大きい場合は、上限に達し、翌日再開される可能性があります。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="headless-cli"></a>

## 🖥️ グラフィカルインターフェイス CLI なし

`.env` + cron / Task Scheduler を優先しますか?同じエンジンはグラフィカル インターフェイスなしで実行されます。

```bash
uv sync
cp .env.example .env            # fill in credentials
uv run main.py                  # dry run — prints every add/remove it *would* do
uv run main.py --execute        # apply for real
```

便利なフラグ:

```bash
uv run main.py --execute --playlists "Aurora,Chill"   # only these pairs
uv run main.py --execute --loop --interval 15m        # run forever
uv run main.py --execute --max-removals 100           # one-off larger cleanup
uv run main.py --execute --sync-mode group --sync-source spotify \
  --authorities spotify,apple --providers spotify,apple,tidal,ytmusic
```

主要な環境変数（`.env.example` を参照）は、使用する各サービスの認証情報と、`PLAYLISTS`、`SYNC_INTERVAL`、`MAX_ADDS` / `MAX_REMOVALS`、`DOWNLOAD_DIR`、`SYNC_MODE`、`SYNC_SOURCE`、`SYNC_AUTHORITIES`、`PROVIDERS` です。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="safety-rails"></a>

## 🛡️ 安全対策

削除は破壊的であるため、保護されています。

- シミュレーションがデフォルトです。`--execute` (または UI のリアル同期アクション) がなければ何も変わりません。
- 同期先には曲があるプレイリストについて、同期元から 0 曲という結果が返された場合、その回の同期では削除を行いません（一時的な API 障害でプレイリストが空になるのを防ぎます）。
- **削除は既定で無効** — `MAX_REMOVALS=0` はすべての削除を保留し、ログに記録するだけで実行しません。そのため、あるプラットフォームでライセンスの都合により曲が配信停止になっても、他のプラットフォームで連鎖的に削除されることはありません。同期ごとに **曲の削除を同期** を有効にするか、`MAX_REMOVALS` を設定してください。有効化後も、1 回の実行で削除予定の件数が上限を超えた場合は、すべての削除をスキップしてログに記録します。
- `MAX_ADDS` は、クロノロジーの修復を含む、同期パス内のタイムスタンプを生成するすべての書き込みを制限します。古い復元された一致で、上限よりも大きなサフィックス リプレイが必要な場合、SongMirror は、一致を最新に見せたり、巨大なプロバイダー バーストを引き起こしたりするのではなく、次のパスに延期します。 1 回限りの転送には次のパスがないため、延期されることはありません。転送の「最近追加した順序を保持」をオンにしない限り、要求されたすべてのトラックがコピーされ、ソースの順序で追加されます。これにより、修復にかかる費用はすべて消費されます。
- クロノロジー修復では、オリジナルを破棄する前に複製コピーをステージングします。曲のすべてのコピーを削除するサービスでは、キーパー カウントが正しくなければならないため、Apple Music はステージングされたコピーが表示されるまで再読み取りを行い、自身の書き込みをまだ追跡している読み取りに対しては何もリタイアすることを拒否します。 Deezer は修復を完全にスキップし、常に追加します。位置挿入もありません。そのため、表現できないオーダーを再実行しても、宛先にとってリスクを負う価値はありません。転送フォームにはその注文スイッチがグレー表示され、その理由が記載されています。
- ネットロス保護 — ソース トラックに似ているが、そのサービス上で一致しないターゲット側トラックは、削除されずに保持されます。
- プロバイダーの認証に失敗すると、そのプロバイダーのパスは直ちに中止されます。期限切れのトークンは部分的に削除されません。
- マージ ジョブは、宛先から削除する前に、すべての構成ソースの読み取りを完了する必要があります。部分的または失敗したソース スナップショットがあると、強制的に追加専用動作に移行します。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="caching-song-archive"></a>

## 🗃️ キャッシュと曲のアーカイブ

解決可能なものはすべてキャッシュされるため、定常状態のパスはほぼ瞬時に行われます。サービスごとの解決キャッシュ (ISRC + ミスを含む検索)、`snapshot_id` キー付きトラックリスト キャッシュ、SQLite の正確な識別子リンク、およびペアごとのスナップショット スキップ (`unchanged since last clean sync`)。

また、すべてのパスでは、表示されるすべてのトラックのメタデータが `song_cache.db` にアーカイブされます。この SQLite ファイルは、増加するだけです。削除されたトラックは、名前、アーティスト、アルバム、再生時間、ISRC、生のスナップショット JSON、および最初/最後に表示されたタイムスタンプとともにアーカイブされます。

```bash
sqlite3 song_cache.db "SELECT name, artist, album, first_seen FROM songs ORDER BY first_seen DESC LIMIT 20"
```

<a id="resolve-mappings"></a>

### マッピングを解決する

各サービスは独自の解決キャッシュを保持し、正規化された `title|artist` キーを、一致したカタログ ID にマッピングします。
that service.一致は永久に再利用されるため、「一致なし」の結果も再利用され、トラックが失敗する原因となります。
一度一致すると、その後のパスでは一致しなくなります。

Web UI の [マッピング] ページは、サービスごとにこれらのキャッシュを直接公開します。

- タイトル、アーティスト、または解決された ID でキャッシュ全体を検索します
- 手動で設定したエントリ (転送競合エディタで選択した一致)、または一致しないエントリにフィルタします。
- 正しいトラックのリンクを貼り付けて間違った ID を修正するか、次のパスで再度検索できるようにマッピングを削除します。
- 1 回のアクションでサービスのすべての「一致しない」エントリをクリアするため、失敗した検索のバッチが再度試行されます。

後でクリアされたミスが解決された場合、単純にそれを追加すると、古い曲が最新のように表示されます。プレイリスト用
宛先では、SongMirror は代わりに、その曲と既存の新しいサフィックスを古いものから新しいものへ再生し、削除します。
古いコピー。プロバイダーはクライアントが元のタイムスタンプを復元することを許可していませんが、これにより相対的なタイムスタンプが保持されます。
最近追加された注文。ネイティブの「いいね！」/お気に入りのコレクションはメンバーシップのみであり、再生されることはありません。

パスはメモリ内にキャッシュを保持しているため、同期の実行中は編集が拒否され、明確なメッセージが表示されます。
期間全体にわたって実行され、完了時にそれらが上書きされます。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="project-layout"></a>

## 🧱 プロジェクトのレイアウト

CLI エントリ: `uv run main.py` (薄いシム) または `python -m songmirror`。ウェブエントリ: `songmirror.web:app`。

```text
songmirror/
  engine/       # provider-agnostic sync core (no web deps): runner, matching, targets/, spotify, downloads, archive
  services/     # stateful services over the engine: accounts/ connectors, syncs, sync_service, transfers, playlists, settings
  web/          # FastAPI app: thin HTTP/SSE over services/ (routers/)
frontend/       # React + Vite SPA (built and served by the API in production)
```

別のサービスの追加: サブクラス `MirrorTarget`、~8 個のメソッドを実装し、そのビルダーを `engine/targets` ' `_REGISTRY` に追加し、そのクラスを `_CLASSES` に追加し、`services/accounts` の下に一致する `Connector` を追加します。すべての調整 (差分、順序付け、安全対策、ロギング、スナップショット スキップ) が継承されます。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="troubleshooting"></a>

## 🩺 トラブルシューティング

- `Missing required environment variable` — `.env` (CLI) を入力するか、UI でサービスに接続します。
- TIDAL レポート `Expired` — サインアウトして、`listen.tidal.com` に戻り、`oauth2/token` リクエストペイロードの `client_id` とその完全なレスポンス JSON の両方をアカウントに貼り付けます。コピーされた OpenAPI リクエストには有効期間が短い Bearer のみが含まれており、更新できません。
- TIDAL レポート HTTP 429 — これは一時的なレート制限であり、期限切れのサインインではありません。 SongMirror は、プロバイダーの再試行遅延を尊重し、API を繰り返し調査する代わりに、アカウントの健全性チェックをキャッシュします。
- Qobuz または Apple レポート `Expired` / `401` / `403` — これらの貼り付けられたセッションには更新可能なシークレットがありません。アカウントで新しいサインイン要求またはトークンをキャプチャします。
- TIDAL は、トークンにいいねトラック アクセスがないことを示しています。`r_usr` と `w_usr` を含む新しいサインイン Web プレーヤー トークンの応答をキャプチャします。
- Deezer 更新は失敗します — 新しい `auth.deezer.com/login/renew` リクエスト (またはその `refresh-token` Cookie) をキャプチャします。現在のパイプ Bearer だけでは一時的なブートストラップにすぎません。
- Amazon Music 更新が失敗する — 完全な `User-Agent`、`Referer`、および `Cookie` ヘッダーを含む、新しくサインインした `POST /config.json?skipToken=false` リクエストをキャプチャします。応答 JSON はオプションです。
- YouTube Music ブラウザ モードが期限切れになります — 新しいブラウザ リクエスト ヘッダーをエクスポートします。最も耐久性のある無人セットアップを行うには、運用中の同意画面で Data API OAuth を使用します。
- Spotify は期限切れを報告します — `open.spotify.com` で再度サインインし、新しい `sp_dc` Cookie をアカウントに貼り付けます。
- プレイリストが同期していません。プレイリストが同期のプレイリスト スコープ内にあり、ソース上に存在することを確認してください (ターゲットは実際のパスで自動作成されます)。

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<a id="license"></a>

## 📄ライセンス

著作権 © 2026 [Ahnaf An Nafee](https://github.com/ahnafnafee).<br/>
このプロジェクトは [MIT](../../LICENSE) ライセンスされています。

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
