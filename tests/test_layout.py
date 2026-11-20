from growbanner import layout as L
from growbanner.layout import compute_layout


def fake(text, size, bold):  # 0.5 em per character, deterministic
    return len(text) * size * 0.5


def test_short_title_one_line_default_size():
    lay = compute_layout("Hi", "May 1 | 6pm", "Braddock | Free", False, fake)
    assert [r.text for r in lay.rows if r.bold] == ["Hi"]
    assert lay.title_size == 68 and lay.info_size == 58


def test_banner_geometry():
    lay = compute_layout("Hi", "May 1 | 6pm", "Braddock | Free", False, fake)
    expected_h = 36 + 28 + 1 * 102 + 2 * 87 - 16
    assert lay.height == expected_h and lay.y0 == 940 - expected_h
    assert lay.width == int(max(len("Braddock | Free") * 58 * 0.5, 2 * 34) + 40 + 124)


def test_long_title_wraps_to_two_balanced_lines():
    t = "word " * 14
    lay = compute_layout(t.strip(), "d", "l", False, fake)
    lines = [r.text for r in lay.rows if r.bold]
    assert len(lines) == 2 and abs(len(lines[0]) - len(lines[1])) <= 5


def test_nowrap_keeps_one_line_and_shrinks():
    t = "x" * 60
    lay = compute_layout(t, "d", "l", True, fake)
    assert len([r for r in lay.rows if r.bold]) == 1
    assert 40 <= lay.title_size < 68


def test_never_shrinks_below_minimum_and_width_capped():
    lay = compute_layout("x" * 500, "d", "l", True, fake)
    assert lay.title_size == L.MIN_TITLE_SIZE and lay.width == L.CANVAS_W


def test_blank_cost_and_time_rows_omitted():
    lay = compute_layout("T", "", "Virtual", False, fake)
    assert [r.text for r in lay.rows] == ["T", "Virtual"]
