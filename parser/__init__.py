from parser.base import BaseParser
from parser.chapter_normalize import normalize_chapter
from parser.device_detection import detect_devices
from parser.export_parsers import (
    HTMLExportParser,
    MarkdownExportParser,
    TXTExportParser,
    get_parser_for_extension,
)
from parser.normalizer import normalize
from parser.sqlite_parser import (
    extract_progress_snapshots,
    extract_reading_sessions,
    extract_shelves,
    parse_sqlite,
)

__all__ = [
    "BaseParser",
    "HTMLExportParser",
    "MarkdownExportParser",
    "TXTExportParser",
    "detect_devices",
    "extract_progress_snapshots",
    "extract_reading_sessions",
    "extract_shelves",
    "get_parser_for_extension",
    "normalize",
    "normalize_chapter",
    "parse_sqlite",
]
