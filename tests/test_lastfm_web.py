"""Last.fm website client: session paste and HTML parsing.

The fixtures below are trimmed from real last.fm markup. They are the fragile
part of this adapter, because it reads server-rendered pages rather than an
API, so they are asserted against directly.
"""

import pytest

from songmirror.lastfm_web import (
    LastfmWeb,
    LastfmWebAuthError,
    _csrf,
    configured,
    credentials_from,
    parse_web_request,
    serialize_web_request,
)

CURL = (
    "curl 'https://www.last.fm/user/ahnafnafee/playlists' "
    "-H 'User-Agent: Mozilla/5.0' "
    "-H 'Cookie: csrftoken=TOK123; sessionid=SESS456; _pk_id.1=noise; other=junk'"
)

INDEX_HTML = """
<div class="playlists">
  <a href="/user/ahnafnafee/playlists/14604666"><img src="cover.jpg"></a>
  <a href="/user/ahnafnafee/playlists/14604666">Test</a>
  <a href="/user/ahnafnafee/playlists/99">Road Trip</a>
  <a href="/user/ahnafnafee/library">Library</a>
</div>
<input type="hidden" name="csrfmiddlewaretoken" value="PAGETOKEN">
"""

ENTRY_HTML = """
<input type="hidden" name="csrfmiddlewaretoken" value="PAGETOKEN">
<table>
<tr class="chartlist-row" data-playlist-row data-playlist-entry-url="/user/ahnafnafee/playlists/14604666/entries/310637776">
  <td class="chartlist-image"><img src="x.jpg" alt="Radiohead - Creep"></td>
  <td class="chartlist-name"><a href="/music/Radiohead/_/Radiohead+-+Creep">Radiohead - Creep</a></td>
  <td class="chartlist-artist"><a href="/music/Radiohead">Radiohead</a></td>
  <td><a href="/music/Radiohead/_/Radiohead+-+Creep">Go to track</a></td>
  <td><a href="/user/ahnafnafee/library/music/Radiohead">Go to artist in library</a></td>
</tr>
<tr class="chartlist-row" data-playlist-row data-playlist-entry-url="/user/ahnafnafee/playlists/14604666/entries/310637777">
  <td class="chartlist-image"><img src="y.jpg" alt="Sam Hunt - Cop Car"></td>
  <td class="chartlist-name"><a href="/music/Sam+Hunt/_/Cop+Car">Cop Car</a></td>
  <td class="chartlist-artist"><a href="/music/Sam+Hunt">Sam Hunt</a></td>
</tr>
</table>
"""

SEARCH_HTML = """
<input type="hidden" name="csrfmiddlewaretoken" value="PAGETOKEN">
<form action="/user/ahnafnafee/playlists/14604666/entries" method="post" data-playlisting-add-form>
  <input type="hidden" name="csrfmiddlewaretoken" value="ROWTOKEN">
  <input type="hidden" name="track" value="Kanye West - Power">
  <input type="hidden" name="artist" value="Kanye West">
  <button type="submit">Add</button>
</form>
<form action="/user/ahnafnafee/playlists/14604666/entries" method="post" data-playlisting-add-form>
  <input type="hidden" name="csrfmiddlewaretoken" value="ROWTOKEN">
  <input type="hidden" name="track" value="01 Kanye West - Power">
  <input type="hidden" name="artist" value="KanyeWestVEVO">
  <button type="submit">Add</button>
</form>
"""


class _Cookies(dict):
    def set(self, name, value, domain=None):
        self[name] = value


class _Response:
    def __init__(self, text="", status_code=200, url=""):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected raise_for_status at {self.status_code}")


class _Session:
    """Scripted stand-in for requests.Session."""

    def __init__(self, pages=None, post_response=None):
        self.headers = {}
        self.cookies = _Cookies()
        self._pages = dict(pages or {})
        self._post_response = post_response
        self.gets, self.posts = [], []

    def get(self, url, params=None, timeout=None):
        self.gets.append((url, params))
        path = url.replace("https://www.last.fm", "")
        for key, body in self._pages.items():
            if key in path:
                return _Response(body, url=url)
        return _Response("", url=url)

    def post(self, url, data=None, timeout=None, headers=None):
        self.posts.append((url.replace("https://www.last.fm", ""), dict(data or {})))
        return self._post_response or _Response(url=url)


def _web(pages=None, post_response=None, user="ahnafnafee"):
    return LastfmWeb({"sessionid": "s", "csrftoken": "c"}, user,
                     session=_Session(pages, post_response))


# -- session paste -----------------------------------------------------------


def test_paste_keeps_only_the_two_session_cookies():
    assert parse_web_request(CURL) == {"sessionid": "SESS456", "csrftoken": "TOK123"}
    stored = serialize_web_request(CURL)
    assert "junk" not in stored and "_pk_id" not in stored


def test_paste_without_the_cookies_is_rejected():
    with pytest.raises(ValueError, match="sessionid"):
        parse_web_request("curl 'https://www.last.fm/' -H 'Cookie: other=junk'")
    with pytest.raises(ValueError):
        parse_web_request("")


def test_credentials_from_tolerates_stored_json_and_garbage():
    assert credentials_from(serialize_web_request(CURL))["sessionid"] == "SESS456"
    assert credentials_from("not a request") is None
    assert credentials_from("") is None
    assert configured({"sessionid": "s"}) is False


# -- parsing -----------------------------------------------------------------


def test_csrf_token_is_read_from_the_page():
    assert _csrf(INDEX_HTML) == "PAGETOKEN"


def test_a_signed_out_page_is_reported_as_an_expired_session():
    with pytest.raises(LastfmWebAuthError, match="expired"):
        _csrf("<html><body>Log In</body></html>")


def test_playlists_are_deduped_and_named():
    """Each playlist is linked twice, once by its cover with no text."""
    found = _web({"/playlists": INDEX_HTML}).list_playlists()

    assert found == [{"id": "14604666", "name": "Test"}, {"id": "99", "name": "Road Trip"}]


def test_entries_carry_the_entry_id_track_and_artist():
    rows = _web({"/playlists/14604666": ENTRY_HTML}).entries("14604666")

    assert rows == [
        {"entry_id": "310637776", "name": "Radiohead - Creep", "artist": "Radiohead"},
        {"entry_id": "310637777", "name": "Cop Car", "artist": "Sam Hunt"},
    ]


def test_entry_parsing_ignores_the_go_to_links():
    rows = _web({"/playlists/14604666": ENTRY_HTML}).entries("14604666")

    assert all("Go to" not in row["name"] for row in rows)


def test_search_returns_the_exact_strings_each_row_would_send():
    rows = _web({"search-catalogue": SEARCH_HTML}).search("Kanye West POWER", "14604666")

    assert rows == [
        {"track": "Kanye West - Power", "artist": "Kanye West"},
        {"track": "01 Kanye West - Power", "artist": "KanyeWestVEVO"},
    ]


# -- writes ------------------------------------------------------------------


def test_add_posts_the_track_and_artist_with_a_fresh_token():
    web = _web({"/playlists/14604666": ENTRY_HTML})

    web.add("14604666", "Radiohead - Creep", "Radiohead")

    path, body = web._session.posts[0]
    assert path == "/user/ahnafnafee/playlists/14604666/entries"
    assert body == {"csrfmiddlewaretoken": "PAGETOKEN",
                    "track": "Radiohead - Creep", "artist": "Radiohead"}


def test_remove_addresses_the_entry_with_delete_entry():
    web = _web({"/playlists/14604666": ENTRY_HTML})

    web.remove("14604666", "310637776")

    path, body = web._session.posts[0]
    assert path == "/user/ahnafnafee/playlists/14604666/entries/310637776"
    assert body["action"] == "delete-entry"


def test_create_takes_the_new_id_from_the_redirect_then_titles_it():
    """The site creates an empty, untitled playlist and takes the title through
    a separate edit post."""
    web = _web({"/playlists": INDEX_HTML},
               post_response=_Response(url="https://www.last.fm/user/ahnafnafee/playlists/777"))

    created = web.create("From Spotify")

    assert created == {"id": "777", "name": "From Spotify"}
    assert web._session.posts[0][0] == "/user/ahnafnafee/playlists"
    assert web._session.posts[1][1]["title"] == "From Spotify"


def test_create_without_a_new_id_is_an_error_not_a_silent_success():
    web = _web({"/playlists": INDEX_HTML},
               post_response=_Response(url="https://www.last.fm/user/ahnafnafee/playlists"))

    with pytest.raises(LastfmWebAuthError, match="did not report"):
        web.create("From Spotify")


def test_delete_sends_the_playlist_action():
    web = _web({"/playlists/14604666": ENTRY_HTML})

    web.delete("14604666")

    path, body = web._session.posts[0]
    assert path == "/user/ahnafnafee/playlists/14604666"
    assert body["action"] == "delete"


def test_a_username_is_required():
    with pytest.raises(LastfmWebAuthError):
        LastfmWeb({"sessionid": "s", "csrftoken": "c"}, "")
