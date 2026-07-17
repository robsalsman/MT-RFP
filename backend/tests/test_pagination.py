"""SoQL pagination: fetch_all must walk $offset until a short page."""
from unittest.mock import patch

from app import soda


def _fake_dataset(n_rows):
    return [{"application_number": str(i)} for i in range(n_rows)]


def _fake_get_json(dataset_id, params, use_cache=True, _rows_holder=None):
    rows = _rows_holder
    offset, limit = params["$offset"], params["$limit"]
    return rows[offset:offset + limit]


def test_paginates_multiple_pages():
    rows = _fake_dataset(2500)
    calls = []

    def fake(dataset_id, params, use_cache=True):
        calls.append(dict(params))
        return _fake_get_json(dataset_id, params, _rows_holder=rows)

    with patch.object(soda, "get_json", side_effect=fake):
        out = soda.fetch_all("x", where="1=1", page_size=1000)
    assert len(out) == 2500
    assert [c["$offset"] for c in calls] == [0, 1000, 2000]
    assert out[0]["application_number"] == "0"
    assert out[-1]["application_number"] == "2499"


def test_single_short_page_stops_immediately():
    rows = _fake_dataset(10)
    calls = []

    def fake(dataset_id, params, use_cache=True):
        calls.append(dict(params))
        return _fake_get_json(dataset_id, params, _rows_holder=rows)

    with patch.object(soda, "get_json", side_effect=fake):
        out = soda.fetch_all("x", where="1=1", page_size=1000)
    assert len(out) == 10
    assert len(calls) == 1


def test_exact_page_boundary_makes_one_extra_call():
    rows = _fake_dataset(1000)

    def fake(dataset_id, params, use_cache=True):
        return _fake_get_json(dataset_id, params, _rows_holder=rows)

    with patch.object(soda, "get_json", side_effect=fake):
        out = soda.fetch_all("x", where="1=1", page_size=1000)
    assert len(out) == 1000
