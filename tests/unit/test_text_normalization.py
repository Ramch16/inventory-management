"""Normalization and similarity: the basis of duplicate detection and field mapping."""

from __future__ import annotations

import pytest
from jobapply_shared.text import (
    content_hash,
    normalize_company,
    normalize_location,
    normalize_title,
    seniority_level,
    title_similarity,
    token_overlap,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme, Inc.", "acme"),
        ("ACME Technologies LLC", "acme"),
        ("Northwind Analytics", "northwind analytics"),
        ("Foo & Bar Corp", "foo and bar"),
    ],
)
def test_normalize_company_strips_legal_suffixes(raw, expected):
    assert normalize_company(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sr. Software Engineer", "senior software engineer"),
        ("SWE II (Remote)", "software engineer ii"),
        ("Data Analyst - Req 12345", "data analyst"),
    ],
)
def test_normalize_title_expands_abbreviations(raw, expected):
    assert normalize_title(raw) == expected


def test_normalize_location_canonicalizes_country():
    assert normalize_location("Austin, TX, USA") == "austin, tx, united states"


def test_seniority_level_orders_titles():
    assert seniority_level("Junior Developer") < seniority_level("Senior Developer")
    assert seniority_level("Director of Engineering") > seniority_level("Staff Engineer")
    assert seniority_level("Software Engineer") is None


def test_title_similarity_is_order_insensitive():
    assert title_similarity("Senior Data Engineer", "Data Engineer, Senior") > 0.8
    assert title_similarity("Data Engineer", "Registered Nurse") < 0.3


def test_token_overlap_bounds():
    assert token_overlap("data engineer", "data engineer") == 1.0
    assert token_overlap("", "data engineer") == 0.0


def test_content_hash_is_stable_across_formatting():
    assert content_hash("Acme  Inc", "Data Engineer") == content_hash("acme inc", "data engineer")
    assert content_hash("Acme", "Data Engineer") != content_hash("Acme", "Data Analyst")
