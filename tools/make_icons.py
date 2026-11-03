"""Generate the ShopEx app artwork (original, CC0-style: drawn here from geometric primitives).

Outputs, in ``client/assets/``:
- ``icon.png``                 1024x1024, opaque accent square + white basket (iOS/Android/web icon;
                               the OS applies its own rounded mask, and App Store icons must be opaque)
- ``adaptive-icon.png``        1024x1024 transparent foreground for Android adaptive icons
                               (glyph kept inside the 66 % safe zone; background colour set in app.json)
- ``adaptive-icon-mono.png``   1024x1024 monochrome variant for Android 13+ themed icons
- ``splash-icon.png``          1024x1024 transparent: rounded accent tile + "ShopEx" wordmark
- ``favicon.png``              48x48 rounded accent tile + basket

Shapes are rendered with signed distance functions and analytic anti-aliasing, and PNGs are
encoded with ``zlib`` + ``struct``: the script needs nothing beyond the Python standard library.

Usage (from the repository root):  python tools/make_icons.py
"""

from __future__ import annotations

import math
import struct
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "client" / "assets"

Color = tuple[int, int, int]
Point = tuple[float, float]
Sdf = Callable[[float, float], float]

# Theme tokens (ARCHITECTURE §5).
ACCENT: Color = (0xF2, 0x54, 0x2D)
WHITE: Color = (0xFF, 0xFF, 0xFF)
INK: Color = (0x19, 0x19, 0x19)


# ---------------------------------------------------------------------------
# Signed distance functions (pixel space, y pointing down; negative = inside)
# ---------------------------------------------------------------------------


def rounded_box(cx: float, cy: float, half_w: float, half_h: float, radius: float) -> Sdf:
    def sdf(x: float, y: float) -> float:
        qx = abs(x - cx) - half_w + radius
        qy = abs(y - cy) - half_h + radius
        outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
        return outside + min(max(qx, qy), 0.0) - radius

    return sdf


def capsule(a: Point, b: Point, radius: float) -> Sdf:
    ax, ay = a
    abx, aby = b[0] - ax, b[1] - ay
    length_sq = abx * abx + aby * aby or 1e-9

    def sdf(x: float, y: float) -> float:
        px, py = x - ax, y - ay
        t = min(max((px * abx + py * aby) / length_sq, 0.0), 1.0)
        return math.hypot(px - abx * t, py - aby * t) - radius

    return sdf


def arc(center: Point, radius: float, half_stroke: float, start_deg: float, end_deg: float) -> Sdf:
    """Stroke along a circle from ``start_deg`` to ``end_deg`` (clockwise on screen), round caps."""
    cx, cy = center
    sweep = (end_deg - start_deg) % 360 or 360
    caps = [
        (cx + radius * math.cos(math.radians(angle)), cy + radius * math.sin(math.radians(angle)))
        for angle in (start_deg, start_deg + sweep)
    ]

    def sdf(x: float, y: float) -> float:
        dx, dy = x - cx, y - cy
        relative = (math.degrees(math.atan2(dy, dx)) - start_deg) % 360
        if relative <= sweep:
            return abs(math.hypot(dx, dy) - radius) - half_stroke
        return min(math.hypot(x - px, y - py) for px, py in caps) - half_stroke

    return sdf


def ring(center: Point, radius: float, half_stroke: float) -> Sdf:
    cx, cy = center

    def sdf(x: float, y: float) -> float:
        return abs(math.hypot(x - cx, y - cy) - radius) - half_stroke

    return sdf


def polygon(points: Sequence[Point], rounding: float = 0.0) -> Sdf:
    """Closed polygon (any winding); ``rounding`` grows it with round corners."""

    def sdf(x: float, y: float) -> float:
        best = math.inf
        inside = False
        count = len(points)
        for index in range(count):
            ax, ay = points[index]
            bx, by = points[index - 1]
            ex, ey = bx - ax, by - ay
            wx, wy = x - ax, y - ay
            t = min(max((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0), 1.0)
            best = min(best, math.hypot(wx - ex * t, wy - ey * t))
            if (ay > y) != (by > y) and x < ax + (y - ay) * ex / ey:
                inside = not inside
        return (-best if inside else best) - rounding

    return sdf


def union(*shapes: Sdf) -> Sdf:
    def sdf(x: float, y: float) -> float:
        return min(shape(x, y) for shape in shapes)

    return sdf


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

Box = tuple[float, float, float, float]  # left, top, right, bottom (pixels)


@dataclass(frozen=True)
class Layer:
    shape: Sdf
    bounds: Box
    color: Color | None  # None erases (cuts a transparent hole)


class Canvas:
    """Straight-alpha RGBA float buffer with source-over compositing."""

    def __init__(self, width: int, height: int, background: Color | None = None) -> None:
        self.width = width
        self.height = height
        alpha = 0.0 if background is None else 1.0
        r, g, b = background or (0, 0, 0)
        self.pixels = [[float(r), float(g), float(b), alpha] for _ in range(width * height)]

    def draw(self, layer: Layer) -> None:
        left, top, right, bottom = layer.bounds
        x0, y0 = max(int(left) - 2, 0), max(int(top) - 2, 0)
        x1, y1 = min(int(right) + 3, self.width), min(int(bottom) + 3, self.height)
        for y in range(y0, y1):
            row = y * self.width
            for x in range(x0, x1):
                # Coverage of the pixel centre by the shape: a 1 px wide linear ramp at the edge.
                coverage = min(max(0.5 - layer.shape(x + 0.5, y + 0.5), 0.0), 1.0)
                if coverage > 0.0:
                    self._blend(self.pixels[row + x], layer.color, coverage)

    @staticmethod
    def _blend(pixel: list[float], color: Color | None, coverage: float) -> None:
        if color is None:
            pixel[3] *= 1.0 - coverage
            return
        dst_alpha = pixel[3] * (1.0 - coverage)
        out_alpha = coverage + dst_alpha
        for channel in range(3):
            pixel[channel] = (color[channel] * coverage + pixel[channel] * dst_alpha) / out_alpha
        pixel[3] = out_alpha

    def save_png(self, path: Path) -> None:
        raw = bytearray()
        for y in range(self.height):
            raw.append(0)  # filter type: none
            for r, g, b, a in self.pixels[y * self.width : (y + 1) * self.width]:
                raw.extend((round(r), round(g), round(b), round(a * 255)))

        def chunk(kind: bytes, data: bytes) -> bytes:
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 6, 0, 0, 0)  # 8-bit RGBA
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )


# ---------------------------------------------------------------------------
# Artwork
# ---------------------------------------------------------------------------


def basket_layers(cx: float, cy: float, size: float, color: Color, slat_color: Color | None) -> list[Layer]:
    """Basket glyph designed on a 100x100 grid centred on (cx, cy), scaled to ``size`` pixels."""
    unit = size / 100.0

    def p(gx: float, gy: float) -> Point:
        return cx + (gx - 50) * unit, cy + (gy - 50) * unit

    def box(gx0: float, gy0: float, gx1: float, gy1: float) -> Box:
        (left, top), (right, bottom) = p(gx0, gy0), p(gx1, gy1)
        return left, top, right, bottom

    handle = arc(p(50, 45), 22 * unit, 4.5 * unit, 180, 360)
    rim = rounded_box(*p(50, 46), 38 * unit, 5.5 * unit, 5.5 * unit)
    body = polygon([p(20, 58), p(80, 58), p(71, 80), p(29, 80)], rounding=4 * unit)
    slats = union(
        capsule(p(37, 62), p(39, 76), 2.6 * unit),
        capsule(p(50, 62), p(50, 76), 2.6 * unit),
        capsule(p(63, 62), p(61, 76), 2.6 * unit),
    )
    return [
        Layer(handle, box(23, 18, 77, 46), color),
        Layer(rim, box(12, 40, 88, 52), color),
        Layer(body, box(16, 54, 84, 84), color),
        Layer(slats, box(33, 58, 67, 80), slat_color),
    ]


# Wordmark: a small geometric font with rounded strokes. Units: cap height 100, x-height 72,
# stroke 16, baseline at y = 0 (y pointing down). Each glyph is (advance width, primitives).
STROKE = 16.0
HALF = STROKE / 2

GlyphBuilder = Callable[[float, float, float], Sdf]  # (origin x, baseline y, px per unit) -> Sdf


def _glyph_s(ox: float, oy: float, u: float) -> Sdf:
    r = 21.0
    return union(
        arc((ox + 29 * u, oy - 71 * u), r * u, HALF * u, 90, 325),
        arc((ox + 29 * u, oy - 29 * u), r * u, HALF * u, 270, 145),
    )


def _glyph_h(ox: float, oy: float, u: float) -> Sdf:
    return union(
        capsule((ox + 8 * u, oy - 92 * u), (ox + 8 * u, oy - 8 * u), HALF * u),
        arc((ox + 30 * u, oy - 42 * u), 22 * u, HALF * u, 180, 360),
        capsule((ox + 52 * u, oy - 42 * u), (ox + 52 * u, oy - 8 * u), HALF * u),
    )


def _glyph_o(ox: float, oy: float, u: float) -> Sdf:
    return ring((ox + 36 * u, oy - 36 * u), 28 * u, HALF * u)


def _glyph_p(ox: float, oy: float, u: float) -> Sdf:
    return union(
        capsule((ox + 8 * u, oy - 64 * u), (ox + 8 * u, oy + 20 * u), HALF * u),
        ring((ox + 36 * u, oy - 36 * u), 28 * u, HALF * u),
    )


def _glyph_e(ox: float, oy: float, u: float) -> Sdf:
    return union(
        capsule((ox + 8 * u, oy - 92 * u), (ox + 8 * u, oy - 8 * u), HALF * u),
        capsule((ox + 8 * u, oy - 92 * u), (ox + 54 * u, oy - 92 * u), HALF * u),
        capsule((ox + 8 * u, oy - 50 * u), (ox + 46 * u, oy - 50 * u), HALF * u),
        capsule((ox + 8 * u, oy - 8 * u), (ox + 54 * u, oy - 8 * u), HALF * u),
    )


def _glyph_x(ox: float, oy: float, u: float) -> Sdf:
    return union(
        capsule((ox + 8 * u, oy - 64 * u), (ox + 52 * u, oy - 8 * u), HALF * u),
        capsule((ox + 52 * u, oy - 64 * u), (ox + 8 * u, oy - 8 * u), HALF * u),
    )


GLYPHS: dict[str, tuple[float, GlyphBuilder]] = {
    "S": (58, _glyph_s),
    "h": (60, _glyph_h),
    "o": (72, _glyph_o),
    "p": (72, _glyph_p),
    "E": (62, _glyph_e),
    "x": (60, _glyph_x),
}
LETTER_SPACING = 10.0
CAP_HEIGHT = 100.0
DESCENDER = 28.0


def wordmark_width(text: str) -> float:
    return sum(GLYPHS[char][0] for char in text) + LETTER_SPACING * (len(text) - 1)


def wordmark_layers(runs: Sequence[tuple[str, Color]], left: float, baseline: float, unit: float) -> list[Layer]:
    layers: list[Layer] = []
    x = left
    for text, color in runs:
        for char in text:
            advance, build = GLYPHS[char]
            bounds = (x, baseline - CAP_HEIGHT * unit, x + advance * unit, baseline + DESCENDER * unit)
            layers.append(Layer(build(x, baseline, unit), bounds, color))
            x += (advance + LETTER_SPACING) * unit
    return layers


def render(width: int, height: int, background: Color | None, layers: Sequence[Layer], path: Path) -> None:
    canvas = Canvas(width, height, background)
    for layer in layers:
        canvas.draw(layer)
    canvas.save_png(path)
    print(f"wrote {path.relative_to(ASSETS_DIR.parent.parent)} ({width}x{height})")


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    size = 1024

    # App icon: opaque, full bleed (the OS rounds the corners).
    render(size, size, ACCENT, basket_layers(512, 512, 640, WHITE, ACCENT), ASSETS_DIR / "icon.png")

    # Android adaptive icon: glyph within the 66 % safe zone, slats cut through to the background.
    render(size, size, None, basket_layers(512, 512, 470, WHITE, None), ASSETS_DIR / "adaptive-icon.png")
    render(size, size, None, basket_layers(512, 512, 470, WHITE, None), ASSETS_DIR / "adaptive-icon-mono.png")

    # Splash: rounded accent tile (same proportions as the in-app <Logo />) above the wordmark.
    tile = 300.0
    unit = 1.35
    text_height = (CAP_HEIGHT + DESCENDER) * unit
    gap = 64.0
    top = (size - (tile + gap + text_height)) / 2
    tile_cy = top + tile / 2
    splash_layers = [
        Layer(rounded_box(512, tile_cy, tile / 2, tile / 2, tile * 0.3), (362, top, 662, top + tile), ACCENT),
        *basket_layers(512, tile_cy, tile * 0.74, WHITE, ACCENT),
        *wordmark_layers(
            [("Shop", INK), ("Ex", ACCENT)],
            left=(size - wordmark_width("ShopEx") * unit) / 2,
            baseline=top + tile + gap + CAP_HEIGHT * unit,
            unit=unit,
        ),
    ]
    render(size, size, None, splash_layers, ASSETS_DIR / "splash-icon.png")

    # Favicon: small rounded tile (transparent corners) with a bold glyph.
    favicon = 48
    render(
        favicon,
        favicon,
        None,
        [
            Layer(rounded_box(24, 24, 24, 24, 12), (0, 0, favicon, favicon), ACCENT),
            *basket_layers(24, 25, 36, WHITE, ACCENT),
        ],
        ASSETS_DIR / "favicon.png",
    )


if __name__ == "__main__":
    main()
