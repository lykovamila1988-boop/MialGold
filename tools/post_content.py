#!/usr/bin/env python3
"""
post_content.py — публикация в Instagram для MILA GOLD.

⚠️  Instagram Graph API публикует только по ПУБЛИЧНОМУ URL картинки/видео
    (локальный файл с диска загрузить нельзя). Сначала загрузите медиа
    на любой публичный хостинг и используйте прямую ссылку (https://...).

Использование:
    # Фото
    python post_content.py photo --url "https://.../foto.jpg" \
        --caption "Новая коллекция ✨ #milagold"

    # Reel (видео)
    python post_content.py reel --url "https://.../video.mp4" \
        --caption "Смотрите 🔥" --cover "https://.../cover.jpg"

    # Кросс-постинг: опубликовать ОДНОВРЕМЕННО в Instagram и Threads
    python post_content.py photo --url "https://.../foto.jpg" \
        --caption "..." --threads

Публикация идёт в 2 шага: (1) создать контейнер, (2) опубликовать.
Для Reels скрипт ждёт окончания обработки видео перед публикацией.
"""
import sys
import argparse
from _common import (load_config, load_threads_config,
                     graph_post, save_report, run_cli, wait_until_ready)


def create_photo_container(cfg, image_url, caption):
    return graph_post(cfg, f"{cfg['node']}/media", {
        "image_url": image_url,
        "caption": caption,
    })["id"]


def create_reel_container(cfg, video_url, caption, cover_url):
    data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
    }
    if cover_url:
        data["cover_url"] = cover_url
    return graph_post(cfg, f"{cfg['node']}/media", data)["id"]


def publish(cfg, container_id):
    return graph_post(cfg, f"{cfg['node']}/media_publish", {
        "creation_id": container_id,
    })


def cross_post_threads(kind, media_url, caption):
    """
    Дублирует публикацию в Threads (отдельный API). photo→image, reel→video.
    Возвращает media_id треда или None при ошибке конфигурации.
    """
    tcfg = load_threads_config()
    tkind = "image" if kind == "photo" else "video"
    data = {"media_type": tkind.upper(), "text": caption}
    data["image_url" if tkind == "image" else "video_url"] = media_url
    container = graph_post(tcfg, f"{tcfg['user_id']}/threads", data)["id"]

    # Ждём обработку контейнера (важно для видео).
    wait_until_ready(tcfg, container, status_field="status",
                     fail_codes=("ERROR", "EXPIRED"), fields="status,error_message",
                     on_tick=lambda c: print(f"   …Threads обработка ({c}), жду…"))

    result = graph_post(tcfg, f"{tcfg['user_id']}/threads_publish",
                        {"creation_id": container})
    return result.get("id")


def main():
    p = argparse.ArgumentParser(description="Публикация в Instagram MILA GOLD")
    p.add_argument("kind", choices=["photo", "reel"], help="тип публикации")
    p.add_argument("--url", required=True, help="публичный URL медиа (https://...)")
    p.add_argument("--caption", default="", help="текст под публикацией")
    p.add_argument("--cover", default="", help="(reel) URL обложки")
    p.add_argument("--threads", action="store_true",
                   help="продублировать публикацию в Threads")
    args = p.parse_args()

    if not args.url.startswith("http"):
        sys.exit("--url должен быть публичной ссылкой https://...")

    cfg = load_config()

    print(f"\n📤 Создаю контейнер ({args.kind})…")
    if args.kind == "photo":
        container = create_photo_container(cfg, args.url, args.caption)
    else:
        container = create_reel_container(cfg, args.url, args.caption, args.cover)
        wait_until_ready(cfg, container, fields="status_code,status",
                         on_tick=lambda c: print(f"   …обработка видео ({c}), жду…"))

    print("📤 Публикую…")
    result = publish(cfg, container)
    media_id = result.get("id")

    report = {"kind": args.kind, "media_id": media_id,
              "caption": args.caption, "url": args.url}

    if args.threads:
        print("\n🧵 Дублирую в Threads…")
        threads_id = cross_post_threads(args.kind, args.url, args.caption)
        report["threads_media_id"] = threads_id
        print(f"✅ Threads: media_id = {threads_id}")

    save_report("post", report)
    print(f"\n✅ Опубликовано! media_id = {media_id}\n")


if __name__ == "__main__":
    run_cli(main)
