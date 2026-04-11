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
from parser.sqlite_parser import parse_sqlite

__all__ = [
    "BaseParser",
    "HTMLExportParser",
    "MarkdownExportParser",
    "TXTExportParser",
    "detect_devices",
    "get_parser_for_extension",
    "normalize",
    "normalize_chapter",
    "parse_sqlite",
]
