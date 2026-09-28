"""
tests/unit/test_tool_registry.py — Unit tests for lib/tool_registry.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_tool_registry.py -v
# EXPECTED: All tests pass (no network, mocked booker)

Tests cover: build_tool_registry, extract_tool_call, invoke_tool error paths.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from tool_registry import build_tool_registry, extract_tool_call, invoke_tool


@pytest.fixture
def minimal_registry():
    async def boom(**kwargs):
        raise ValueError("simulated failure")

    async def ok(**kwargs):
        return {"result": "ok", "kwargs": kwargs}

    return {"boom": boom, "ok": ok}


# ── build_tool_registry ───────────────────────────────────────────────────────
def test_build_registry_has_expected_tools(mock_booker_success):
    import rag_lib as r
    index_holder = {"index": r.TfidfIndex(r.load_documents())}
    registry = build_tool_registry(index_holder, booker=mock_booker_success)
    expected = {"search_properties", "get_property", "answer_question", "hybrid_search", "book_site_visit"}
    assert expected.issubset(set(registry.keys()))


def test_hybrid_search_alias_same_as_answer_question(mock_booker_success):
    import rag_lib as r
    index_holder = {"index": r.TfidfIndex(r.load_documents())}
    registry = build_tool_registry(index_holder, booker=mock_booker_success)
    assert registry["hybrid_search"] is registry["answer_question"]


# ── extract_tool_call ─────────────────────────────────────────────────────────
def test_extract_valid_tool_call():
    text = '{"tool": "get_property", "args": {"property_id": "LAH-0001"}}'
    result = extract_tool_call(text)
    assert result == {"tool": "get_property", "args": {"property_id": "LAH-0001"}}


def test_extract_returns_none_for_plain_text():
    assert extract_tool_call("Ji sir, DHA Phase 6 available hai") is None


def test_extract_returns_none_for_missing_tool_key():
    text = '{"name": "get_property", "args": {}}'
    assert extract_tool_call(text) is None


def test_extract_returns_none_on_malformed_json():
    """Malformed JSON should be handled gracefully — return None, not raise."""
    result = extract_tool_call("{invalid json")
    assert result is None


def test_extract_with_book_site_visit():
    text = json.dumps({"tool": "book_site_visit", "args": {"property_id": "LAH-0001"}})
    result = extract_tool_call(text)
    assert result["tool"] == "book_site_visit"


# ── invoke_tool ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_invoke_tool_unknown_name(minimal_registry):
    result = await invoke_tool("does_not_exist", {}, minimal_registry)
    assert result["ok"] is False
    assert "unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_invoke_tool_raises_becomes_error(minimal_registry):
    result = await invoke_tool("boom", {}, minimal_registry)
    assert result["ok"] is False
    assert "ValueError" in result["error"]
    assert "simulated failure" in result["error"]


@pytest.mark.asyncio
async def test_invoke_tool_success(minimal_registry):
    result = await invoke_tool("ok", {"x": 1}, minimal_registry)
    assert result["ok"] is True
    assert result["result"]["result"] == "ok"


@pytest.mark.asyncio
async def test_invoke_tool_bad_args_type_error(minimal_registry):
    """Passing an unexpected keyword arg to a function that doesn't accept it."""
    async def strict_fn(x: int):
        return x

    reg = {"strict": strict_fn}
    result = await invoke_tool("strict", {"x": 1, "unexpected": 99}, reg)
    # TypeError should become {"ok": False, ...}
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_invoke_tool_never_raises():
    """invoke_tool must never propagate an exception to the caller."""
    async def always_crash(**kwargs):
        raise RuntimeError("complete meltdown")

    reg = {"crash": always_crash}
    try:
        result = await invoke_tool("crash", {}, reg)
        assert result["ok"] is False
    except Exception:
        pytest.fail("invoke_tool raised instead of returning error dict")


@pytest.mark.asyncio
async def test_invoke_get_property_real(db_conn):
    """invoke_tool with real get_property against real DB."""
    import rag_lib as r
    index_holder = {"index": r.TfidfIndex([])}
    booker = MagicMock()
    registry = build_tool_registry(index_holder, booker=booker)
    result = await invoke_tool("get_property", {"property_id": "LAH-0001"}, registry)
    assert result["ok"] is True
    assert result["result"]["property_id"] == "LAH-0001"


@pytest.mark.asyncio
async def test_invoke_get_property_not_found(db_conn):
    import rag_lib as r
    index_holder = {"index": r.TfidfIndex([])}
    booker = MagicMock()
    registry = build_tool_registry(index_holder, booker=booker)
    result = await invoke_tool("get_property", {"property_id": "LAH-9999"}, registry)
    assert result["ok"] is True
    assert result["result"] is None
