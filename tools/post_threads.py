#!/usr/bin/env python3
"""
post_threads.py — публикация в Threads для MILA GOLD.

⚠️  Threads API — ОТДЕЛЬНЫЙ от Instagram: своё приложение, свой токен
    (THREADS_ACCESS_TOKEN, THREADS_USER_ID в .env) и другой хост
    (graph.threads.net). Картинки/видео — только по ПУБЛИЧНОМУ URL.

Использование:
    # Текстовый пост
    python post_threads.py text --text "Точка выбора есть всегда 🧡"

    # Пост с картинкой (text — необязательная подпись)
    python post_threads.py image --url "https://.../foto.jpg" \
        --text "Новый практикум"

    # Пост с видео
    python post_threads.py video --url "https://.../video.mp4" \
        --text "Смотри до конца"

Публикация идёт в 2 шага: (1) создать контейнер, (2) опубликовать.
Перед публикацией скрипт ждёт, пока контейнер обработается (status=FINISHED) —
особенно важно для видео.
"""
import sys
import argparse
from _common import (load_threads_config, graph_post, save_report,
                     run_cli, wait_until_ready)


def create_container(cfg, kind, media_url, text):
    """Создаёт медиа-контейнер Threads и возвращает его id."""
    data = {"media_type": kind.upper()}  # TEXT / IMAGE / VIDEO
    if text:
        data["text"] = text
    if kind == "image":
        data["image_url"] = media_url
    elif kind == "video":
        data["video_url"] = media_url
    return graph_post(cfg, f"{cfg['user_id']}/threads", data)["id"]


def publish(cfg, container_id):
    return graph_post(cfg, f"{cfg['user_id']}/threads_publish", {
        "creation_id": container_id,
    })


def main():
    p = argparse.ArgumentParser(description="Публикация в Threads MILA GOLD")
    p.add_argument("kind", choices=["text", "image", "video"],
                   help="тип публикации")
    p.add_argument("--text", default="", help="текст поста / подпись")
    p.add_argument("--url", default="",
                   help="публичный URL медиа (https://...) — для image/video")
    args = p.parse_args()

    if args.kind in ("image", "video"):
        if not args.url.startswith("http"):
            sys.exit(f"--url обязателен и должен быть публичной ссылкой "
                     f"https://... для типа '{args.kind}'")
    elif not args.text:
        sys.exit("--text обязателен для текстового поста")

    cfg = load_threads_config()

    print(f"\n📤 Создаю контейнер Threads ({args.kind})…")
    container = create_container(cfg, args.kind, args.url, args.text)
    wait_until_ready(cfg, container, status_field="status",
                     fail_codes=("ERROR", "EXPIRED"), fields="status,error_message",
                     on_tick=lambda c: print(f"   …обработка ({c}), жду…"))

    print("📤 Публикую…")
    result = publish(cfg, container)
    media_id = result.get("id")

    save_report("threads_post", {"kind": args.kind, "media_id": media_id,
                                 "text": args.text, "url": args.url})
    print(f"\n✅ Опубликовано в Threads! media_id = {media_id}\n")


if __name__ == "__main__":
    run_cli(main)
