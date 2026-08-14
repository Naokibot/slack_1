from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import logging
import time
from typing import Callable, Iterable

from defusedxml import ElementTree as ET
import httpx

from .db import Database
from .timeutil import JST, now_jst

LOGGER = logging.getLogger(__name__)

JMA_EQ_FEED = "https://www.data.jma.go.jp/developer/xml/feed/eqvol.xml"
JMA_EXTRA_FEED = "https://www.data.jma.go.jp/developer/xml/feed/extra.xml"
JMA_EQ_LONG_FEED = "https://www.data.jma.go.jp/developer/xml/feed/eqvol_l.xml"
JMA_EXTRA_LONG_FEED = "https://www.data.jma.go.jp/developer/xml/feed/extra_l.xml"

INTENSITY_RANK = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5-": 5,
    "5+": 6,
    "6-": 7,
    "6+": 8,
    "7": 9,
}
INTENSITY_JA = {
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "5-": "5弱",
    "5+": "5強",
    "6-": "6弱",
    "6+": "6強",
    "7": "7",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def children_named(element: ET.Element, name: str) -> Iterable[ET.Element]:
    return (child for child in list(element) if local_name(child.tag) == name)


def first_child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next(children_named(element, name), None)


def first_descendant(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element.iter() if local_name(item.tag) == name), None)


def text_of(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def descendant_text(element: ET.Element, name: str) -> str | None:
    return text_of(first_descendant(element, name))


def parse_jma_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(JST)


@dataclass(frozen=True)
class FeedEntry:
    entry_id: str
    title: str
    updated: datetime | None
    url: str


def parse_atom_feed(xml_bytes: bytes) -> list[FeedEntry]:
    root = ET.fromstring(xml_bytes)
    entries: list[FeedEntry] = []
    for entry in (item for item in root.iter() if local_name(item.tag) == "entry"):
        entry_id = descendant_text(entry, "id") or ""
        title = descendant_text(entry, "title") or ""
        updated = parse_jma_datetime(descendant_text(entry, "updated"))
        url = ""
        for link in (item for item in entry.iter() if local_name(item.tag) == "link"):
            href = link.attrib.get("href", "")
            if href.endswith(".xml"):
                url = href
                break
        if entry_id and url:
            entries.append(FeedEntry(entry_id=entry_id, title=title, updated=updated, url=url))
    entries.sort(key=lambda item: item.updated or datetime.min.replace(tzinfo=JST))
    return entries


@dataclass(frozen=True)
class EarthquakeInfo:
    event_id: str
    report_time: datetime | None
    origin_time: datetime | None
    hypocenter: str | None
    magnitude: str | None
    depth: str | None
    max_intensity: str
    strong_areas: dict[str, tuple[str, ...]]
    tsunami_text: str | None

    @property
    def fingerprint(self) -> str:
        source = repr((self.max_intensity, self.magnitude, self.depth, self.strong_areas, self.tsunami_text))
        return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _earthquake_observation(root: ET.Element) -> ET.Element | None:
    intensity = next((item for item in root.iter() if local_name(item.tag) == "Intensity"), None)
    if intensity is None:
        return None
    return next((item for item in intensity.iter() if local_name(item.tag) == "Observation"), None)


def _extract_strong_areas(observation: ET.Element) -> dict[str, tuple[str, ...]]:
    by_intensity: dict[str, set[str]] = defaultdict(set)
    for city in (item for item in observation.iter() if local_name(item.tag) == "City"):
        name = descendant_text(city, "Name")
        intensity = descendant_text(city, "MaxInt")
        if name and intensity and INTENSITY_RANK.get(intensity, 0) >= INTENSITY_RANK["5-"]:
            by_intensity[intensity].add(name)

    if not by_intensity:
        for area in (item for item in observation.iter() if local_name(item.tag) == "Area"):
            name = descendant_text(area, "Name")
            intensity = descendant_text(area, "MaxInt")
            if name and intensity and INTENSITY_RANK.get(intensity, 0) >= INTENSITY_RANK["5-"]:
                by_intensity[intensity].add(name)

    return {
        intensity: tuple(sorted(names))
        for intensity, names in sorted(by_intensity.items(), key=lambda item: INTENSITY_RANK.get(item[0], 0), reverse=True)
    }


def parse_earthquake_xml(xml_bytes: bytes) -> EarthquakeInfo | None:
    root = ET.fromstring(xml_bytes)
    control = first_child(root, "Control")
    title = descendant_text(control if control is not None else root, "Title") or ""
    if "震度" not in title and "地震" not in title:
        return None

    head = first_child(root, "Head")
    if head is None:
        head = first_descendant(root, "Head")
    head_or_root = head if head is not None else root
    event_id = descendant_text(head_or_root, "EventID")
    observation = _earthquake_observation(root)
    if not event_id or observation is None:
        return None
    max_intensity = descendant_text(observation, "MaxInt")
    if not max_intensity:
        return None

    earthquake = next((item for item in root.iter() if local_name(item.tag) == "Earthquake"), None)
    origin_time = parse_jma_datetime(descendant_text(earthquake, "OriginTime")) if earthquake is not None else None
    hypocenter = None
    depth = None
    magnitude = None
    if earthquake is not None:
        hypocenter_node = first_descendant(earthquake, "Hypocenter")
        area = first_descendant(hypocenter_node, "Area") if hypocenter_node is not None else None
        hypocenter = descendant_text(area, "Name") if area is not None else None
        coordinate = first_descendant(area, "Coordinate") if area is not None else None
        if coordinate is not None:
            depth = coordinate.attrib.get("description") or None
        magnitude_node = first_descendant(earthquake, "Magnitude")
        if magnitude_node is not None:
            magnitude = magnitude_node.attrib.get("description") or text_of(magnitude_node)

    tsunami_candidates: list[str] = []
    for item in root.iter():
        if local_name(item.tag) in {"Text", "VarComment"}:
            value = text_of(item)
            if value and "津波" in value:
                tsunami_candidates.append(value)
    tsunami_text = tsunami_candidates[0] if tsunami_candidates else None

    report_time = parse_jma_datetime(descendant_text(head_or_root, "ReportDateTime"))
    return EarthquakeInfo(
        event_id=event_id,
        report_time=report_time,
        origin_time=origin_time,
        hypocenter=hypocenter,
        magnitude=magnitude,
        depth=depth,
        max_intensity=max_intensity,
        strong_areas=_extract_strong_areas(observation),
        tsunami_text=tsunami_text,
    )


def qualifies_earthquake(info: EarthquakeInfo) -> bool:
    return INTENSITY_RANK.get(info.max_intensity, 0) >= INTENSITY_RANK["5-"]


def format_earthquake(info: EarthquakeInfo, updated: bool = False) -> str:
    heading = "🔄 *地震情報が更新されました*" if updated else "🚨 *地震情報*"
    lines = [heading, "", f"最大震度：{INTENSITY_JA.get(info.max_intensity, info.max_intensity)}"]
    if info.origin_time:
        lines.append(f"発生時刻：{info.origin_time:%Y年%m月%d日 %H:%M}")
    if info.hypocenter:
        lines.append(f"震源地：{info.hypocenter}")
    if info.magnitude:
        lines.append(f"マグニチュード：{info.magnitude}")
    if info.depth:
        lines.append(f"深さ：{info.depth}")
    for intensity, areas in info.strong_areas.items():
        lines.extend(["", f"*震度{INTENSITY_JA.get(intensity, intensity)}*：", *[f"・{area}" for area in areas]])
    if info.tsunami_text:
        lines.extend(["", f"津波情報：{info.tsunami_text}"])
    lines.extend(["", "情報源：気象庁"])
    return "\n".join(lines)


@dataclass(frozen=True)
class WarningTransition:
    alert_name: str
    area_name: str
    status: str


@dataclass(frozen=True)
class WarningReport:
    report_time: datetime | None
    transitions: tuple[WarningTransition, ...]


def _is_shizuoka_report(root: ET.Element) -> bool:
    offices = [
        descendant_text(root, "PublishingOffice") or "",
        descendant_text(root, "EditorialOffice") or "",
    ]
    if any("静岡" in value for value in offices):
        return True
    for area in (item for item in root.iter() if local_name(item.tag) == "Area"):
        if descendant_text(area, "Name") == "静岡県":
            return True
    return False


def _is_warning_name(name: str) -> bool:
    return "警報" in name and "注意報" not in name and "警報級" not in name


def parse_shizuoka_warning_xml(xml_bytes: bytes) -> WarningReport | None:
    root = ET.fromstring(xml_bytes)
    control = first_child(root, "Control")
    control_title = descendant_text(control if control is not None else root, "Title") or ""
    if "警報" not in control_title and "注意報" not in control_title:
        return None
    if not _is_shizuoka_report(root):
        return None

    transitions: list[WarningTransition] = []
    for warning in (item for item in root.iter() if local_name(item.tag) == "Warning"):
        warning_type = warning.attrib.get("type", "")
        if warning_type and "気象" not in warning_type and "警報" not in warning_type:
            continue
        for item in children_named(warning, "Item"):
            area_node = first_child(item, "Area")
            area_name = descendant_text(area_node, "Name") if area_node is not None else None
            if not area_name:
                continue
            for kind in children_named(item, "Kind"):
                name = descendant_text(kind, "Name")
                status = descendant_text(kind, "Status") or ""
                if name and _is_warning_name(name) and status in {"発表", "継続", "解除", "切替"}:
                    transitions.append(WarningTransition(name, area_name, status))

    if not transitions:
        return None
    head = first_child(root, "Head")
    if head is None:
        head = first_descendant(root, "Head")
    head_or_root = head if head is not None else root
    return WarningReport(
        report_time=parse_jma_datetime(descendant_text(head_or_root, "ReportDateTime")),
        transitions=tuple(transitions),
    )


def format_warning_changes(report_time: datetime | None, new: dict[str, list[str]], released: dict[str, list[str]]) -> str:
    special = any("特別警報" in name for name in new)
    heading = "🚨🚨 *静岡県 特別警報* 🚨🚨" if special else "⚠️ *静岡県 防災警報更新*"
    lines = [heading]
    if report_time:
        lines.extend(["", f"発表時刻：{report_time:%Y年%m月%d日 %H:%M}"])
    if new:
        lines.extend(["", "*新規・発表*："])
        for name, areas in sorted(new.items()):
            lines.append(f"{name}：")
            lines.extend(f"・{area}" for area in sorted(set(areas)))
    if released:
        lines.extend(["", "*解除*："])
        for name, areas in sorted(released.items()):
            lines.append(f"{name}：")
            lines.extend(f"・{area}" for area in sorted(set(areas)))
    lines.extend(["", "情報源：気象庁", "※安全判断はこのBotだけに依存せず、気象庁・自治体の最新情報を確認してください。"])
    return "\n".join(lines)


class JmaClient:
    def __init__(self, timeout: float = 15.0):
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": "kosen-slack-bot/0.1 (+personal disaster notifier)"},
        )

    def get(self, url: str) -> bytes:
        response = self.client.get(url)
        response.raise_for_status()
        return response.content

    def close(self) -> None:
        self.client.close()


class JmaMonitor:
    def __init__(
        self,
        db: Database,
        post_earthquake: Callable[[str], None],
        post_warning: Callable[[str], None],
        post_admin: Callable[[str], None],
        client: JmaClient | None = None,
        max_backfill_hours: int | None = None,
    ):
        self.db = db
        self.post_earthquake = post_earthquake
        self.post_warning = post_warning
        self.post_admin = post_admin
        self.client = client or JmaClient()
        self.max_backfill_hours = max_backfill_hours
        self.failure_since: datetime | None = None
        self.failure_announced = False
        self.last_success: datetime | None = None

    def poll(self, *, include_long_feed: bool = False) -> None:
        feeds = [(JMA_EQ_FEED, "earthquake"), (JMA_EXTRA_FEED, "warning")]
        if include_long_feed:
            feeds.extend([(JMA_EQ_LONG_FEED, "earthquake"), (JMA_EXTRA_LONG_FEED, "warning")])
        try:
            for feed_url, category in feeds:
                self._process_feed(feed_url, category)
        except Exception:
            self._record_failure()
            raise
        else:
            self._record_success()

    def _process_feed(self, feed_url: str, category: str) -> None:
        for entry in parse_atom_feed(self.client.get(feed_url)):
            if self.db.has_processed_jma_entry(entry.entry_id):
                continue
            if (
                self.max_backfill_hours is not None
                and entry.updated is not None
                and entry.updated < now_jst() - timedelta(hours=self.max_backfill_hours)
            ):
                self.db.mark_jma_entry_processed(entry.entry_id, category, now_jst())
                continue
            try:
                if category == "earthquake":
                    self._process_earthquake_entry(entry)
                else:
                    self._process_warning_entry(entry)
            except Exception:
                LOGGER.exception("JMA entry processing failed: %s", entry.entry_id)
                raise
            else:
                self.db.mark_jma_entry_processed(entry.entry_id, category, now_jst())

    def _process_earthquake_entry(self, entry: FeedEntry) -> None:
        if "震度" not in entry.title and "地震" not in entry.title:
            return
        info = parse_earthquake_xml(self.client.get(entry.url))
        if info is None:
            return
        existing = self.db.get_earthquake_event(info.event_id)
        was_qualified = existing is not None and INTENSITY_RANK.get(str(existing["max_intensity"]), 0) >= INTENSITY_RANK["5-"]
        changed = existing is None or str(existing["fingerprint"]) != info.fingerprint
        if qualifies_earthquake(info) and (not was_qualified or changed):
            self.post_earthquake(format_earthquake(info, updated=was_qualified))
        self.db.upsert_earthquake_event(
            info.event_id,
            info.max_intensity,
            info.magnitude,
            info.tsunami_text,
            info.fingerprint,
            now_jst(),
        )

    def _process_warning_entry(self, entry: FeedEntry) -> None:
        if "警報" not in entry.title and "注意報" not in entry.title:
            return
        report = parse_shizuoka_warning_xml(self.client.get(entry.url))
        if report is None:
            return
        new: dict[str, list[str]] = defaultdict(list)
        released: dict[str, list[str]] = defaultdict(list)
        for transition in report.transitions:
            was_active = self.db.get_warning_active(transition.alert_name, transition.area_name)
            active_now = transition.status != "解除"
            if active_now and not was_active:
                new[transition.alert_name].append(transition.area_name)
            elif not active_now and was_active:
                released[transition.alert_name].append(transition.area_name)
            self.db.set_warning_active(transition.alert_name, transition.area_name, active_now, now_jst())
        if new or released:
            self.post_warning(format_warning_changes(report.report_time, new, released))

    def _record_failure(self) -> None:
        current = now_jst()
        if self.failure_since is None:
            self.failure_since = current
        elapsed = (current - self.failure_since).total_seconds()
        if elapsed >= 300 and not self.failure_announced:
            self.post_admin("⚠️ *防災情報取得エラー*\n\n気象庁の情報を5分以上取得できていません。Botは再試行を続けています。")
            self.failure_announced = True

    def _record_success(self) -> None:
        self.last_success = now_jst()
        if self.failure_announced:
            self.post_admin("✅ 防災情報取得が復旧しました。")
        self.failure_since = None
        self.failure_announced = False
