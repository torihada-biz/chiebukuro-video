"""
Yahoo知恵袋スクレイパー
デイリーランキングやカテゴリ別ページからQ&Aを取得し、
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

BASE_URL = "https://detail.chiebukuro.yahoo.co.jp"
RANKING_URL = "https://chiebukuro.yahoo.co.jp/ranking/daily"
CATEGORY_URL = "https://chiebukuro.yahoo.co.jp/dir/list"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def _generate_id(url: str) -> str:
    """URLからユニークなIDを生成"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _fetch_page(url: str) -> Optional[BeautifulSoup]:
    """ページを取得してBeautifulSoupオブジェクトを返す"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print_substep(f"Failed to fetch {url}: {e}", style="red")
        return None


def _extract_question_links_from_ranking(soup: BeautifulSoup) -> list:
    """ランキングページから質問リンクを抽出"""
    links = []
    # ランキングページの質問リンクを取得
    for a_tag in soup.select("a[href*='detail.chiebukuro.yahoo.co.jp/qa/question_detail']"):
        href = a_tag.get("href", "")
        if href and href not in links:
            links.append(href)
    # フォールバック: /qa/question_detail を含むリンクを広く取得
    if not links:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "question_detail" in href:
                if href.startswith("/"):
                    href = "https://detail.chiebukuro.yahoo.co.jp" + href
                if href not in links:
                    links.append(href)
    return links


def _extract_question_detail(url: str) -> Optional[dict]:
    """個別の質問ページからQ&Aデータを抽出"""
    soup = _fetch_page(url)
    if soup is None:
        return None

    # 質問タイトルの取得
    title_tag = soup.select_one("h1") or soup.select_one(".qa-question_title")
    if not title_tag:
        return None
    title = title_tag.get_text(strip=True)

    # 質問本文の取得
    question_body = ""
    body_tag = soup.select_one(".qa-question_body") or soup.select_one(
        '[class*="QuestionItem__TextContainer"]'
    )
    if body_tag:
        question_body = body_tag.get_text(strip=True)

    # 回答の取得
    answers = []
    answer_containers = soup.select(".qa-answer") or soup.select(
        '[class*="AnswerItem"]'
    )
    # フォールバック: 回答コンテナを広く検索
    if not answer_containers:
        answer_containers = soup.select('[data-testid*="answer"]') or []

    for idx, ans in enumerate(answer_containers):
        body_el = (
            ans.select_one(".qa-answer_body")
            or ans.select_one('[class*="TextContainer"]')
            or ans.select_one("p")
        )
        if body_el:
            answer_text = body_el.get_text(strip=True)
            if answer_text and len(answer_text) > 5:
                answer_id = _generate_id(f"{url}_answer_{idx}")
                answers.append(
                    {
                        "comment_body": answer_text,
                        "comment_url": url,
                        "comment_id": answer_id,
                    }
                )

    if not title:
        return None

    question_id = _generate_id(url)

    return {
        "thread_url": url,
        "thread_title": title,
        "thread_id": question_id,
        "thread_post": question_body,
        "is_nsfw": False,
        "comments": answers,
    }


def _is_already_done(question_id: str) -> bool:
    """この質問が既に動画化済みかチェック"""
    videos_path = "./video_creation/data/videos.json"
    if not exists(videos_path):
        with open(videos_path, "w") as f:
            json.dump([], f)
        return False
    with open(videos_path, "r", encoding="utf-8") as f:
        done_videos = json.load(f)
    return any(v["id"] == question_id for v in done_videos)


def _contains_blocked_words(text: str) -> bool:
    """ブロックワードが含まれているかチェック"""
    blocked_raw = settings.config["chiebukuro"].get("blocked_words", "")
    if not blocked_raw:
        return False
    blocked = [w.strip().lower() for w in blocked_raw.split(",") if w.strip()]
    text_lower = text.lower()
    return any(word in text_lower for word in blocked)


def get_chiebukuro_threads(post_url: str = None) -> dict:
    """
    Yahoo知恵袋からQ&Aスレッドを取得する。

    Args:
        post_url: 特定の質問URL（指定時はそのページのみ取得）

    Returns:
        dict: RedditVideoMakerBotと互換性のある辞書
    """
    print_step("Yahoo知恵袋から質問を取得中...")

    # 特定URLが指定されている場合
    if post_url:
        print_substep(f"指定URL: {post_url}")
        result = _extract_question_detail(post_url)
        if result is None:
            raise ValueError(f"質問を取得できませんでした: {post_url}")
        return result

    # 設定から特定URLが指定されている場合
    config_url = settings.config["chiebukuro"].get("post_url", "")
    if config_url:
        print_substep(f"設定ファイルのURL: {config_url}")
        result = _extract_question_detail(config_url)
        if result is None:
            raise ValueError(f"質問を取得できませんでした: {config_url}")
        return result

    # ランキングから取得
    source = settings.config["chiebukuro"].get("source", "ranking")
    max_results = int(settings.config["chiebukuro"].get("max_results", 10))

    if source == "ranking":
        print_substep("デイリーランキングから取得中...")
        soup = _fetch_page(RANKING_URL)
    else:
        print_substep(f"カテゴリページから取得中...")
        soup = _fetch_page(CATEGORY_URL)

    if soup is None:
        raise ConnectionError("Yahoo知恵袋に接続できませんでした")

    links = _extract_question_links_from_ranking(soup)
    print_substep(f"{len(links)} 件の質問リンクを発見")

    if not links:
        raise ValueError("質問リンクが見つかりませんでした")

    # 未処理の質問を探す
    min_answers = int(settings.config["chiebukuro"].get("min_answers", 1))
    max_answer_length = int(settings.config["chiebukuro"].get("max_answer_length", 500))
    min_answer_length = int(settings.config["chiebukuro"].get("min_answer_length", 10))

    for link in links[:max_results]:
        print_substep(f"質問を解析中: {link}")
        result = _extract_question_detail(link)
        if result is None:
            continue

        # ブロックワードチェック
        if _contains_blocked_words(result["thread_title"]):
            print_substep("ブロックワードを検出。スキップ...")
            continue

        # 既に処理済みかチェック
        if _is_already_done(result["thread_id"]):
            print_substep("この質問は既に動画化済み。スキップ...")
            continue

        # 回答数チェック
        if len(result["comments"]) < min_answers:
            print_substep(
                f"回答数が少なすぎます ({len(result['comments'])} < {min_answers})。スキップ..."
            )
            continue

        # 回答の長さでフィルタ
        result["comments"] = [
            c
            for c in result["comments"]
            if min_answer_length <= len(c["comment_body"]) <= max_answer_length
        ]

        if not result["comments"]:
            print_substep("条件に合う回答がありません。スキップ...")
            continue

        print_substep(f"選択: {result['thread_title']}", style="bold green")
        print_substep(f"URL: {result['thread_url']}", style="bold green")
        print_substep(f"回答数: {len(result['comments'])}", style="bold blue")

        # 少し待機（礼儀正しいスクレイピング）
        time.sleep(1)
        return result

    raise ValueError("条件に合う未処理の質問が見つかりませんでした")
