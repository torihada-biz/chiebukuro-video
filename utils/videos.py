import json
import time

from utils import settings
from utils.console import print_step


def check_done(thread_id: str) -> bool:
    """指定IDが既に処理済みかチェック

    Args:
        thread_id: スレッドID

    Returns:
        bool: 処理済みならTrue
    """
    with open("./video_creation/data/videos.json", "r", encoding="utf-8") as done_vids_raw:
        done_videos = json.load(done_vids_raw)
    for video in done_videos:
        if video["id"] == str(thread_id):
            return True
    return False


def save_data(subreddit: str, filename: str, reddit_title: str, reddit_id: str, credit: str):
    """動画生成済みデータをJSONに保存

    Args:
        subreddit: カテゴリ名
        filename: 動画ファイル名
        reddit_title: タイトル
        reddit_id: ID
        credit: 背景クレジット
    """
    with open("./video_creation/data/videos.json", "r+", encoding="utf-8") as raw_vids:
        done_vids = json.load(raw_vids)
        if reddit_id in [video["id"] for video in done_vids]:
            return
        payload = {
            "subreddit": subreddit,
            "id": reddit_id,
            "time": str(int(time.time())),
            "background_credit": credit,
            "reddit_title": reddit_title,
            "filename": filename,
        }
        done_vids.append(payload)
        raw_vids.seek(0)
        json.dump(done_vids, raw_vids, ensure_ascii=False, indent=4)
