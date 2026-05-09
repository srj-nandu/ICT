from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "PROJECT_REPORT.md"
TARGET = ROOT / "PROJECT_REPORT.pdf"

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_LEFT = 56
MARGIN_RIGHT = 56
MARGIN_TOP = 58
MARGIN_BOTTOM = 54
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

FONT_REGULAR = "helv"
FONT_BOLD = "hebo"
FONT_MONO = "cour"

INK = (0.11, 0.12, 0.13)
MUTED = (0.37, 0.41, 0.45)
TEAL = (0.04, 0.38, 0.35)
TEAL_LIGHT = (0.88, 0.96, 0.95)
LINE = (0.78, 0.82, 0.84)
SOFT = (0.96, 0.97, 0.97)


def strip_markdown(text: str) -> str:
    text = text.replace("**", "")
    text = text.replace("`", "")
    text = text.replace("–", "-").replace("—", "-")
    return text.strip()


def split_table_row(line: str) -> list[str]:
    return [strip_markdown(cell) for cell in line.strip().strip("|").split("|")]


def is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line.strip()))


def textbox_height(text: str, width: float, size: float, line_height: float = 1.28) -> float:
    clean = strip_markdown(text)
    if not clean:
        return size * line_height
    chars_per_line = max(12, int(width / (size * 0.48)))
    lines = 0
    for paragraph in clean.splitlines() or [""]:
        lines += max(1, (len(paragraph) // chars_per_line) + 1)
    return lines * size * line_height


def wrap_text(text: str, width: float, size: float) -> list[str]:
    clean = strip_markdown(text)
    chars_per_line = max(18, int(width / (size * 0.47)))
    wrapped: list[str] = []
    for paragraph in clean.splitlines() or [""]:
        wrapped.extend(textwrap.wrap(paragraph, width=chars_per_line) or [""])
    return wrapped


class ReportPdf:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page: fitz.Page | None = None
        self.y = MARGIN_TOP
        self.current_chapter = "Careermitra"

    def new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        self.y = MARGIN_TOP

    def ensure(self, height: float) -> None:
        if self.page is None or self.y + height > PAGE_HEIGHT - MARGIN_BOTTOM:
            self.new_page()

    def rect(self, x0: float, y0: float, x1: float, y1: float, fill: tuple[float, float, float] | None = None) -> None:
        assert self.page is not None
        self.page.draw_rect(
            fitz.Rect(x0, y0, x1, y1),
            color=LINE,
            fill=fill,
            width=0.6,
        )

    def text_box(
        self,
        text: str,
        x: float,
        y: float,
        width: float,
        height: float,
        size: float,
        font: str = FONT_REGULAR,
        color: tuple[float, float, float] = INK,
        align: int = fitz.TEXT_ALIGN_LEFT,
    ) -> None:
        assert self.page is not None
        self.page.insert_textbox(
            fitz.Rect(x, y, x + width, y + height),
            strip_markdown(text),
            fontsize=size,
            fontname=font,
            color=color,
            align=align,
        )

    def text_line(
        self,
        text: str,
        x: float,
        y: float,
        size: float,
        font: str = FONT_REGULAR,
        color: tuple[float, float, float] = INK,
    ) -> None:
        assert self.page is not None
        self.page.insert_text(
            (x, y),
            strip_markdown(text),
            fontsize=size,
            fontname=font,
            color=color,
        )

    def centered_line(
        self,
        text: str,
        y: float,
        size: float,
        font: str = FONT_REGULAR,
        color: tuple[float, float, float] = INK,
    ) -> None:
        assert self.page is not None
        text = strip_markdown(text)
        width = fitz.get_text_length(text, fontname=font, fontsize=size)
        self.text_line(text, (PAGE_WIDTH - width) / 2, y, size, font, color)

    def paragraph(self, text: str) -> None:
        lines = wrap_text(text, CONTENT_WIDTH, 10.7)
        line_height = 15.0
        self.ensure(line_height + 8)
        for line in lines:
            self.ensure(line_height + 8)
            self.text_line(line, MARGIN_LEFT, self.y + 10.7, 10.7)
            self.y += line_height
        self.y += 7

    def bullet(self, text: str) -> None:
        item = strip_markdown(text.lstrip("- ").strip())
        width = CONTENT_WIDTH - 24
        lines = wrap_text(item, width, 10.5)
        line_height = 14.5
        self.ensure(line_height + 5)
        assert self.page is not None
        self.page.draw_circle((MARGIN_LEFT + 6, self.y + 7), 1.7, color=TEAL, fill=TEAL)
        for line in lines:
            self.ensure(line_height + 5)
            self.text_line(line, MARGIN_LEFT + 18, self.y + 10.5, 10.5)
            self.y += line_height
        self.y += 3

    def heading(self, text: str, level: int) -> None:
        text = strip_markdown(text)
        if level == 1:
            if self.page is not None and self.y > MARGIN_TOP + 35:
                self.new_page()
            self.current_chapter = text
            self.ensure(64)
            assert self.page is not None
            self.page.draw_rect(
                fitz.Rect(MARGIN_LEFT, self.y, PAGE_WIDTH - MARGIN_RIGHT, self.y + 38),
                color=TEAL,
                fill=TEAL,
                width=0,
            )
            self.text_line(text.upper(), MARGIN_LEFT + 14, self.y + 25, 14.5, FONT_BOLD, (1, 1, 1))
            self.y += 54
            return

        if level == 2:
            self.ensure(42)
            self.text_line(text.upper(), MARGIN_LEFT, self.y + 16, 12.8, FONT_BOLD, TEAL)
            assert self.page is not None
            self.page.draw_line((MARGIN_LEFT, self.y + 23), (PAGE_WIDTH - MARGIN_RIGHT, self.y + 23), color=TEAL, width=0.8)
            self.y += 34
            return

        self.ensure(26)
        self.text_line(text, MARGIN_LEFT, self.y + 14, 11.3, FONT_BOLD)
        self.y += 24

    def table(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        column_count = max(len(row) for row in rows)
        widths = self.column_widths(rows, column_count)
        x_positions = [MARGIN_LEFT]
        for width in widths[:-1]:
            x_positions.append(x_positions[-1] + width)

        for row_index, row in enumerate(rows):
            row = row + [""] * (column_count - len(row))
            heights = [
                textbox_height(cell, widths[col] - 10, 8.8 if row_index else 9.2, 1.18)
                for col, cell in enumerate(row)
            ]
            row_height = max(24, max(heights) + 12)
            self.ensure(row_height)
            fill = TEAL_LIGHT if row_index == 0 else (SOFT if row_index % 2 == 0 else (1, 1, 1))
            for col, cell in enumerate(row):
                x = x_positions[col]
                self.rect(x, self.y, x + widths[col], self.y + row_height, fill=fill)
                self.text_box(
                    cell,
                    x + 5,
                    self.y + 6,
                    widths[col] - 10,
                    row_height - 8,
                    9.2 if row_index == 0 else 8.8,
                    FONT_BOLD if row_index == 0 else FONT_REGULAR,
                    TEAL if row_index == 0 else INK,
                )
            self.y += row_height
        self.y += 12

    def column_widths(self, rows: list[list[str]], column_count: int) -> list[float]:
        if column_count == 2:
            return [CONTENT_WIDTH * 0.36, CONTENT_WIDTH * 0.64]
        if column_count == 3:
            return [CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.62, CONTENT_WIDTH * 0.20]
        return [CONTENT_WIDTH / column_count] * column_count

    def code_block(self, lines: list[str]) -> None:
        if not lines:
            return
        line_height = 10.8
        max_lines_per_page = int((PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM - 24) / line_height)
        index = 0
        while index < len(lines):
            chunk = lines[index : index + max_lines_per_page]
            height = len(chunk) * line_height + 18
            self.ensure(height)
            assert self.page is not None
            self.page.draw_rect(
                fitz.Rect(MARGIN_LEFT, self.y, PAGE_WIDTH - MARGIN_RIGHT, self.y + height),
                color=LINE,
                fill=(0.98, 0.98, 0.98),
                width=0.6,
            )
            y = self.y + 10
            for line in chunk:
                assert self.page is not None
                self.page.insert_text(
                    (MARGIN_LEFT + 10, y + 8.4),
                    line.replace("\t", "    ")[:104],
                    fontsize=8.4,
                    fontname=FONT_MONO,
                    color=INK,
                )
                y += line_height
            self.y += height + 12
            index += len(chunk)

    def image(self, alt_text: str, relative_path: str) -> None:
        image_path = (ROOT / relative_path).resolve()
        if not image_path.exists():
            self.paragraph(f"[Missing screenshot: {relative_path}]")
            return

        with ImageInfo(image_path) as info:
            max_width = CONTENT_WIDTH
            max_height = 270
            scale = min(max_width / info.width, max_height / info.height)
            draw_width = info.width * scale
            draw_height = info.height * scale

        needed = draw_height + 44
        self.ensure(needed)
        assert self.page is not None
        x = MARGIN_LEFT + (CONTENT_WIDTH - draw_width) / 2
        self.page.draw_rect(
            fitz.Rect(x - 4, self.y - 4, x + draw_width + 4, self.y + draw_height + 4),
            color=LINE,
            fill=(1, 1, 1),
            width=0.8,
        )
        self.page.insert_image(
            fitz.Rect(x, self.y, x + draw_width, self.y + draw_height),
            filename=str(image_path),
        )
        self.y += draw_height + 12
        self.text_box(alt_text, MARGIN_LEFT, self.y, CONTENT_WIDTH, 18, 9.2, FONT_BOLD, MUTED, fitz.TEXT_ALIGN_CENTER)
        self.y += 30

    def cover(self) -> None:
        self.new_page()
        assert self.page is not None
        self.page.draw_rect(
            fitz.Rect(42, 42, PAGE_WIDTH - 42, PAGE_HEIGHT - 42),
            color=TEAL,
            width=1.2,
        )
        self.page.draw_rect(
            fitz.Rect(52, 52, PAGE_WIDTH - 52, PAGE_HEIGHT - 52),
            color=LINE,
            width=0.6,
        )
        self.centered_line("CAREERMITRA", 148, 25, FONT_BOLD, TEAL)
        self.centered_line("RESUME SKILL GAP ANALYSIS SYSTEM", 188, 16, FONT_BOLD, INK)
        self.page.draw_line((132, 222), (PAGE_WIDTH - 132, 222), color=TEAL, width=1.0)
        self.centered_line("A project report submitted in partial fulfillment", 290, 12)
        self.centered_line("of the requirements for the certification of", 312, 12)
        self.centered_line("ADVANCED PYTHON", 356, 15, FONT_BOLD, TEAL)
        self.centered_line("Submitted by", 440, 12)
        self.centered_line("SOORAJ", 472, 15, FONT_BOLD)
        self.centered_line("May 2026", 624, 12)

    def finish(self) -> None:
        for index, page in enumerate(self.doc, start=1):
            if index > 1:
                page.insert_text(
                    (MARGIN_LEFT, 34),
                    "CAREERMITRA PROJECT REPORT",
                    fontsize=8.5,
                    fontname=FONT_BOLD,
                    color=MUTED,
                )
                page.draw_line((MARGIN_LEFT, 45), (PAGE_WIDTH - MARGIN_RIGHT, 45), color=LINE, width=0.6)
            footer = str(index)
            width = fitz.get_text_length(footer, fontname=FONT_REGULAR, fontsize=9)
            page.draw_line((MARGIN_LEFT, PAGE_HEIGHT - 42), (PAGE_WIDTH - MARGIN_RIGHT, PAGE_HEIGHT - 42), color=LINE, width=0.6)
            page.insert_text(
                ((PAGE_WIDTH - width) / 2, PAGE_HEIGHT - 27),
                footer,
                fontsize=9,
                fontname=FONT_REGULAR,
                color=MUTED,
            )
        self.doc.save(TARGET, garbage=4, deflate=True)
        print(f"Wrote {TARGET} ({self.doc.page_count} pages)")


def flush_paragraph(writer: ReportPdf, paragraph: list[str]) -> None:
    if paragraph:
        writer.paragraph(" ".join(paragraph))
        paragraph.clear()


class ImageInfo:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.pixmap: fitz.Pixmap | None = None
        self.width = 0
        self.height = 0

    def __enter__(self) -> "ImageInfo":
        self.pixmap = fitz.Pixmap(str(self.path))
        self.width = self.pixmap.width
        self.height = self.pixmap.height
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.pixmap = None


def render_body(writer: ReportPdf, markdown: str) -> None:
    skip_cover = True
    paragraph: list[str] = []
    table_rows: list[list[str]] = []
    code_lines: list[str] = []
    in_code = False
    started_body = False

    def flush_table() -> None:
        if table_rows:
            writer.table(table_rows.copy())
            table_rows.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()

        if skip_cover:
            if line.strip() == "---":
                skip_cover = False
            continue

        if not started_body:
            writer.new_page()
            started_body = True

        if line.startswith("```"):
            flush_paragraph(writer, paragraph)
            flush_table()
            if in_code:
                writer.code_block(code_lines.copy())
                code_lines.clear()
            in_code = not in_code
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_paragraph(writer, paragraph)
            flush_table()
            continue

        if line.strip() == "---":
            flush_paragraph(writer, paragraph)
            flush_table()
            writer.new_page()
            continue

        image_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", line.strip())
        if image_match:
            flush_paragraph(writer, paragraph)
            flush_table()
            writer.image(image_match.group(1), image_match.group(2))
            continue

        if line.strip().startswith("|"):
            flush_paragraph(writer, paragraph)
            if not is_separator_row(line):
                table_rows.append(split_table_row(line))
            continue

        flush_table()

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            flush_paragraph(writer, paragraph)
            writer.heading(heading_match.group(2), len(heading_match.group(1)))
            continue

        if line.lstrip().startswith("- "):
            flush_paragraph(writer, paragraph)
            writer.bullet(line)
            continue

        paragraph.append(line.strip())

    flush_paragraph(writer, paragraph)
    flush_table()
    if code_lines:
        writer.code_block(code_lines)


def main() -> int:
    if not SOURCE.exists():
        print(f"Missing source: {SOURCE}", file=sys.stderr)
        return 1

    writer = ReportPdf()
    writer.cover()
    render_body(writer, SOURCE.read_text(encoding="utf-8"))
    writer.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
