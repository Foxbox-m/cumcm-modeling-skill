#!/usr/bin/env python3
"""Readable, reproducible CUMCM figure defaults and lightweight QA helpers.

The module deliberately does not prescribe a figure count or let category
identity depend on color alone. It provides compositional visual encodings,
explicit CJK-font checks, and helpers for sizing figures against the target
paper width.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib import cycler
from matplotlib import font_manager
from matplotlib.text import Text
from PIL import Image


PREFERRED_CJK_FONTS = (
    "Noto Serif CJK SC",
    "Source Han Serif CN",
    "FZShuSong-Z01",
    "Noto Sans CJK SC",
    "Source Han Sans CN",
    "Droid Sans Fallback",
)

# A restrained Okabe-Ito-derived set avoids the former red/green pairing. It is
# still combined with line styles, markers, or hatches rather than carrying
# category identity through color alone.
CUMCM_COLORS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")
CUMCM_LINESTYLES = ("-", "--", "-.", ":")
CUMCM_MARKERS = ("o", "s", "^", "D", "x", "v")
CUMCM_HATCHES = ("", "/", "\\", "x")
_CJK_RE = re.compile(
    r"[\u2e80-\u2fff\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
)


def contains_cjk(text: str) -> bool:
    """Return whether *text* contains a CJK character requiring a CJK font."""
    return bool(_CJK_RE.search(text or ""))


def _register_font(font_path: str | Path) -> str:
    path = Path(font_path)
    if not path.is_file():
        raise FileNotFoundError(f"指定中文字体不存在：{path}")
    font_manager.fontManager.addfont(str(path))
    return font_manager.FontProperties(fname=str(path)).get_name()


def find_cjk_font(font_path: str | Path | None = None) -> str | None:
    """Find a CJK font, optionally registering an explicitly supplied font.

    ``None`` is intentional for ASCII-only figures: DejaVu Sans is sufficient
    there. Chinese text never silently falls back to DejaVu.
    """
    if font_path is not None:
        return _register_font(font_path)
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in PREFERRED_CJK_FONTS:
        if name in installed:
            return name
    return None


def _figure_text(figure) -> str:
    return " ".join(
        text.get_text() for text in figure.findobj(match=Text) if text.get_text()
    )


def ensure_font_for_text(text: str, font_path: str | Path | None = None) -> str:
    """Validate font support and return the font family to use."""
    if not contains_cjk(text):
        return "DejaVu Sans"
    cjk_font = find_cjk_font(font_path)
    if cjk_font is None:
        raise RuntimeError(
            "图形包含中文但未找到 CJK 字体；请安装 Noto/思源 CJK，"
            "或在 set_cumcm_style/save_figure 中传入 font_path。"
        )
    return cjk_font


def set_cumcm_style(
    text: str | None = None,
    font_path: str | Path | None = None,
    *,
    grid: bool = False,
) -> str:
    """Apply defaults and return the selected font family.

    Pass labels/title text when available. ASCII-only figures use DejaVu;
    figures containing CJK text require an installed or explicitly supplied
    CJK font. Grid lines are opt-in because heatmaps and category plots often
    have their own visual structure.
    """
    cjk_text = text or ""
    selected_font = (
        ensure_font_for_text(cjk_text, font_path)
        if cjk_text
        else (find_cjk_font(font_path) or "DejaVu Sans")
    )
    plt.rcParams.update(
        {
            "font.family": [selected_font],
            "axes.unicode_minus": False,
            "font.size": 10.5,
            "axes.titlesize": 11,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.titlesize": 12,
            "lines.linewidth": 1.5,
            "lines.markersize": 5,
            "axes.grid": bool(grid),
            "grid.alpha": 0.3,
            "grid.linestyle": "--",
            "grid.linewidth": 0.6,
            "axes.edgecolor": "#333333",
            "axes.linewidth": 0.8,
            "axes.prop_cycle": cycler(color=CUMCM_COLORS),
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
        }
    )
    return selected_font


def figure_size_for_width(
    target_width_in: float = 6.2, aspect: float = 0.62
) -> tuple[float, float]:
    """Return a figure size in inches for a target paper width."""
    if target_width_in <= 0 or aspect <= 0:
        raise ValueError("target_width_in 和 aspect 必须为正数")
    return (float(target_width_in), float(target_width_in) * float(aspect))


def linewidth_for_width(
    base_width: float = 1.5,
    target_width_in: float = 6.2,
    reference_width_in: float = 6.2,
) -> float:
    """Scale a line width with target width while keeping a readable floor."""
    if min(base_width, target_width_in, reference_width_in) <= 0:
        raise ValueError("线宽和图宽必须为正数")
    return max(0.6, float(base_width) * float(target_width_in) / float(reference_width_in))


def series_style(
    index: int, target_width_in: float = 6.2, *, marker: bool = False
) -> dict[str, object]:
    """Return a color + line style, with a marker only when explicitly enabled."""
    if index < 0:
        raise ValueError("series index 不能为负数")
    style: dict[str, object] = {
        "color": CUMCM_COLORS[index % len(CUMCM_COLORS)],
        "linestyle": CUMCM_LINESTYLES[index % len(CUMCM_LINESTYLES)],
        "marker": None,
        "linewidth": linewidth_for_width(target_width_in=target_width_in),
    }
    if marker:
        style["marker"] = CUMCM_MARKERS[index % len(CUMCM_MARKERS)]
    return style


def bar_style(index: int, target_width_in: float = 6.2) -> dict[str, object]:
    """Return a color + hatch + outline combination for one bar series."""
    if index < 0:
        raise ValueError("bar index 不能为负数")
    return {
        "color": CUMCM_COLORS[index % len(CUMCM_COLORS)],
        "hatch": CUMCM_HATCHES[index % len(CUMCM_HATCHES)],
        "edgecolor": "#3A3A3A",
        "linewidth": linewidth_for_width(
            base_width=0.8, target_width_in=target_width_in
        ),
    }


def save_figure(
    figure,
    filename_base: str | Path,
    formats: Iterable[str] = ("pdf", "png"),
    font_path: str | Path | None = None,
) -> list[Path]:
    """Save a figure after checking CJK glyph support."""
    format_values = tuple(str(extension).lower().lstrip(".") for extension in formats)
    if not any(extension in {"pdf", "svg"} for extension in format_values):
        raise ValueError("formats 必须至少包含 pdf 或 svg 矢量容器")
    text = _figure_text(figure)
    selected_font = ensure_font_for_text(text, font_path)
    if contains_cjk(text):
        for artist in figure.findobj(match=Text):
            artist.set_fontfamily(selected_font)
    base = Path(filename_base)
    base.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for extension in format_values:
        if extension not in {"pdf", "svg", "png", "tiff"}:
            raise ValueError(f"不支持的图形格式：{extension}")
        output = base.with_suffix(f".{extension}")
        figure.savefig(output)
        outputs.append(output)
        if extension == "png":
            save_grayscale_preview(output)
    return outputs


def save_grayscale_preview(
    image_path: str | Path, output_dir: str | Path | None = None
) -> Path:
    """Create a grayscale PNG for visual QA; it is not a submission figure."""
    source = Path(image_path)
    if source.suffix.lower() != ".png":
        raise ValueError("灰度预览以最终 PNG 为输入，避免不同格式渲染差异")
    if not source.is_file():
        raise FileNotFoundError(source)
    target_dir = Path(output_dir) if output_dir is not None else source.parent / "_qa"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source.stem}_gray.png"
    with Image.open(source) as image:
        image.convert("L").save(target)
    return target


if __name__ == "__main__":
    print(f"绘图字体：{set_cumcm_style()}")
