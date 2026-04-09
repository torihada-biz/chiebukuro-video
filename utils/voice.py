import re
import sys
import time as pytime
from datetime import datetime
from time import sleep

from cleantext import clean
from requests import Response

from utils import settings

if sys.version_info[0] >= 3:
    from datetime import timezone


def check_ratelimit(response: Response) -> bool:
    """
    Checks if the response is a ratelimit response.
    If it is, it sleeps for the time specified in the response.
    """
    if response.status_code == 429:
        try:
            time = int(response.headers["X-RateLimit-Reset"])
            print(f"Ratelimit hit. Sleeping for {time - int(pytime.time())} seconds.")
            sleep_until(time)
            return False
        except KeyError:
            return False

    return True


def sleep_until(time) -> None:
    """
    Pause your program until a specific end time.
    'time' is either a valid datetime object or unix timestamp in seconds
    """
    end = time

    if isinstance(time, datetime):
        if sys.version_info[0] >= 3 and time.tzinfo:
            end = time.astimezone(timezone.utc).timestamp()
        else:
            zoneDiff = pytime.time() - (datetime.now() - datetime(1970, 1, 1)).total_seconds()
            end = (time - datetime(1970, 1, 1)).total_seconds() + zoneDiff

    if not isinstance(end, (int, float)):
        raise Exception("The time parameter is not a number or datetime object")

    while True:
        now = pytime.time()
        diff = end - now
        if diff <= 0:
            break
        else:
            sleep(diff / 2)


def sanitize_text(text: str) -> str:
    """TTS用にテキストをサニタイズする。
    URL, HTMLタグ, 特殊記号を除去。日本語の句読点は保持。

    Args:
        text: サニタイズするテキスト

    Returns:
        サニタイズ済みテキスト
    """
    # URLを除去
    regex_urls = r"((http|https)://)?[a-zA-Z0-9./\\?:@\-_=#]+\.[a-zA-Z]{2,6}[a-zA-Z0-9.&/\\?:@\-_=#]*"
    result = re.sub(regex_urls, " ", text)

    # HTMLタグを除去
    result = re.sub(r"<[^>]+>", " ", result)

    # 特殊記号を除去（日本語の句読点・かな・漢字・全角記号は保持）
    regex_expr = r'[\^_~@&;#:\-%*/{}\[\]\\|<>=+]'
    result = re.sub(regex_expr, " ", result)

    # 絵文字除去（設定で有効時）
    # clean-textのclean()は日本語をローマ字化するため使用禁止
    # Supplemental Planes (U+1F000以上) の絵文字ブロックのみ除去し、
    # BMP内のCJK文字 (U+3000-U+9FFF) には触れない
    if settings.config["settings"]["tts"]["no_emojis"]:
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols extended-A
            "\U0000FE00-\U0000FE0F"  # variation selectors
            "\U0000200D"             # zero width joiner
            "]+",
            flags=re.UNICODE,
        )
        result = emoji_pattern.sub(" ", result)

    # 余分な空白を除去
    return " ".join(result.split())
