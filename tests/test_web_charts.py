"""The SVG charts: shapes, the target line, ranges and the empty state."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from price_alerts.web.charts import price_chart, sparkline, window
from price_alerts.web.model import Point

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def pts(*pairs):
    return [Point(NOW - timedelta(days=days), Decimal(price)) for days, price in pairs]


def test_chart_has_one_marker_per_price_with_a_tooltip():
    svg = price_chart(pts((20, "59.99"), (10, "54.99"), (2, "49.50")), NOW, currency="GBP", target=None, name="Kettle")
    assert svg.count("<circle") == 3
    assert "£54.99 · 11 Oct 2026, 12:00 UTC" in svg
    assert 'role="img"' in svg and "now £49.50" in svg


def test_target_line_is_drawn_and_included_in_the_scale():
    svg = price_chart(pts((5, "100")), NOW, currency="USD", target=Decimal("60"), name="X")
    assert "Target $60.00" in svg and "stroke-dasharray" in svg
    assert "$60" in svg  # the y axis reaches down to the target


def test_markers_at_or_below_target_are_green():
    svg = price_chart(pts((9, "80"), (1, "55")), NOW, currency="USD", target=Decimal("60"), name="X")
    assert svg.count('stroke="#2f7d4f"') >= 1


def test_a_single_price_still_draws_a_line_to_now():
    svg = price_chart(pts((0, "10")), NOW, currency=None, target=None, name="X")
    assert svg.count("<circle") == 1 and "<path" in svg


def test_empty_history_shows_a_message_not_an_empty_chart():
    svg = price_chart([], NOW, currency=None, target=None, name="X")
    assert "No price recorded yet" in svg and "<circle" not in svg


def test_text_is_escaped():
    svg = price_chart(pts((1, "5")), NOW, currency=None, target=None, name='<script>"x"</script>')
    assert "<script>" not in svg


def test_ranges_keep_the_price_that_was_in_force_at_the_start():
    points = pts((40, "10"), (20, "8"), (3, "7"))
    seven = window(points, NOW, "7d")
    assert [str(p.price) for p in seven] == ["8", "7"]  # 8 was in force when the 7-day window began
    assert seven[0].when == NOW - timedelta(days=7)
    assert len(window(points, NOW, "all")) == 3


def test_sparkline_colour_follows_the_trend():
    assert "#2f7d4f" in sparkline(pts((9, "10"), (1, "8")), NOW)   # cheaper: green
    assert "#b42318" in sparkline(pts((9, "8"), (1, "10")), NOW)   # dearer: red
    assert "stroke-dasharray" in sparkline([], NOW)                # nothing yet: dashed baseline


def test_a_young_series_runs_a_flat_line_across_and_never_labels_the_future():
    svg = price_chart(pts((0, "51.77")), NOW, currency="GBP", target=None, name="X")
    assert svg.count("<circle") == 1
    assert 'M68 ' in svg and ' H732' in svg  # starts at the left edge of the plot, ends at the right edge
    assert "22 Oct" not in svg  # the axis runs a day past "now", but only past labels are drawn
    spark = sparkline(pts((0, "51.77")), NOW)
    assert 'M4 ' in spark and ' H128' in spark
