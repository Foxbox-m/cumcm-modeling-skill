#!/usr/bin/env python3
"""Render a paper PDF for page-flow and visual QA.

The script deliberately has a small dependency surface: PyMuPDF renders the
PDF and Pillow assembles color/gray contact sheets.  It writes only to the
caller-provided project QA directory and never changes the PDF or its source.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import math
from pathlib import Path
import sys


def _load_dependencies():
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("缺少 PyMuPDF：请安装 pymupdf") from exc
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError as exc:
        raise RuntimeError("缺少 Pillow：请安装 Pillow") from exc
    return fitz, Image, ImageDraw, ImageOps


def _positive_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是正数") from exc
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("必须是正数")
    return value


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是正整数") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return value


def _expected_outputs(page_count: int, pages_per_sheet: int) -> list[Path]:
    outputs: list[Path] = []
    for page_number in range(1, page_count + 1):
        outputs.append(Path("pages") / f"page-{page_number:03d}.png")
    for start in range(1, page_count + 1, pages_per_sheet):
        end = min(start + pages_per_sheet - 1, page_count)
        name = f"{start}-{end}.png"
        outputs.extend(
            (
                Path("contact") / f"color-pages-{name}",
                Path("contact") / f"gray-pages-{name}",
            )
        )
    return outputs


def _existing_output_conflicts(output_dir: Path, expected: list[Path]) -> list[Path]:
    return [relative for relative in expected if (output_dir / relative).exists()]


def _page_image(page, fitz, Image, dpi: float):
    scale = dpi / 72.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    with Image.open(BytesIO(pixmap.tobytes("png"))) as rendered:
        return rendered.convert("RGB")


def _contact_sheet(images, page_numbers, Image, ImageDraw, ImageOps):
    columns = 3
    rows = max(1, math.ceil(len(images) / columns))
    tile_width, tile_height = 320, 460
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "#dddddd")
    for index, (image, page_number) in enumerate(zip(images, page_numbers)):
        thumbnail = ImageOps.contain(image, (300, 424), method=Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (tile_width, tile_height), "white")
        x = (tile_width - thumbnail.width) // 2
        tile.paste(thumbnail, (x, 28))
        ImageDraw.Draw(tile).text((10, 7), f"Page {page_number}", fill="black")
        sheet.paste(tile, ((index % columns) * tile_width, (index // columns) * tile_height))
    return sheet


def render(pdf_path: Path, output_dir: Path, dpi: float = 160.0,
           pages_per_sheet: int = 6, overwrite: bool = False) -> int:
    if not pdf_path.is_file():
        raise ValueError(f"PDF 文件不存在：{pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("输入文件必须是 PDF")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"输出目录不是目录：{output_dir}")

    fitz, Image, ImageDraw, ImageOps = _load_dependencies()
    try:
        document = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError(f"无法打开 PDF：{exc}") from exc
    try:
        page_count = len(document)
        if page_count <= 0:
            raise ValueError("PDF 不含页面")
        expected = _expected_outputs(page_count, pages_per_sheet)
        if output_dir.exists() and not overwrite:
            conflicts = _existing_output_conflicts(output_dir, expected)
            if conflicts:
                listed = "、".join(str(path) for path in conflicts[:8])
                suffix = "等" if len(conflicts) > 8 else ""
                raise FileExistsError(
                    f"输出目录含同名既有 QA 文件：{listed}{suffix}；如需覆盖请显式使用 --overwrite"
                )
        output_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = output_dir / "pages"
        contact_dir = output_dir / "contact"
        pages_dir.mkdir(exist_ok=True)
        contact_dir.mkdir(exist_ok=True)

        for page_index, page in enumerate(document):
            image = _page_image(page, fitz, Image, dpi)
            try:
                image.save(pages_dir / f"page-{page_index + 1:03d}.png")
            finally:
                image.close()

        for start in range(0, page_count, pages_per_sheet):
            end = min(start + pages_per_sheet, page_count)
            images = []
            try:
                for page_number in range(start + 1, end + 1):
                    with Image.open(pages_dir / f"page-{page_number:03d}.png") as stored:
                        images.append(stored.convert("RGB"))
                numbers = list(range(start + 1, end + 1))
                sheet = _contact_sheet(images, numbers, Image, ImageDraw, ImageOps)
                range_name = f"{start + 1}-{end}"
                sheet.save(contact_dir / f"color-pages-{range_name}.png")
                gray_sheet = ImageOps.grayscale(sheet)
                try:
                    gray_sheet.save(contact_dir / f"gray-pages-{range_name}.png")
                finally:
                    gray_sheet.close()
                sheet.close()
            finally:
                for image in images:
                    image.close()
        print(f"渲染完成：{page_count} 页；输出目录：{output_dir}")
        print(f"逐页彩色 PNG：{pages_dir}")
        print(f"彩色/灰度联系表：{contact_dir}")
        return 0
    finally:
        document.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将论文 PDF 渲染为逐页 PNG 与彩色/灰度联系表")
    parser.add_argument("pdf", type=Path, help="输入 PDF")
    parser.add_argument("--output-dir", required=True, type=Path, help="项目内 QA 输出目录，例如 <PROJECT_ROOT>/paper/_qa/")
    parser.add_argument("--dpi", type=_positive_float, default=160.0, help="渲染分辨率，默认 160")
    parser.add_argument("--pages-per-sheet", type=_positive_int, default=6, help="每张联系表页数，默认 6")
    parser.add_argument("--overwrite", action="store_true", help="仅覆盖本脚本同名输出，不删除目录其他文件")
    args = parser.parse_args(argv)
    try:
        return render(
            args.pdf,
            args.output_dir,
            dpi=args.dpi,
            pages_per_sheet=args.pages_per_sheet,
            overwrite=args.overwrite,
        )
    except (FileExistsError, RuntimeError, ValueError, OSError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
