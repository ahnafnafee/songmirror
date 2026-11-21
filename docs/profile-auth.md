# Protect the web app with owner sign-in

SongMirror can require one owner username and password for a self-hosted instance. Signing in grants access to the instance's existing playlists, music service accounts, sync jobs, and settings.

## Set up in the web app

On an instance without owner credentials, the web server logs a one-time owner setup code when it starts. For Docker Compose, find it with `docker compose logs web`. For a native installation, read the Uvicorn startup log. Use the most recent code and keep it private.

Open **Settings → General → Owner sign-in** and select **Set up sign-in**. Enter the code, a username, and a unique password of at least 15 characters, then select **Enable sign-in**. SongMirror signs in this browser and immediately requires sign-in for other browsers. Complete setup before sharing access to your instance.

SongMirror stores the username and a salted password hash in `owner-auth/credentials.json` in its data directory (`./data` in the default Compose setup). Keep that directory private and mounted persistently. Use **Sign out** in the sidebar or mobile menu when you finish.

## Configure through the environment

For unattended deployments, set both values in the deployment's `.env` or the web process's environment. Keep the file private.

```dotenv
SONGMIRROR_AUTH_USERNAME=owner
SONGMIRROR_AUTH_PASSWORD=
```

Use a password of at least 15 characters. With Docker Compose, run `docker compose up -d --force-recreate web` after editing `.env`. For a native installation, restart Uvicorn. The environment credentials take precedence over a profile saved through the web app. A partially configured pair prevents startup.

## Remote access and recovery

Use an HTTPS reverse proxy for remote access and keep the backend HTTP port private. Have the proxy forward the original HTTPS scheme via `X-Forwarded-Proto` and configure Uvicorn to trust only that proxy. SongMirror sets a Secure session cookie on HTTPS. For provider OAuth with owner sign-in enabled, open the app at the callback's exact origin and sign in there. For a loopback callback at `127.0.0.1`, open the app at that address using the same port.

Sessions last up to 24 hours and are cleared when the web process restarts. Run the web app with a single worker so all requests use the same session store.

If you lose the password, set a new pair of environment credentials and restart the web app. To set up a new password through the UI or return to an open instance, take the web app offline, move the `owner-auth` directory to a private backup location, remove any environment credentials, and restart it on a trusted network.

For API clients, send the username and password as JSON to `POST /api/auth/login`, keep the returned session cookie, and send `X-SongMirror-Request: 1` on requests that change state, including sign-in and sign-out. Signed-in clients can read `/openapi.json`. SongMirror serves the schema directly to keep third-party documentation scripts off the app origin, including before setup. `GET /health` stays available to health checks.
