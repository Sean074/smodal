"""Smoke tests for core.brand.

`brand.py` is small (constants + a Streamlit page header). These tests pin the
public constants and verify `page_header()` is callable without raising when
Streamlit calls are stubbed — enough to catch accidental breakage during
refactors or the modal_analysis -> smodal rename.
"""

from __future__ import annotations


def test_constants_exposed():
    """APP_NAME and TAGLINE are importable and non-empty."""
    from core import brand

    assert isinstance(brand.APP_NAME, str) and brand.APP_NAME
    assert isinstance(brand.TAGLINE, str) and brand.TAGLINE


def test_app_name_is_smodal():
    """APP_NAME pins the user-facing application name.

    Update this test deliberately if the app is ever renamed — that change
    should be conscious, not an accidental string edit.
    """
    from core import brand

    assert brand.APP_NAME == "smodal"


def test_page_header_runs(monkeypatch):
    """page_header() invokes st.caption and st.markdown without raising."""
    import core.brand as brand

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(brand.st, "caption", lambda msg: calls.append(("caption", msg)))
    monkeypatch.setattr(brand.st, "markdown", lambda msg: calls.append(("markdown", msg)))

    brand.page_header()

    assert any(kind == "caption" and brand.APP_NAME in msg for kind, msg in calls), (
        "page_header() should emit a caption containing APP_NAME"
    )
    assert any(kind == "markdown" for kind, _ in calls), "page_header() should emit a markdown divider"
