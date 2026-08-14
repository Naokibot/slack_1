from pathlib import Path

from kosen_bot.jma import (
    INTENSITY_RANK,
    format_earthquake,
    parse_earthquake_xml,
    parse_shizuoka_warning_xml,
    qualifies_earthquake,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_earthquake_threshold():
    info4 = parse_earthquake_xml(load("earthquake_4.xml"))
    info5 = parse_earthquake_xml(load("earthquake_5lower.xml"))
    info6 = parse_earthquake_xml(load("earthquake_6lower.xml"))
    assert info4 is not None and not qualifies_earthquake(info4)
    assert info5 is not None and qualifies_earthquake(info5)
    assert info6 is not None and qualifies_earthquake(info6)
    assert info5.strong_areas["5-"] == ("静岡市",)
    assert "津波の心配はありません" in (info5.tsunami_text or "")
    assert "震度5弱" in format_earthquake(info5)
    assert INTENSITY_RANK["6-"] > INTENSITY_RANK["5+"]


def test_shizuoka_warning_filters_notice_and_other_prefecture():
    report = parse_shizuoka_warning_xml(load("shizuoka_warning.xml"))
    assert report is not None
    assert {(x.alert_name, x.area_name, x.status) for x in report.transitions} == {
        ("大雨警報", "静岡市", "発表"),
        ("大雨警報", "焼津市", "継続"),
    }
    assert parse_shizuoka_warning_xml(load("aichi_warning.xml")) is None


def test_all_strong_intensity_codes_qualify():
    from datetime import datetime
    from kosen_bot.jma import EarthquakeInfo
    from kosen_bot.timeutil import JST

    for intensity in ("5-", "5+", "6-", "6+", "7"):
        info = EarthquakeInfo(
            event_id="test",
            report_time=None,
            origin_time=datetime(2026, 8, 14, 13, 24, tzinfo=JST),
            hypocenter="test",
            magnitude="M5.0",
            depth="10km",
            max_intensity=intensity,
            strong_areas={intensity: ("test city",)},
            tsunami_text=None,
        )
        assert qualifies_earthquake(info)


def test_special_warning_is_included():
    xml = load("shizuoka_warning.xml").replace("大雨警報".encode(), "大雨特別警報".encode())
    report = parse_shizuoka_warning_xml(xml)
    assert report is not None
    assert any(item.alert_name == "大雨特別警報" for item in report.transitions)
