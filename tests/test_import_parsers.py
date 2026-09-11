from songmirror.services.import_parsers.csv_parser import parse_csv
from songmirror.services.import_parsers.file import parse_file
from songmirror.services.import_parsers.m3u import parse_m3u
from songmirror.services.import_parsers.text import parse_text


class TestTextParser:
    def test_artist_title_format(self):
        result = parse_text("Daft Punk - One More Time")
        assert len(result.tracks) == 1
        assert result.tracks[0].artist == "Daft Punk"
        assert result.tracks[0].title == "One More Time"

    def test_em_dash(self):
        result = parse_text("Beyoncé – CUFF IT")
        assert result.tracks[0].artist == "Beyoncé"
        assert result.tracks[0].title == "CUFF IT"

    def test_by_format(self):
        result = parse_text("Mr. Brightside by The Killers")
        assert result.tracks[0].title == "Mr. Brightside"
        assert result.tracks[0].artist == "The Killers"

    def test_title_only(self):
        result = parse_text("Bohemian Rhapsody")
        assert result.tracks[0].title == "Bohemian Rhapsody"
        assert result.tracks[0].artist is None

    def test_hash_prefixed_title(self):
        result = parse_text("#1 Crush")
        assert result.tracks[0].title == "#1 Crush"

    def test_empty_lines(self):
        result = parse_text("\n\nDaft Punk - One More Time\n\n")
        assert len(result.tracks) == 1


class TestCSVParser:
    def test_header_with_aliases(self):
        csv_content = "Track Name,Artist Name\nOne More Time,Daft Punk"
        result = parse_csv(csv_content)
        assert result.tracks[0].title == "One More Time"
        assert result.tracks[0].artist == "Daft Punk"

    def test_positional_format(self):
        # Positional CSV is artist,title[,album[,duration]].
        csv_content = "Daft Punk,One More Time"
        result = parse_csv(csv_content)
        assert result.tracks[0].artist == "Daft Punk"
        assert result.tracks[0].title == "One More Time"

    def test_utf8_bom(self):
        csv_content = b"\xef\xbb\xbfTitle,Artist\nSong,Artist"
        result = parse_file(csv_content, "playlist.csv")
        assert result.tracks[0].title == "Song"
        assert result.tracks[0].artist == "Artist"


class TestM3UParser:
    def test_extm3u_format(self):
        m3u_content = """#EXTM3U
#EXTINF:240,Daft Punk - One More Time
One More Time.mp3
#EXTINF:200,Beethoven - Symphony
Beethoven.mp3"""
        result = parse_m3u(m3u_content)
        assert len(result.tracks) == 2
        assert result.tracks[0].artist == "Daft Punk"
        assert result.tracks[0].title == "One More Time"

    def test_simple_list(self):
        m3u_content = "song1.mp3\nsong2.mp3"
        result = parse_m3u(m3u_content)
        assert len(result.tracks) == 2
