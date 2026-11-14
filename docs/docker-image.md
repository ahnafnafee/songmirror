# SongMirror container image

The official image is published to `ghcr.io/ahnafnafee/songmirror` for
`linux/amd64` and `linux/arm64`. The package is public, so normal pulls do not
require a GitHub login.

## Recommended: Docker Compose

The repository's Compose file declares every persistent token, cache, database,
and download path. Use it for a durable installation:

```bash
git clone https://github.com/ahnafnafee/songmirror.git
cd songmirror
mkdir -p data downloads
docker compose pull
docker compose up -d
docker compose ps
```

Open `http://localhost:8888`. Configuration entered in the browser is stored in
`./data`; downloaded music is stored in `./downloads` unless `DOWNLOAD_DIR` is
set in `.env`. Back up those directories before upgrades. The web UI has no
login. Compose publishes port 8888 on loopback by default. Set
`SONGMIRROR_BIND_ADDRESS=0.0.0.0` in `.env` only when every client on that LAN is
trusted, or place the service behind an authenticated reverse proxy. Do not
expose the unauthenticated API directly to the internet.

### Non-root storage and upgrades

The image runs as UID/GID 1000 and keeps its application and downloader under
root-owned, read-only locations. Compose drops capabilities, prevents privilege
escalation, makes the root filesystem read-only and provides a temporary cache.
Create the two bind directories as your ordinary host user before the first
start. On Linux, set `SONGMIRROR_UID` and `SONGMIRROR_GID` to that user's numeric
IDs if they differ from 1000. Additional music mounts must be writable by the
selected identity. The image does not change ownership of music files.

Older images may have created root-owned, private files under `./data`. Back up
that directory, stop the old service, then repair only the application-data
mount before starting the new image:

```bash
docker compose stop web
docker compose run --rm --no-deps --user 0:0 \
  --cap-add CHOWN --cap-add FOWNER --cap-add DAC_OVERRIDE --entrypoint sh web -c \
  'chown -R "$SONGMIRROR_UID:$SONGMIRROR_GID" /data'
docker compose up -d
```

This is a one-time owner migration. It does not repair permissions on a music
mount; choose its owner/group or ACL deliberately on the host. On Windows,
application credential storage receives a protected ACL for the running user,
SYSTEM and Administrators, including existing children. POSIX storage remains
owner-only. These permissions protect other local users; they do not encrypt
credentials or protect them from the running service account.

### Allowed folders and settings

Folder browsing, directory creation, downloads and backup destinations share one
startup-controlled policy. In Compose the defaults are `/data` and `/music`.
To use another bind mount, declare it in Compose and include its container path
in `SONGMIRROR_FOLDER_ROOTS`, a JSON array such as `["/data","/music","/backups"]`.
Use forward slashes for native Windows roots, for example
`["D:/Music","F:/Playlist Backups"]`. Native defaults include app data, the
adjacent downloads directory, the user's Music directory and paths explicitly
provided by the startup environment. A saved web setting does not expand the
allowed roots. Symlinks are resolved before admission, and parent navigation
stays inside a permitted root.

After upgrading, declare any previously selected download or backup directory
that falls outside these roots. A denied stored download directory fails its
job before execution; a denied backup folder stays visible and can be changed
in Settings. Empty download paths still disable downloads.

The settings API accepts only supported editable fields. Provider connection
routes accept only their declared fields and supported authentication choices.
Executable overrides such as `SPOTDL_CMD`, storage-file paths, local-library
paths and host/origin policy belong in the trusted startup environment or local
`.env`, rather than `settings.json`. Unsupported legacy JSON values remain
available for operator review but are not returned or projected into the
managed environment. The managed `app.env` is regenerated before use and loads
values literally, without variable interpolation. Restart the server after
upgrading; do not reuse an already modified process environment from the old
version.

Builds pin base-image digests, Python 3.13.16, pnpm 11.5.1 and spotDL 4.6.0.
Update those pins deliberately when applying future security updates. Local
`.env` files and runtime credentials are excluded from the build context.

### Browser and network protections

SongMirror accepts loopback hosts, literal private LAN addresses and the server's
hostname by default. For another DNS name, set `SONGMIRROR_ALLOWED_HOSTS` to a
comma-separated list of exact hostnames, or set `SONGMIRROR_PUBLIC_URL` to the
browser-visible HTTP(S) URL. Wildcard hosts are not supported. Reverse proxies
must preserve the intended Host and Origin; the configured public URL also
supports TLS termination and a path prefix. These checks complement the trusted
LAN deployment and do not add application login.

Browser mutations reject foreign or null origins and cross-site request metadata.
Command-line API clients without browser-origin headers remain supported. Import
requests are limited before multipart parsing, with a 10 MiB file limit, a small
multipart envelope allowance and a 10,000-track parsing limit.

Redirect authorization first visits a short-lived start page on the callback
origin. This binds its cookie to the correct browser even when the UI uses
`localhost` and the provider callback uses `127.0.0.1`. Allow cookies for that
origin and complete authorization in the same browser within ten minutes.
Restarting the server, changing account configuration or disconnecting invalidates
pending attempts; start again from Accounts when an attempt expires.

Artwork downloads accept public destinations and explicitly configured private
media origins, validate every redirect, pin connections to checked addresses and
limit response size and time. The selected Subsonic/Jellyfin server origin is
trusted for its own artwork. If artwork comes from another private origin, add
its exact HTTP(S) origin to `SONGMIRROR_MEDIA_ORIGINS`; no provider credentials are
attached to artwork requests. A rejected cover does not stop music copying.

To follow the newest default-branch image:

```bash
docker compose up -d --pull always
docker compose logs -f
```

To build the checked-out source instead of pulling GHCR, leave
`SONGMIRROR_IMAGE` unset and run:

```bash
docker compose up -d --build
```

## Tags and immutable digests

The publisher creates these references:

| Reference | Meaning |
| --- | --- |
| `latest` | Current default-branch build; also refreshed by the weekly rebuild. |
| `sha-<short-commit>` | Build associated with a Git commit. A scheduled rebuild can update this tag when upstream base images change. |
| `1.2.3` | Image built from Git tag `v1.2.3`. |
| `1.2` and `1` | Moving aliases for the newest matching release. |
| `@sha256:<digest>` | Exact image bytes; this is the immutable form. |

Inspect a tag to obtain the multi-platform digest:

```bash
docker buildx imagetools inspect ghcr.io/ahnafnafee/songmirror:latest
```

For repeatable deployments, put the digest from that output in `.env`:

```dotenv
SONGMIRROR_IMAGE=ghcr.io/ahnafnafee/songmirror@sha256:REPLACE_WITH_DIGEST
```

Then recreate the service:

```bash
docker compose up -d --pull always --force-recreate
```

`SONGMIRROR_IMAGE` is consumed by Compose. Do not set it to a digest when using
`docker compose ... --build`, because a local build needs a taggable image name.

## Pull or inspect the image directly

You can pull the image without Compose:

```bash
docker pull ghcr.io/ahnafnafee/songmirror:latest
docker image inspect ghcr.io/ahnafnafee/songmirror:latest
```

A disposable smoke test is also possible:

```bash
docker run --rm -p 8888:8080 ghcr.io/ahnafnafee/songmirror:latest
```

That command intentionally has no persistent volumes. Use the Compose setup for
a real installation so account tokens, provider caches, the song database, and
downloads survive container replacement.

## Verify provenance

Published images receive a GitHub artifact attestation bound to the exact pushed
digest. With GitHub CLI installed and authenticated to GHCR, verify it with:

```bash
gh attestation verify \
  oci://ghcr.io/ahnafnafee/songmirror:latest \
  --repo ahnafnafee/songmirror \
  --signer-workflow ahnafnafee/songmirror/.github/workflows/docker-publish.yml
```

Verification proves which repository workflow attested the image. For a stable
deployment reference, still use the verified digest rather than a moving tag.

## Roll back

Replace `SONGMIRROR_IMAGE` in `.env` with a previously working digest, then run:

```bash
docker compose up -d --pull always --force-recreate
docker compose logs -f
```

Rolling back the container does not roll back `./data`. Make a data backup before
upgrading when application-level storage compatibility matters.

## Cache-isolation policy

Release builds intentionally disable all persistent caches exposed by the Docker
publishing toolchain:

- the QEMU setup action does not cache its binfmt image;
- the Buildx setup action does not cache its binary or retain builder state; and
- BuildKit runs with `no-cache` and has no cache import or export destination.

This prevents cross-run cache state from becoming an input to a published image.
It deliberately makes releases slower. It does not make moving tags immutable or
remove external registry and dependency trust, which is why digest pinning and
attestation verification remain useful.
