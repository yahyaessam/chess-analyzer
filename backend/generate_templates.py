"""Generate a default set of chess piece templates from system Unicode fonts."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

PIECES = {
    "w_P": "♙",
    "w_N": "♘",
    "w_B": "♗",
    "w_R": "♖",
    "w_Q": "♕",
    "w_K": "♔",
    "b_P": "♟",
    "b_N": "♞",
    "b_B": "♝",
    "b_R": "♜",
    "b_Q": "♛",
    "b_K": "♚",
}

FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/ARIALUNI.TTF",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
]


def find_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_piece(char: str, size: int, fill: str, outline: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = find_font(int(size * 0.75))
    x, y = size * 0.12, size * 0.05
    for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, -2), (0, 2), (-2, 0), (2, 0)]:
        draw.text((x + dx, y + dy), char, font=font, fill=outline)
    draw.text((x, y), char, font=font, fill=fill)
    return img


def generate(size: int = 64) -> None:
    for label, char in PIECES.items():
        is_white = label.startswith("w_")
        fill = "white" if is_white else "black"
        outline = "black" if is_white else "white"
        img = draw_piece(char, size, fill, outline)
        img.save(TEMPLATE_DIR / f"{label}.png")
    print(f"Generated {len(PIECES)} templates in {TEMPLATE_DIR}")


if __name__ == "__main__":
    generate()
