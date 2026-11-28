# SongMirror releases

Each push to `main`, including a pull request merge, can publish a GitHub release after the Python and frontend CI jobs pass for that commit. Tags use `vMAJOR.MINOR.PATCH`. The first automated release uses the project version in `pyproject.toml` at the commit that introduces the release generator.

Each later mainline commit advances the version once. A breaking change raises the major version. A `feat` commit raises the minor version. Other changes raise the patch version. A merge uses the highest bump among its PR title and the commits it introduces. Failed checks and pushes containing several commits can cause gaps in published versions. Retries keep their original tag.

To receive release notifications, open the repository on GitHub and choose **Watch → Custom → Releases**. You can also follow the [releases feed](https://github.com/ahnafnafee/songmirror/releases.atom).

## Write release notes

For a change that users will notice, add a short Markdown file in `.github/release-notes/`. Start with a level-one headline that names the feature and the music service where relevant. Use the opening paragraph to explain what users can now do and include the words they would search for, such as “Shazam CSV” or “Spotify playlist import.” Keep the remaining bullets specific to the change.

The release title combines the SongMirror name, the version, and that headline. The release body puts these notes before the archive verification instructions and GitHub’s generated changelog. For releases without a note file, the workflow uses the most relevant Conventional Commit or PR headline.

## Verify a release

Download the named `songmirror-v*.tar.gz` attachment and its `.sigstore.json` bundle from the [release page](https://github.com/ahnafnafee/songmirror/releases). The CI workflow signs the archive digest and records the source commit. Use these attachments to verify the release archive.

```sh
gh attestation verify songmirror-v0.1.0.tar.gz \
  --bundle songmirror-v0.1.0.tar.gz.sigstore.json \
  --repo ahnafnafee/songmirror \
  --signer-workflow ahnafnafee/songmirror/.github/workflows/ci.yml \
  --source-ref refs/heads/main
```

Replace the example version with the two filenames you downloaded. The signature is a keyless Sigstore attestation on the archive. Docker images have separate [provenance attestations](docker-image.md).
