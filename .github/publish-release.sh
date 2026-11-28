#!/usr/bin/env bash
set -euo pipefail

archive_name=${RELEASE_ARCHIVE##*/}
bundle="${RELEASE_ARCHIVE}.sigstore.json"
cp -- "$ATTESTATION_BUNDLE" "$bundle"
gh attestation verify "$RELEASE_ARCHIVE" --bundle "$bundle" --repo "$GITHUB_REPOSITORY" \
  --signer-workflow "$GITHUB_REPOSITORY/.github/workflows/ci.yml" \
  --source-ref refs/heads/main --source-digest "$GITHUB_SHA"

# A rerun may find a draft after an interrupted upload. Check the commit before
# resuming it. Published releases are only checked, never overwritten.
remote_tag=$(git ls-remote origin "refs/tags/$RELEASE_TAG" "refs/tags/$RELEASE_TAG^{}" |
  awk '$2 ~ /\^\{\}$/ { peeled = $1; next } { tag = $1 } END { print (peeled ? peeled : tag) }')
if [[ -n "$remote_tag" && "$remote_tag" != "$GITHUB_SHA" ]]; then
  echo "Release tag $RELEASE_TAG already points to $remote_tag" >&2
  exit 1
fi

if release=$(gh release view "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" \
    --json isDraft,targetCommitish,assets); then
  if [[ $(jq -r '.isDraft' <<< "$release") == false ]]; then
    [[ "$remote_tag" == "$GITHUB_SHA" ]]
    jq -e --arg archive "$archive_name" --arg bundle "${bundle##*/}" \
      '([.assets[].name] | index($archive) != null and index($bundle) != null)' \
      <<< "$release" > /dev/null
    exit 0
  fi
  [[ $(jq -r '.targetCommitish' <<< "$release") == "$GITHUB_SHA" || "$remote_tag" == "$GITHUB_SHA" ]]
else
  notes=$(cat -- "$RELEASE_NOTES")
  printf -v notes '%s\n\n## Download and verify\n\nThe source archive includes a Sigstore provenance bundle. [Verification instructions](https://github.com/%s/blob/%s/docs/releases.md).' \
    "$notes" "$GITHUB_REPOSITORY" "$GITHUB_SHA"
  start=()
  if [[ -n "$RELEASE_PREVIOUS_TAG" ]]; then
    start=(--notes-start-tag "$RELEASE_PREVIOUS_TAG")
  fi
  gh release create "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --target "$GITHUB_SHA" \
    --title "$RELEASE_TITLE" --generate-notes --draft "${start[@]}" --notes "$notes"
fi

gh release upload "$RELEASE_TAG" "$RELEASE_ARCHIVE" "$bundle" --repo "$GITHUB_REPOSITORY" --clobber
tip=$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq '.object.sha')
latest=false
if [[ "$tip" == "$GITHUB_SHA" ]]; then
  latest=true
fi
gh release edit "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false --latest="$latest"
