"""Keep provider settings projected by one test out of the next test."""

import os

import pytest


@pytest.fixture(autouse=True)
def restore_test_process_environment():
    previous = dict(os.environ)
    os.environ["SONGMIRROR_ALLOWED_HOSTS"] = "testserver"
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)
