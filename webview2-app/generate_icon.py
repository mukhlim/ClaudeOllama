#!/usr/bin/env python3
"""Generate a simple app icon for ClaudeOllamaLauncher."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).parent / "ui" / "icon.ico"

# Sizes required for a proper Windows .ico
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (30, 30, 46, 255))
    draw = ImageDraw.Draw(img)

    # Background circle in accent color
    pad = size // 12
    draw.ellipse(
        [pad, pad, size - pad, size - pad],
        fill=(137, 180, 250, 255),  # Catppuccin blue
        outline=(180, 190, 254, 255),
        width=max(1, size // 64),
    )

    # Inner cloud shape (simplified as overlapping circles)
    cloud_color = (30, 30, 46, 255)
    cloud_y = size * 0.48
    r = size * 0.14
    centers = [
        (size * 0.32, cloud_y),
        (size * 0.50, cloud_y - size * 0.08),
        (size * 0.68, cloud_y),
    ]
    for cx, cy in centers:
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=cloud_color,
        )
    # Flat bottom of cloud
    draw.rectangle(
        [size * 0.32, cloud_y, size * 0.68, cloud_y + r],
        fill=cloud_color,
    )

    # Draw letter "C" inside the cloud
    try:
        font = ImageFont.truetype("segoeui.ttf", int(size * 0.26))
    except Exception:
        font = ImageFont.load_default()

    text = "C"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2
    y = cloud_y - text_h / 2 + size * 0.02
    draw.text((x, y), text, font=font, fill=(137, 180, 250, 255))

    return img


def main():
    images = [draw_icon(s) for s in SIZES]
    images[0].save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Icon saved to {OUTPUT}")


if __name__ == "__main__":
    main()
