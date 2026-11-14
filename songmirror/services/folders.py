"""Directory selection for files written by the SongMirror server."""

import os
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath


def writable_directory(value):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError("Enter a folder path on the computer running SongMirror.")
    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        raise ValueError("Use a full folder path on the computer running SongMirror.")
    if not path.is_dir():
        raise ValueError("Folder not found. Choose an existing folder accessible to SongMirror.")
    if not os.access(path, os.W_OK | os.X_OK):
        raise ValueError("SongMirror cannot write to this folder. Choose another folder or update its permissions.")
    return path.resolve()


def download_directory(settings):
    configured = settings.get("DOWNLOAD_DIR", "") or ""
    mounted = os.getenv("SONGMIRROR_DOWNLOAD_DIR", "")
    # Explicit choices made through the folder UI take precedence, including
    # disabling downloads. Older configs may contain a host-only Windows path.
    if settings.get("DOWNLOAD_DIR_CONFIRMED") == "1":
        return configured
    if mounted:
        return mounted
    return configured or os.getenv("DOWNLOAD_DIR", "")


class FolderBrowser:
    """Browse directories available to the server, without reading file contents."""

    def __init__(self, settings):
        self.settings = settings
        configured = os.getenv("SONGMIRROR_FOLDER_ROOTS", "")
        if configured:
            try:
                roots = json.loads(configured)
            except ValueError as exc:
                raise ValueError("SONGMIRROR_FOLDER_ROOTS must be a JSON array of absolute paths.") from exc
            if not isinstance(roots, list) or not roots or any(not isinstance(root, str) for root in roots):
                raise ValueError("SONGMIRROR_FOLDER_ROOTS must be a nonempty JSON array of absolute paths.")
        else:
            roots = [str(Path.home() / "Music"), str(Path(settings.data_dir).resolve().parent / "downloads")]
            roots += [value for value in (os.getenv("SONGMIRROR_DOWNLOAD_DIR"),
                os.getenv("DOWNLOAD_DIR"), os.getenv("LOCAL_LIBRARY_DIR")) if value]
        self.roots = tuple(dict.fromkeys([Path(settings.data_dir).resolve(), *[
            self._absolute(root) for root in roots
        ]]))

    @staticmethod
    def _absolute(value):
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("Folder roots must be absolute server paths.")
        return path.resolve()

    def _root(self, path):
        roots = [root for root in self.roots if path.is_relative_to(root)]
        if not roots:
            raise ValueError("Folder is outside the server's allowed locations. Configure SONGMIRROR_FOLDER_ROOTS on the server.")
        return max(roots, key=lambda root: len(root.parts))

    def directory(self, value, *, writable=False):
        value = self.server_path(value)
        if not isinstance(value, str) or "\0" in value or len(value) > 4096:
            raise ValueError("Enter a valid folder path.")
        path = self._absolute(value)
        self._root(path)
        if writable:
            return writable_directory(str(path))
        if not path.is_dir():
            raise ValueError("Folder not found. Choose a listed location.")
        return path

    def config(self):
        container = Path('/.dockerenv').is_file()
        host = os.getenv("SONGMIRROR_HOST_DOWNLOAD_DIR", "")
        server = os.getenv("SONGMIRROR_DOWNLOAD_DIR", "")
        mounts = []
        if host and server and (PureWindowsPath(host).is_absolute() or PurePosixPath(host).is_absolute()):
            mounts.append({"host": host, "server": server})
        locations = [{"name": "App data", "path": str(Path(self.settings.data_dir).resolve())}]
        music = download_directory(self.settings)
        if music and Path(music).is_dir():
            locations.insert(0, {"name": "Music downloads", "path": str(Path(music).resolve())})
        locations.extend({"name": root.name or str(root), "path": str(root)}
                         for root in self.roots if root.is_dir())
        locations = list({item["path"]: item for item in locations
                          if any(Path(item["path"]).resolve().is_relative_to(root) for root in self.roots)}.values())
        return {"mounts": mounts, "locations": locations,
                "scope": "container" if container else "computer"}

    def server_path(self, value):
        if not isinstance(value, str):
            return value
        for mount in self.config()["mounts"]:
            path_type = PureWindowsPath if PureWindowsPath(mount["host"]).drive else PurePosixPath
            try:
                relative = path_type(value).relative_to(mount["host"])
            except ValueError:
                continue
            if ".." in relative.parts:
                raise ValueError("Folder must stay within its shared location.")
            return str(PurePosixPath(mount["server"]).joinpath(*relative.parts))
        if os.name != 'nt' and PureWindowsPath(value).is_absolute():
            raise ValueError('This Windows folder is not shared with SongMirror. Choose a listed location, or share the folder with the Docker container first.')
        return value

    def browse(self, value=""):
        path = self.directory(value or str(self.settings.data_dir))
        root = self._root(path)
        directories = []
        try:
            for child in path.iterdir():
                try:
                    if child.is_dir() and not child.name.startswith('.'):
                        self._root(child.resolve())
                        directories.append({"name": child.name, "path": str(child)})
                except (OSError, ValueError):
                    continue
        except PermissionError as exc:
            raise ValueError("SongMirror cannot open this folder. Choose another location or update its permissions.") from exc
        directories.sort(key=lambda child: (child["name"].casefold(), child["name"]))
        ancestors = [item for item in reversed(path.parents) if item.is_relative_to(root)] + [path]
        return {"path": str(path), "parent": str(path.parent) if path != root else None,
                "breadcrumbs": [{"name": item.name or str(item), "path": str(item)} for item in ancestors],
                "directories": directories, "writable": os.access(path, os.W_OK | os.X_OK)}

    def create(self, parent, name):
        # Accept one portable folder name, never a path or a Windows device.
        if (not isinstance(name, str) or not name or len(name) > 255
                or name != name.strip() or name.endswith('.') or name in ('.', '..')
                or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name)
                or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I)):
            raise ValueError('Enter a folder name without path separators, reserved characters, or trailing dots or spaces.')
        directory = self.directory(parent, writable=True)
        child = directory / name
        try:
            child.mkdir()
        except FileExistsError as exc:
            raise ValueError('A file or folder with that name already exists. Choose another name.') from exc
        except OSError as exc:
            raise ValueError('SongMirror could not create this folder. Check permissions or choose another name or location.') from exc
        return {"path": str(child)}
