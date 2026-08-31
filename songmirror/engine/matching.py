"""Track identity and matching.

The hierarchy every cross-service music tool uses: a hard identifier (ISRC or a
cached link) first, then a fuzzy search scored against title/artist/duration.
The fuzzy layer is RapidFuzz `token_set_ratio` (order/subset/decoration
tolerant) plus Jaro-Winkler (short strings, transliteration near-misses), run
over both raw and romanized (anyascii) variants so different scripts match. The
duration anchor gates the looser matching so a different version or a
wrong-artist cover is rejected when its length disagrees.
"""

import math
import re
import unicodedata
from datetime import datetime, timezone

from anyascii import anyascii
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

FUZZY_THRESHOLD = 0.92
DURATION_TOLERANCE_MS = 2500
CATALOG_DURATION_TOLERANCE_MS = 5000

PAREN_FEAT_RE = re.compile(r"[\(\[]\s*(feat|featuring|ft|with)\b.*?[\)\]]", re.IGNORECASE)
TRAILING_FEAT_RE = re.compile(r"\s+(feat|featuring|ft)\s+.*$")
CATALOG_TAG = r"(?:(?:\d{4}\s+)?re-?master(?:ed)?(?:\s+\d{4})?|clean|explicit)"
BRACKETED_CATALOG_TAG_RE = re.compile(rf"[\(\[]\s*(?:{CATALOG_TAG})\s*[\)\]]", re.IGNORECASE)
TRAILING_CATALOG_TAG_RE = re.compile(rf"\s*[-–—]\s*(?:{CATALOG_TAG})\s*$", re.IGNORECASE)
FROM_RELEASE_RE = re.compile(
    r'\s*(?:[-–—]\s*from|[\(\[]\s*from)\s+["“][^"”]+["”]\s*[\)\]]?\s*$',
    re.IGNORECASE,
)
CREATIVE_VERSION_PATTERNS = (
    ("live", re.compile(r"\blive\b", re.IGNORECASE)),
    ("acoustic", re.compile(r"\b(?:acoustic|unplugged)\b", re.IGNORECASE)),
    ("remix", re.compile(r"\b(?:remix|rework|extended mix|radio edit)\b", re.IGNORECASE)),
    ("instrumental", re.compile(r"\binstrumental\b", re.IGNORECASE)),
    ("karaoke", re.compile(r"\bkaraoke\b", re.IGNORECASE)),
    ("piano", re.compile(r"\bpiano\b", re.IGNORECASE)),
    ("demo", re.compile(r"\bdemo\b", re.IGNORECASE)),
    ("session", re.compile(r"\bsession\b", re.IGNORECASE)),
    ("alternate-speed", re.compile(r"\b(?:sped up|slowed(?: down)?|nightcore)\b", re.IGNORECASE)),
    ("mix-format", re.compile(r"\b(?:mono|stereo)\b", re.IGNORECASE)),
    ("cover", re.compile(r"\bcover\b", re.IGNORECASE)),
)


def _added_at_epoch(value):
    """Normalize provider date-added values to Unix seconds when possible.

    Providers currently expose a mix of ISO-8601 strings and Unix timestamps
    (seconds or milliseconds). Comparing their raw strings puts, for example,
    every numeric timestamp before every ISO date regardless of chronology.
    """
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        if 1 <= year <= 9999:
            return datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        timestamp = float(text)
        if not math.isfinite(timestamp):
            return None
        # Bring millisecond/microsecond/nanosecond values down to seconds. The
        # threshold is safely beyond any date a playlist API can return.
        while abs(timestamp) > 32_503_680_000:
            timestamp /= 1000
        return timestamp
    if text[-1:] in {"Z", "z"}:
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def track_addition_order_key(track, *, source_rank=0, playlist_position=0):
    """Oldest-first key with deterministic source-position fallback.

    A trustworthy date-added value is the best cross-provider chronology. If a
    provider does not expose one (Apple, Amazon, and YouTube currently do not),
    its playlist position is the only truthful order evidence available.
    """
    timestamp = _added_at_epoch(track.get("added_at"))
    if timestamp is None:
        return 1, source_rank, playlist_position, 0
    return 0, timestamp, source_rank, playlist_position


def tracks_oldest_first(tracks):
    """Return tracks in date-added order, preserving playlist order as fallback."""
    positioned = list(enumerate(tracks))
    positioned.sort(key=lambda item: track_addition_order_key(
        item[1], playlist_position=item[0]))
    return [track for _, track in positioned]


def normalize_text(value):
    """Unicode-aware: keeps letters/digits in ANY script (Cyrillic, CJK,
    Bengali, ...). A Latin-only character class silently empties non-Latin
    titles, which breaks matching and can delete real tracks."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    normalized = re.sub(r"[\W_]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_isrc(value):
    """Canonical ISRC spelling across provider APIs and old cache entries.

    ISRC is case-insensitive and commonly rendered with optional punctuation
    (``GB-SMU-26-29433`` vs ``GBSMU2629433``). Canonical membership must not
    treat those presentation differences as different recordings.
    """
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).upper()


def normalize_canonical_id(value):
    """Normalize the ISRC portion of an ``i:`` identity; preserve other kinds."""
    canonical = str(value or "")
    if not canonical.startswith("i:"):
        return canonical
    isrc = normalize_isrc(canonical[2:])
    return f"i:{isrc}" if isrc else canonical


def loose_name(name):
    """Title with feat-clauses stripped — '(feat. X)' is the classic drift for
    the SAME song. Version qualifiers like (Live)/(Acoustic) are kept: those
    are different recordings — but the abbreviation 'ver' expands to 'version'
    so 'Twin Ver.' and 'Twin Version' agree token-for-token."""
    cleaned = TRAILING_FEAT_RE.sub("", normalize_text(PAREN_FEAT_RE.sub(" ", name or ""))).strip()
    cleaned = re.sub(r"\bver\b", "version", cleaned)
    return cleaned or normalize_text(name)


def catalog_name(name):
    """A conservative title identity for destination-side duplicate guards.

    Providers often expose the same audio under a second catalog id with a
    remaster year, clean/explicit label, or soundtrack-release suffix. Those
    decorations are safe to ignore when artist and duration also agree. Creative
    qualifiers (remix, acoustic, live, piano, radio edit, etc.) deliberately
    remain, so genuinely different recordings never collapse merely by title.
    """
    cleaned = str(name or "")
    while True:
        previous = cleaned
        cleaned = BRACKETED_CATALOG_TAG_RE.sub(" ", cleaned)
        cleaned = TRAILING_CATALOG_TAG_RE.sub(" ", cleaned)
        cleaned = FROM_RELEASE_RE.sub(" ", cleaned)
        if cleaned == previous:
            break
    return loose_name(cleaned)


def creative_version_markers(name):
    """Recording-changing title qualifiers that must agree during fuzzy search.

    Search APIs regularly rank a live/acoustic/remix release above the ordinary
    studio track. Similar title/artist text (and occasionally similar duration)
    is not enough evidence to substitute one for the other. Generic "version"
    is used only when no more specific qualifier explains it, so "Piano
    Version" and "Piano" still describe the same creative variant.
    """
    normalized = normalize_text(name)
    markers = {
        marker
        for marker, pattern in CREATIVE_VERSION_PATTERNS
        if pattern.search(normalized)
    }
    if not markers and re.search(r"\bversion\b", normalized):
        markers.add("alternate-version")
    return markers


def romanized(text):
    """ASCII romanization for cross-script matching (Камин->kamin, ত্রি->tri).
    Cyrillic / Bengali / Greek / Arabic romanize reliably; CJK yields a Chinese
    reading, so kanji/kana titles stay best-effort."""
    return normalize_text(anyascii(str(text or "")))


def track_key(name, artist):
    return f"{loose_name(name)}|{normalize_text(artist)}"


def _sim_strict(a, b):
    """0..1 similarity that PENALIZES extra words (token_sort) with a
    Jaro-Winkler floor for short strings / transliteration near-misses. Rejects
    different versions whose titles carry extra words when duration can't."""
    if not a or not b:
        return 0.0
    return max(fuzz.token_sort_ratio(a, b) / 100.0, JaroWinkler.normalized_similarity(a, b))


def _sim_loose(a, b):
    """0..1 token-set similarity: order-, subset- and decoration-tolerant. High
    when one string's tokens are a subset of the other (multi-artist credits,
    decorated video titles). Trusted for titles only with duration support."""
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b) / 100.0


def _name_variants(text):
    return {v for v in (loose_name(text), romanized(text)) if v}


def _best(sim, q_variants, c_variants):
    return max((sim(a, b) for a in q_variants for b in c_variants if a and b), default=0.0)


def _artist_variants(track):
    artists = track.get("artists") or ([track["artist"]] if track.get("artist") else [])
    joined = " ".join(str(artist) for artist in artists if artist)
    display = track.get("artist") or joined
    variants = {
        variant
        for variant in (
            normalize_text(joined),
            romanized(joined),
            normalize_text(display),
            romanized(display),
        )
        if variant
    }
    # Provider punctuation varies for compact stage names (AC/DC vs ACDC,
    # M|A|R|R|S vs MARRS). Keep the ordinary tokenized forms too so multi-artist
    # subset matching still behaves as before.
    variants.update(variant.replace(" ", "") for variant in list(variants))
    return variants


def _artist_similarity(track, candidate):
    return _best(_sim_loose, _artist_variants(track), _artist_variants(candidate))


def fuzzy_in(key, keys, threshold=FUZZY_THRESHOLD):
    # ponytail: O(len(keys)) scan per unmatched track; fine for playlist-sized
    # sets, index it if someone mirrors a 50k-track monster.
    return any(_sim_loose(key, k) >= threshold for k in keys)


def score_candidate(name, artists, duration_ms, cand_name, cand_artist, cand_duration_ms):
    """(score in 0..1, acceptable) for a search-result candidate vs the wanted
    track — the fuzzy fallback when no ISRC/link resolves it."""
    if creative_version_markers(name) != creative_version_markers(cand_name):
        return 0.0, False
    if isinstance(artists, str):
        artists = [artists]
    q_names, c_names = _name_variants(name), _name_variants(cand_name)
    name_strict = _best(_sim_strict, q_names, c_names)
    name_loose = _best(_sim_loose, q_names, c_names)

    joined = " ".join(artists)
    q_art = {normalize_text(joined), romanized(joined)}
    c_art = {normalize_text(cand_artist), romanized(cand_artist)}
    artist_sim = _best(_sim_loose, q_art, c_art)  # subset-tolerant: services list the primary artist

    if duration_ms is not None and cand_duration_ms is not None:
        delta = abs(duration_ms - cand_duration_ms)
        duration_score = max(0.0, 1.0 - delta / (DURATION_TOLERANCE_MS * 4))
        duration_close = delta <= DURATION_TOLERANCE_MS
    else:
        duration_score, duration_close = 0.5, False

    name_sim = max(name_strict, name_loose) if duration_close else name_strict
    score = 0.45 * name_sim + 0.35 * artist_sim + 0.20 * duration_score
    strong = duration_close and name_sim >= 0.78 and artist_sim >= 0.58
    fuzzy = name_strict >= 0.88 and artist_sim >= 0.60
    return score, (strong or fuzzy)


def spotify_track_keys(track):
    keys = {track_key(track["name"], artist) for artist in track["artists"]}
    keys.add(track_key(track["name"], " ".join(track["artists"])))
    return keys


def same_catalog_recording(track, candidate):
    """Whether two provider entries are safely interchangeable recordings.

    This is intentionally narrower than search matching: exact catalog-normalized
    title, strongly overlapping artist credits, and (when both providers expose
    it) near-identical duration. It catches alternate catalog releases without
    treating an acoustic/live/remix/version as the ordinary track.
    """
    wanted = catalog_name(track.get("name"))
    existing = catalog_name(candidate.get("name"))
    if not wanted or wanted != existing:
        return False

    artist_sim = _artist_similarity(track, candidate)
    if artist_sim < FUZZY_THRESHOLD:
        return False

    duration = track.get("duration_ms")
    candidate_duration = candidate.get("duration_ms")
    if duration is not None and candidate_duration is not None:
        return abs(duration - candidate_duration) <= CATALOG_DURATION_TOLERANCE_MS
    return True


def same_unresolved_recording(source_track, existing_track, threshold=0.8):
    """Whether an unresolved source item can safely protect an existing copy.

    This guard intentionally favors retention, but title and artist evidence
    must be evaluated independently. Comparing one combined ``title|artist``
    string lets a shared title and one common artist token outweigh a different
    performer (for example, two unrelated songs named "Bad Blood"). Duration,
    when both providers expose it, must also agree closely.
    """
    if creative_version_markers(source_track.get("name")) != creative_version_markers(
        existing_track.get("name")
    ):
        return False

    title_similarity = _best(
        _sim_loose,
        _name_variants(source_track.get("name")),
        _name_variants(existing_track.get("name")),
    )
    if title_similarity < threshold:
        return False
    if _artist_similarity(source_track, existing_track) < FUZZY_THRESHOLD:
        return False

    source_duration = source_track.get("duration_ms")
    existing_duration = existing_track.get("duration_ms")
    if source_duration is not None and existing_duration is not None:
        return abs(source_duration - existing_duration) <= CATALOG_DURATION_TOLERANCE_MS
    return True


def compute_diff(sp_tracks, target_tracks, expected_by_sp, target_id_of, threshold=FUZZY_THRESHOLD):
    """Set diff shared by every target.

    expected_by_sp: {spotify_track_id: set(target_ids)} the Spotify track is
    known to correspond to (cached links + ISRC candidates). target_id_of(t):
    the target's stable id for one of its existing tracks.

    to_add: Spotify tracks with no matching id and no exact title|artist key on
    the target, sorted by added_at ascending so the newest lands last.
    to_remove: target tracks whose id isn't expected and whose key has no exact
    or fuzzy Spotify match (fuzzy applies only to this destructive side, as the
    guard against a metadata mismatch deleting a real track).
    """
    target_ids = {target_id_of(t) for t in target_tracks if target_id_of(t)}
    target_keys = {track_key(t["name"], t["artist"]) for t in target_tracks}

    expected_all = set()
    sp_keys = set()
    sp_keys_by_version = {}
    to_add = []
    for tr in sp_tracks:
        expected = expected_by_sp.get(tr.get("id")) or set()
        expected_all |= expected
        keys = spotify_track_keys(tr)
        sp_keys |= keys
        version = frozenset(creative_version_markers(tr.get("name")))
        sp_keys_by_version.setdefault(version, set()).update(keys)
        if expected & target_ids:
            continue
        if keys & target_keys:
            continue
        to_add.append(tr)
    to_add = tracks_oldest_first(to_add)

    to_remove = []
    for t in target_tracks:
        tid = target_id_of(t)
        if tid and tid in expected_all:
            continue
        key = track_key(t["name"], t["artist"])
        compatible_keys = sp_keys_by_version.get(
            frozenset(creative_version_markers(t.get("name"))), set()
        )
        if key in sp_keys or fuzzy_in(key, compatible_keys, threshold):
            continue
        to_remove.append(t)
    return to_add, to_remove


def match_unresolved_removals(to_remove, not_found_tracks, threshold=0.8):
    """Return safe removals and the unresolved source match protecting each hold."""
    safe, protected = [], []
    for track in to_remove:
        source_match = next(
            (
                source_track
                for source_track in not_found_tracks
                if same_unresolved_recording(source_track, track, threshold)
            ),
            None,
        )
        if source_match is not None:
            protected.append((track, source_match))
        else:
            safe.append(track)
    return safe, protected


def protect_removals(to_remove, not_found_tracks, threshold=0.8):
    """Split removals into (safe, held): a target track resembling a Spotify
    track that has NO match on that service must not be deleted — that would
    drop the song with no replacement. The title threshold is deliberately
    loose because wrongly holding leaves an extra track while wrongly deleting
    loses music; artist and duration evidence are still checked independently."""
    safe, protected = match_unresolved_removals(
        to_remove, not_found_tracks, threshold
    )
    return safe, [track for track, _source_match in protected]
