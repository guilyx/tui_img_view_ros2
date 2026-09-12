from __future__ import annotations

import numpy as np
import pytest

from tui_img_view.core.types import Frame
from tui_img_view.render.filters import FILTER_ORDER, FILTERS, apply_filters, next_filter
from tui_img_view.render.pipeline import Renderer


@pytest.fixture
def photo() -> np.ndarray:
    yy, xx = np.mgrid[0:24, 0:32]
    px = np.zeros((24, 32, 3), dtype=np.uint8)
    px[..., 0] = (xx * 8) % 256
    px[..., 1] = (yy * 10) % 256
    px[..., 2] = 40
    return px


@pytest.mark.parametrize("name", FILTER_ORDER)
def test_every_filter_keeps_shape_and_dtype(name, photo):
    out = apply_filters(photo, [name])
    assert out.shape == photo.shape and out.dtype == np.uint8
    assert out.flags["C_CONTIGUOUS"]
    assert FILTERS[name][1]  # has a description


def test_invert_and_gray_and_threshold(photo):
    inv = apply_filters(photo, ["invert"])
    assert np.array_equal(inv, 255 - photo)
    assert np.array_equal(apply_filters(inv, ["invert"]), photo)
    g = apply_filters(photo, ["gray"])
    assert np.array_equal(g[..., 0], g[..., 1]) and np.array_equal(g[..., 1], g[..., 2])
    t = apply_filters(photo, ["threshold"])
    assert set(np.unique(t)) <= {0, 255}


def test_filters_compose_in_order(photo):
    a = apply_filters(photo, ["gray", "invert"])
    b = apply_filters(apply_filters(photo, ["gray"]), ["invert"])
    assert np.array_equal(a, b)
    assert np.array_equal(apply_filters(photo, []), photo)
    with pytest.raises(KeyError):
        apply_filters(photo, ["gray", "nope"])


def test_next_filter_cycles_through_every_filter():
    seen = []
    active: list[str] = []
    for _ in range(len(FILTER_ORDER) + 1):
        active = next_filter(active)
        seen.append(tuple(active))
    assert seen[:-1] == [(n,) for n in FILTER_ORDER]
    assert seen[-1] == ()
    assert next_filter(["gray", "blur"]) == []  # a stack collapses to none


def test_renderer_filter_stack(photo):
    r = Renderer(filters=["gray"])
    assert r.filters == ("gray",)
    assert r.toggle_filter("invert") is True and r.filters == ("gray", "invert")
    assert r.toggle_filter("gray") is False and r.filters == ("invert",)
    with pytest.raises(KeyError):
        r.toggle_filter("nope")
    with pytest.raises(KeyError):
        Renderer(filters=["nope"])
    r.set_filters(["blur", "blur", "edges"])
    assert r.filters == ("blur", "edges")
    r.clear_filters()
    assert r.filters == ()
    assert r.cycle_filter() == ("gray",)


def test_renderer_applies_filters_to_output(photo):
    frame = Frame(photo)
    plain = Renderer("half").render(frame, (), 32, 12)
    inverted = Renderer("half", filters=["invert"]).render(frame, (), 32, 12)
    fg_plain = plain.get(16, 6)[1]
    fg_inv = inverted.get(16, 6)[1]
    assert fg_plain is not None and fg_inv is not None
    assert all(abs((255 - a) - b) <= 1 for a, b in zip(fg_plain, fg_inv, strict=True))
