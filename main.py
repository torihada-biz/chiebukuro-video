#!/usr/bin/env python
import math
import sys
from os import name
from pathlib import Path
from subprocess import Popen
from typing import Dict, NoReturn

from chiebukuro.scraper import get_chiebukuro_threads
from utils import settings
from utils.cleanup import cleanup
from utils.console import print_markdown, print_step, print_substep
from utils.ffmpeg_install import ffmpeg_install
from utils.id import extract_id
from video_creation.background import (
    chop_background,
    download_background_audio,
    download_background_video,
    get_background_config,
)
from video_creation.final_video import make_final_video
from video_creation.text_image_generator import generate_text_images
from video_creation.voices import save_text_to_mp3

__VERSION__ = "4.0.0"

print(
    """
██╗  ██╗██╗███████╗██████╗ ██╗   ██╗██╗  ██╗██╗   ██╗██████╗  ██████╗
██║ ██╔╝██║██╔════╝██╔══██╗██║   ██║██║ ██╔╝██║   ██║██╔══██╗██╔═══██╗
█████╔╝ ██║█████╗  ██████╔╝██║   ██║█████╔╝ ██║   ██║██████╔╝██║   ██║
██╔═██╗ ██║██╔══╝  ██╔══██╗██║   ██║██╔═██╗ ██║   ██║██╔══██╗██║   ██║
██║  ██╗██║███████╗██████╔╝╚██████╔╝██║  ██╗╚██████╔╝██║  ██║╚██████╔╝
╚═╝  ╚═╝╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝
    知恵袋ショート動画メーカー v{version}
""".format(version=__VERSION__)
)
print_markdown(
    "### Yahoo知恵袋の面白いQ&Aから縦型ショート動画を自動生成します"
)

thread_id: str
thread_object: Dict[str, str | list]


def main(post_url=None) -> None:
    global thread_id, thread_object
    thread_object = get_chiebukuro_threads(post_url)
    thread_id = extract_id(thread_object)
    print_substep(f"スレッドID: {thread_id}", style="bold blue")
    length, number_of_comments = save_text_to_mp3(thread_object)
    length = math.ceil(length)
    generate_text_images(thread_object, number_of_comments)
    bg_config = {
        "video": get_background_config("video"),
        "audio": get_background_config("audio"),
    }
    download_background_video(bg_config["video"])
    download_background_audio(bg_config["audio"])
    chop_background(bg_config, length, thread_object)
    make_final_video(number_of_comments, length, thread_object, bg_config)


def run_many(times) -> None:
    for x in range(1, times + 1):
        print_step(f"{x}/{times} 回目の実行")
        main()
        Popen("cls" if name == "nt" else "clear", shell=True).wait()


def shutdown() -> NoReturn:
    if "thread_id" in globals():
        print_markdown("## 一時ファイルを削除中")
        cleanup(thread_id)

    print("終了します...")
    sys.exit()


if __name__ == "__main__":
    if sys.version_info.major != 3 or sys.version_info.minor not in [10, 11, 12, 13]:
        print(
            "Python 3.10以上が必要です。対応するバージョンをインストールしてください。"
        )
        sys.exit()
    ffmpeg_install()
    directory = Path().absolute()
    config = settings.check_toml(
        f"{directory}/utils/.config.template.chiebukuro.toml",
        f"{directory}/config.toml",
    )
    config is False and sys.exit()

    if (
        not settings.config["settings"]["tts"]["tiktok_sessionid"]
        or settings.config["settings"]["tts"]["tiktok_sessionid"] == ""
    ) and config["settings"]["tts"]["voice_choice"] == "tiktok":
        print_substep(
            "TikTok TTSにはsessionidが必要です。ドキュメントを確認してください。",
            "bold red",
        )
        sys.exit()
    try:
        if config["chiebukuro"].get("post_url"):
            urls = config["chiebukuro"]["post_url"].split("+")
            for index, url in enumerate(urls):
                url = url.strip()
                if not url:
                    continue
                index += 1
                print_step(f"{index}/{len(urls)} 件目の質問を処理中")
                main(url)
                Popen("cls" if name == "nt" else "clear", shell=True).wait()
        elif config["settings"]["times_to_run"]:
            run_many(config["settings"]["times_to_run"])
        else:
            main()
    except KeyboardInterrupt:
        shutdown()
    except Exception as err:
        config["settings"]["tts"]["tiktok_sessionid"] = "REDACTED"
        config["settings"]["tts"]["elevenlabs_api_key"] = "REDACTED"
        config["settings"]["tts"]["openai_api_key"] = "REDACTED"
        print_step(
            f"エラーが発生しました。再試行するか、GitHubでissueを報告してください。\n"
            f"Version: {__VERSION__} \n"
            f"Error: {err} \n"
            f'Config: {config["settings"]}'
        )
        raise err
