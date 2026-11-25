# SongMirror website

The public site at [songmirror.ahnafnafee.dev](https://songmirror.ahnafnafee.dev/) uses Cloudflare Workers Static Assets. Its Docker commands come from the main README, and its language links come from the app's locale registry.

From the repository root, install the frontend dependencies to get the pinned Archivo font and build the static site.

```sh
pnpm -C frontend install --frozen-lockfile
node site/build.mjs
cd site
pnpm dlx wrangler@4.167.0 dev
```

To publish a new build, run `pnpm run deploy` from `site/` using the Cloudflare account that owns the domain. This rebuilds the site, publishes it, verifies the live sitemap and IndexNow key, and notifies IndexNow. If publication succeeds but notification fails, use `pnpm run notify:search` to retry. Pass canonical page URLs to submit only the pages that changed.

The site advertises its sitemap to Google in `robots.txt`. Submit it in the `ahnafnafee.dev` Search Console domain property and use URL Inspection to request indexing after significant updates.

The site reuses SongMirror’s application icons and the existing Amazon Music artwork. Run `pnpm -C promo build:assets` from the repository root to capture the product footage and regenerate the MP4, GIF, and poster. The site build generates captions and video metadata from `promo/cues.json`.
