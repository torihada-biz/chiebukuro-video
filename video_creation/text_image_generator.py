"""
日本語テキスト画像生成モジュール
Playwright/Reddit依存を排除し、Pillowで知恵袋Q&Aのテキスト画像を生成する。
"""

import os
import re
import textwrap
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils import settings
from utils.console import print_step, print_substep
from utils.videos import save_data

__all__ = ["generate_text_images"]

# 日本語フォントのパス
FONT_JP_BOLD = os.path.join("fonts", "NotoSansJP-Variable.ttf")
FONT_JP_REGULAR = os.path.join("fonts", "NotoSansJP-Variable.ttf")
FONT_FALLBACK = os.path.join("fonts", "Roboto-Bold.ttf")


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """日本語フォントを取得（フォールバック付き）"""
    font_path = FONT_JP_BOLD if bold else FONT_JP_REGULAR
    try:
        return ImageFont.truetype(font_path, size)
    except (OSError, IOError):
        return ImageFont.truetype(FONT_FALLBACK, size)


def _wrap_text_jp(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """日本語テキストを指定幅で折り返す"""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
    return lines


def _draw_rounded_rect(draw, xy, radius, fill):
    """角丸矩形を描画"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _create_question_card(
    title: str,
    width: int,
    height: int,
    theme: str = "dark",
) -> Image.Image:
    """質問カード画像を生成"""
    if theme == "dark":
        bg_color = (24, 24, 32, 230)
        card_color = (40, 40, 55, 255)
        title_color = (255, 255, 255)
        accent_color = (255, 107, 107)
        label_bg = (255, 107, 107, 255)
    elif theme == "transparent":
        bg_color = (0, 0, 0, 0)
        card_color = (0, 0, 0, 160)
        title_color = (255, 255, 255)
        accent_color = (255, 200, 87)
        label_bg = (255, 200, 87, 255)
    else:  # light
        bg_color = (245, 245, 250, 230)
        card_color = (255, 255, 255, 255)
        title_color = (30, 30, 30)
        accent_color = (220, 53, 69)
        label_bg = (220, 53, 69, 255)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    padding = 60
    card_margin = 40
    card_x1 = card_margin
    card_y1 = height // 4
    card_x2 = width - card_margin
    card_y2 = height * 3 // 4

    # カード背景
    _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y2), 24, card_color)

    # 「質問」ラベル
    label_font = _get_font(28, bold=True)
    label_text = "質問"
    label_w = label_font.getbbox(label_text)[2] + 30
    label_h = 50
    label_x = card_x1 + padding
    label_y = card_y1 + 30
    _draw_rounded_rect(
        draw,
        (label_x, label_y, label_x + label_w, label_y + label_h),
        12,
        label_bg,
    )
    draw.text(
        (label_x + 15, label_y + 8),
        label_text,
        font=label_font,
        fill=(255, 255, 255),
    )

    # 質問タイトル
    title_font = _get_font(52, bold=True)
    text_area_width = card_x2 - card_x1 - padding * 2
    lines = _wrap_text_jp(title, title_font, text_area_width)

    line_height = 72
    text_start_y = label_y + label_h + 40
    for i, line in enumerate(lines[:8]):  # 最大8行
        draw.text(
            (card_x1 + padding, text_start_y + i * line_height),
            line,
            font=title_font,
            fill=title_color,
        )

    # ?マーク装飾
    q_font = _get_font(120, bold=True)
    draw.text(
        (card_x2 - 140, card_y1 - 60),
        "?",
        font=q_font,
        fill=(*accent_color[:3], 80) if len(accent_color) >= 3 else accent_color,
    )

    return img


def _create_answer_card(
    answer_text: str,
    answer_idx: int,
    width: int,
    height: int,
    theme: str = "dark",
) -> Image.Image:
    """回答カード画像を生成"""
    if theme == "dark":
        bg_color = (24, 24, 32, 230)
        card_color = (40, 40, 55, 255)
        text_color = (240, 240, 240)
        accent_color = (100, 200, 255)
        label_bg = (100, 200, 255, 255)
    elif theme == "transparent":
        bg_color = (0, 0, 0, 0)
        card_color = (0, 0, 0, 160)
        text_color = (255, 255, 255)
        accent_color = (100, 255, 200)
        label_bg = (100, 255, 200, 255)
    else:  # light
        bg_color = (245, 245, 250, 230)
        card_color = (255, 255, 255, 255)
        text_color = (30, 30, 30)
        accent_color = (0, 123, 255)
        label_bg = (0, 123, 255, 255)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    padding = 60
    card_margin = 40
    card_x1 = card_margin
    card_y1 = height // 6
    card_x2 = width - card_margin
    card_y2 = height * 5 // 6

    # カード背景
    _draw_rounded_rect(draw, (card_x1, card_y1, card_x2, card_y2), 24, card_color)

    # 「ベストアンサー」 or 「回答N」ラベル
    label_font = _get_font(26, bold=True)
    label_text = "ベストアンサー" if answer_idx == 0 else f"回答 {answer_idx + 1}"
    label_w = label_font.getbbox(label_text)[2] + 30
    label_h = 46
    label_x = card_x1 + padding
    label_y = card_y1 + 30
    _draw_rounded_rect(
        draw,
        (label_x, label_y, label_x + label_w, label_y + label_h),
        12,
        label_bg,
    )
    draw.text(
        (label_x + 15, label_y + 7),
        label_text,
        font=label_font,
        fill=(255, 255, 255) if theme != "light" else (255, 255, 255),
    )

    # 回答テキスト
    text_font = _get_font(42, bold=False)
    text_area_width = card_x2 - card_x1 - padding * 2
    lines = _wrap_text_jp(answer_text, text_font, text_area_width)

    line_height = 60
    text_start_y = label_y + label_h + 35
    max_lines = (card_y2 - text_start_y - 40) // line_height
    for i, line in enumerate(lines[:max_lines]):
        draw.text(
            (card_x1 + padding, text_start_y + i * line_height),
            line,
            font=text_font,
            fill=text_color,
        )

    return img


def generate_text_images(chiebukuro_object: dict, screenshot_num: int):
    """
    知恵袋Q&Aのテキストから画像を生成する。
    screenshot_downloader.get_screenshots_of_reddit_postsの代替。

    Args:
        chiebukuro_object: 知恵袋オブジェクト
        screenshot_num: 生成する回答画像の数
    """
    W: Final[int] = int(settings.config["settings"]["resolution_w"])
    H: Final[int] = int(settings.config["settings"]["resolution_h"])
    theme: str = settings.config["settings"]["theme"]

    print_step("テキスト画像を生成中...")
    thread_id = re.sub(r"[^\w\s-]", "", chiebukuro_object["thread_id"])
    Path(f"assets/temp/{thread_id}/png").mkdir(parents=True, exist_ok=True)

    # 質問カード生成
    title_img = _create_question_card(
        chiebukuro_object["thread_title"],
        W,
        H,
        theme=theme,
    )
    title_img.save(f"assets/temp/{thread_id}/png/title.png")
    print_substep("質問カード生成完了", style="bold green")

    # 回答カード生成
    comments = chiebukuro_object["comments"][:screenshot_num]
    for idx, comment in enumerate(comments):
        answer_img = _create_answer_card(
            comment["comment_body"],
            idx,
            W,
            H,
            theme=theme,
        )
        answer_img.save(f"assets/temp/{thread_id}/png/comment_{idx}.png")

    print_substep(
        f"{len(comments) + 1} 枚のテキスト画像を生成完了", style="bold green"
    )
