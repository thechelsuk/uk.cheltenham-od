"""Offline tests for the charities fetcher's website clean-up.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import pytest

import charities


@pytest.mark.parametrize("raw, expected", [
    ("www.example.org.uk", "http://www.example.org.uk"),
    ("http://www.example.org.uk", "http://www.example.org.uk"),
    ("HTTPS://www.example.org.uk/about", "HTTPS://www.example.org.uk/about"),
    # The register sometimes has a scheme with one slash missing.
    ("http:/gloucestershire.example.org.uk", "http://gloucestershire.example.org.uk"),
    ("https:/www.example.org.uk", "https://www.example.org.uk"),
    ("  ", None),
    (None, None),
])
def test_website(raw, expected):
    assert charities.website(raw) == expected

