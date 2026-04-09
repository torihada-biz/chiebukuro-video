"""
Yahoo知恵袋スクレイパー
バズりやすいカテゴリ（恋愛相談・人間関係等）からQ&Aを取得し、
RedditVideoMakerBotと互換性のある辞書形式で返す。
"""

import hashlib
import json
import re
import time
from os.path import exists
from typing import Optional

import requests
from bs4 import BeautifulSoup

from utils import settings
from utils.console import print_step, print_substep

TOP_URL = "https://chiebukuro.yahoo.co.jp/"

# バズりやすいカテゴリ
BUZZ_CATEGORIES = {
    "恋愛相談": "https://chiebukuro.yahoo.co.jp/category/2078675272/question/list",
    "友人関係の悩み": "https://chiebukuro.yahoo.co.jp/category/2078675275/question/list",
    "家族関係の悩み": "https://chiebukuro.yahoo.co.jp/category/2078675273/question/list",
    "職場の悩み": "https://chiebukuro.yahoo.co.jp/category/2078675274/question/list",
    "生き方、人生相談": "https://chiebukuro.yahoo.co.jp/category/2079526980/question/list",
    "学校の悩み": "https://chiebukuro.yahoo.co.jp/category/2080401676/question/list",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def _generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print_substep(f"ページ取得失敗 {url}: {e}", style="red")
        return None


def _extract_question_links(soup: BeautifulSoup) -> list:
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "question_detail" in href:
            if href.startswith("/"):
                href = "https://detail.chiebukuro.yahoo.co.jp" + href
            if href.startswith("http") and href not in links:
                links.append(href)
    return links


def _extract_question_detail(url: str) -> Optional[dict]:
    soup = _fetch_page(url)
    if soup is None:
        return None

    title_tag = soup.select_one("h1")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)
    if not title or len(title) < 5:
        return None

    # 知恵袋のh1にはタイトル+本文が結合されていることがある
    # 最初の句点・改行・「…続きを読む」で切る
    question_body = ""
    body_el = soup.select_one('[class*="QuestionItem"] [class*="Text"]')
    if body_el:
        question_body = body_el.get_text(strip=True)

    # タイトルが長すぎる場合、最初の文で切り詰める
    if len(title) > 100:
        # 句点・疑問符・感嘆符で区切って最初の1-2文だけ残す
        sentences = re.split(r"(?<=[。？！?!])", title)
        short_title = ""
        for s in sentences:
            if len(short_title) + len(s) > 100:
                break
            short_title += s
        if short_title:
            title = short_title

    answers = []
    top_answer_items = soup.select('[class*="AnswerItem__Item__"]')
    for idx, item in enumerate(top_answer_items):
        text_el = item.select_one('[class*="ItemText"]')
        if not text_el:
            continue
        body_text = text_el.get_text(strip=True)
        if len(body_text) < 10:
            continue
        answer_id = _generate_id(f"{url}_answer_{idx}")
        answers.append(
            {
                "comment_body": body_text,
                "comment_url": url,
                "comment_id": answer_id,
            }
        )

    return {
        "thread_url": url,
        "thread_title": title,
        "thread_id": _generate_id(url),
        "thread_post": question_body,
        "is_nsfw": False,
        "comments": answers,
    }


def _is_already_done(question_id: str) -> bool:
    videos_path = "./video_creation/data/videos.json"
    if not exists(videos_path):
        with open(videos_path, "w") as f:
            json.dump([], f)
        return False
    with open(videos_path, "r", encoding="utf-8") as f:
        done_videos = json.load(f)
    return any(v["id"] == question_id for v in done_videos)


def _contains_blocked_words(text: str) -> bool:
    blocked_raw = settings.config["chiebukuro"].get("blocked_words", "")
    if not blocked_raw:
        return False
    blocked = [w.strip().lower() for w in blocked_raw.split(",") if w.strip()]
    text_lower = text.lower()
    return any(word in text_lower for word in blocked)


def _score_question(result: dict) -> float:
    """質問の面白さスコアを計算（高い方がバズりやすい）"""
    score = 0.0
    title = result["thread_title"]
    comments = result["comments"]

    # --- 回答数ボーナス（3以上で加速） ---
    n = len(comments)
    if n >= 3:
        score += 10 + min(n - 3, 7) * 2  # 3=10, 10=24
    else:
        score += n * 2

    # --- タイトルの感情強度 ---
    # 疑問符・感嘆符の数（多いほど感情的）
    q_count = title.count("？") + title.count("?")
    e_count = title.count("！") + title.count("!")
    score += min(q_count, 3) * 3
    score += min(e_count, 3) * 2

    # www・笑・草 = ネタ系
    laugh_count = len(re.findall(r"[wW]+|笑|草|ワロタ|ウケる", title))
    score += min(laugh_count, 3) * 4

    # タイトルの長さ（適度が良い）
    if 15 < len(title) < 100:
        score += 3

    # --- バズワード（タイトル） ---
    title_buzz = [
        "なぜ", "どうして", "本当", "マジ", "やばい", "ヤバい", "ヤバ",
        "びっくり", "驚", "衝撃", "信じられない", "意味不明",
        "助けて", "困", "緊急", "至急", "限界",
        "面白", "ウケ", "神", "天才", "最悪", "最高",
        "好き", "嫌い", "別れ", "浮気", "告白", "片思い", "彼氏", "彼女",
        "友達", "いじめ", "無視", "裏切",
        "どう思", "おかしい", "普通", "非常識",
    ]
    for word in title_buzz:
        if word in title:
            score += 3

    # --- 回答の感情強度 ---
    answer_buzz = [
        "ヤバい", "ヤバ", "やばい", "信じられない", "最悪", "最低",
        "ありえない", "おかしい", "狂", "頭おかしい",
        "可哀想", "かわいそう", "泣", "涙", "感動",
        "笑", "草", "ウケる", "面白",
        "別れ", "逃げ", "縁を切", "離婚",
        "正直", "ぶっちゃけ", "はっきり言",
    ]
    answer_text_all = " ".join(c["comment_body"] for c in comments)
    for word in answer_buzz:
        count = answer_text_all.count(word)
        if count > 0:
            score += min(count, 3) * 2

    # --- 回答の質（適度な長さの回答が多い） ---
    good_answers = [c for c in comments if 30 < len(c["comment_body"]) < 300]
    score += len(good_answers) * 2

    return score


def get_chiebukuro_threads(post_url: str = None) -> dict:
    """
    Yahoo知恵袋からQ&Aスレッドを取得する。
    バズりやすいカテゴリを巡回して最も面白い質問を選択。
    """
    print_step("Yahoo知恵袋から質問を取得中...")

    # 特定URLが指定されている場合
    if post_url:
        print_substep(f"指定URL: {post_url}")
        result = _extract_question_detail(post_url)
        if result is None:
            raise ValueError(f"質問を取得できませんでした: {post_url}")
        return result

    config_url = settings.config["chiebukuro"].get("post_url", "")
    if config_url:
        print_substep(f"設定ファイルのURL: {config_url}")
        result = _extract_question_detail(config_url)
        if result is None:
            raise ValueError(f"質問を取得できませんでした: {config_url}")
        return result

    max_results = int(settings.config["chiebukuro"].get("max_results", 10))
    min_answers = max(int(settings.config["chiebukuro"].get("min_answers", 3)), 3)
    max_answer_length = int(settings.config["chiebukuro"].get("max_answer_length", 500))
    min_answer_length = int(settings.config["chiebukuro"].get("min_answer_length", 10))

    # バズカテゴリから質問を収集
    all_links = []
    for cat_name, cat_url in BUZZ_CATEGORIES.items():
        print_substep(f"カテゴリ取得中: {cat_name}")
        soup = _fetch_page(cat_url)
        if soup is None:
            continue
        links = _extract_question_links(soup)
        print_substep(f"  {len(links)} 件")
        all_links.extend(links)
        time.sleep(0.3)

    # トップページからも取得（おバカ質問はカテゴリ問わず出る）
    print_substep("トップページからも取得中...")
    top_soup = _fetch_page(TOP_URL)
    if top_soup:
        top_links = _extract_question_links(top_soup)
        print_substep(f"  {len(top_links)} 件")
        all_links.extend(top_links)

    # 重複除去
    seen = set()
    unique_links = []
    for link in all_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    print_substep(f"合計 {len(unique_links)} 件のユニーク質問を発見")

    if not unique_links:
        raise ValueError("質問リンクが見つかりませんでした")

    # 質問を解析してスコアリング
    candidates = []
    checked = 0
    for link in unique_links:
        if checked >= max_results:
            break

        result = _extract_question_detail(link)
        if result is None:
            continue

        if _contains_blocked_words(result["thread_title"]):
            continue

        if _is_already_done(result["thread_id"]):
            continue

        # 回答数3以上に絞る
        if len(result["comments"]) < min_answers:
            continue

        # 回答の長さでフィルタ
        result["comments"] = [
            c
            for c in result["comments"]
            if min_answer_length <= len(c["comment_body"]) <= max_answer_length
        ]
        if len(result["comments"]) < min_answers:
            continue

        score = _score_question(result)
        candidates.append((score, result))
        checked += 1
        time.sleep(0.3)

    if not candidates:
        raise ValueError("条件に合う未処理の質問が見つかりませんでした")

    candidates.sort(key=lambda x: x[0], reverse=True)

    # 上位3件をログ
    print_substep("--- スコア上位 ---", style="bold")
    for i, (s, r) in enumerate(candidates[:3]):
        print_substep(
            f"  {i+1}. [{s:.0f}pt] {r['thread_title'][:50]}... ({len(r['comments'])}回答)"
        )

    best_score, best = candidates[0]
    print_substep(f"選択: {best['thread_title']}", style="bold green")
    print_substep(f"URL: {best['thread_url']}", style="bold green")
    print_substep(f"回答数: {len(best['comments'])}", style="bold blue")
    print_substep(f"面白さスコア: {best_score:.0f}pt", style="bold blue")

    return best
