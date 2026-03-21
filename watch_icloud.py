#!/usr/bin/env python3
"""
iCloud Drive経由でAmazon URLを受け取り自動実行するスクリプト

【iPhone側の操作】（毎回これだけ！）
1. Amazonアプリで商品ページを開く
2. 共有ボタン（□↑）をタップ
3. 「ファイル」をタップ
4. 「iCloud Drive」を選んで保存

→ Macが自動で画像取得 → AirDropパネルが開く！
"""

import plistlib
import subprocess
import sys
import time
from pathlib import Path

ICLOUD_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"


def extract_url_from_webloc(path: Path) -> str | None:
    """weblocファイル（URL共有ファイル）からURLを取り出す"""
    try:
        with open(path, "rb") as f:
            data = plistlib.load(f)
        return data.get("URL")
    except Exception:
        return None


def get_processed_files() -> set:
    done_file = Path(__file__).parent / ".processed_files.txt"
    if done_file.exists():
        return set(done_file.read_text().splitlines())
    return set()


def save_processed_file(name: str):
    done_file = Path(__file__).parent / ".processed_files.txt"
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
    print("☁️  iCloud Drive監視中...")
    print("=" * 50)
    print("iPhoneで 共有→ファイル→iCloud Drive で保存してください")
    print("終了するには Ctrl+C を押してください\n")

    notify("✅ 監視スタート", "iPhoneで共有→ファイル→iCloud Driveで保存してください")

    processed = get_processed_files()

    while True:
        try:
            # iCloud Drive内の.weblocファイルを監視
            for webloc in ICLOUD_DIR.glob("*.webloc"):
                key = webloc.name
                if key not in processed:
                    url = extract_url_from_webloc(webloc)
                    if url and ("amazon" in url or "amzn" in url):
                        processed.add(key)
                        save_processed_file(key)
                        print(f"\n🔗 Amazon URL検出: {url[:60]}...")
                        notify("🛍️ Amazon URL受信！", "画像取得を開始します...")
                        run_scraper(url)
                        # 処理済みファイルを削除
                        webloc.unlink(missing_ok=True)
                        print("\n☁️  次の商品を待っています...")
                    elif key not in processed:
                        processed.add(key)

            time.sleep(3)

        except KeyboardInterrupt:
            print("\n\n監視を終了しました。")
            break


if __name__ == "__main__":
    main()
