"""Keep provider settings projected by one test out of the next test."""

import os
import json

import pytest


@pytest.fixture(autouse=True)
def restore_test_process_environment(tmp_path):
    previous = dict(os.environ)
    os.environ["SONGMIRROR_ALLOWED_HOSTS"] = "testserver"
    os.environ["SONGMIRROR_FOLDER_ROOTS"] = json.dumps([str(tmp_path)])
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)
