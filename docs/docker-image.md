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
docker compose pull
docker compose up -d
docker compose ps
```

Open `http://localhost:8888`. Configuration entered in the browser is stored in
`./data`; downloaded music is stored in `./downloads` unless `DOWNLOAD_DIR` is
set in `.env`. Back up those directories before upgrades. The web UI has no
login, so keep port 8888 on a trusted LAN and do not expose it directly to the
internet.

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
