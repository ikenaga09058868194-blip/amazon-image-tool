#!/usr/bin/env python3
"""
AirDrop経由でAmazon URLを受け取り自動実行するスクリプト

【毎回の使い方】
1. Amazonアプリで商品ページを開く
2. 共有ボタン（□↑）→ AirDrop → MacBook を選ぶ
3. 自動で画像取得 → AirDropパネルが開く！
"""

import plistlib
import subprocess
import sys
import time
from pathlib import Path

WATCH_DIRS = [
    Path.home() / "Downloads",
    Path.home() / "Desktop",
]


def extract_url_from_webloc(path: Path) -> str | None:
    """weblocファイルからURLを取り出す"""
    try:
        with open(path, "rb") as f:
            data = plistlib.load(f)
        return data.get("URL")
    except Exception:
        return None


def get_processed_files() -> set:
    done_file = Path(__file__).parent / ".processed_airdrop.txt"
    if done_file.exists():
        return set(done_file.read_text().splitlines())
    return set()


def save_processed_file(name: str):
    done_file = Path(__file__).parent / ".processed_airdrop.txt"
    with open(done_file, "a") as f:
        f.write(name + "\n")


def run_scraper(url: str):
    script_dir = Path(__file__).parent
    cmd = [sys.executable, str(script_dir / "main.py"), "scrape-only", url]
    subprocess.run(cmd, cwd=str(script_dir))


def notify(title: str, message: str):
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script])


def main():
    print("=" * 50)
    print("📡 AirDrop受信待ち...")
    print("=" * 50)
    print("iPhoneで 共有 → AirDrop → MacBook を選んでください")
    print("終了するには Ctrl+C を押してください\n")

    notify("✅ 監視スタート", "iPhoneで共有→AirDrop→MacBookを選んでください")

    processed = get_processed_files()

    while True:
        try:
            for watch_dir in WATCH_DIRS:
                for webloc in watch_dir.glob("*.webloc"):
                    key = str(webloc)
                    if key not in processed:
                        url = extract_url_from_webloc(webloc)
                        if url and ("amazon" in url or "amzn" in url):
                            processed.add(key)
                            save_processed_file(key)
                            print(f"\n🔗 Amazon URL検出: {url[:60]}...")
                            notify("🛍️ AirDrop受信！", "画像取得を開始します...")
                            run_scraper(url)
                            webloc.unlink(missing_ok=True)
                            print("\n📡 次の商品を待っています...")
                        else:
                            processed.add(key)

            time.sleep(2)

        except KeyboardInterrupt:
            print("\n\n監視を終了しました。")
            break


if __name__ == "__main__":
    main()
