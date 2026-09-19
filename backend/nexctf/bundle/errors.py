"""The error every bundle reader raises."""

from __future__ import annotations


class BundleFormatError(Exception):
    """A tree could not be read as a bundle."""
