#!/usr/bin/env python3
"""
クリップボード監視スクリプト

iPhoneでAmazonのURLをコピーすると自動的に画像取得とAirDropを実行します。

使い方:
  python watch_clipboard.py

実行後はiPhoneでAmazonURLをコピーするだけでOK！
"""

import subprocess
import sys
import time
from pathlib import Path


def get_clipboard() -> str:
    """クリップボードの内容を取得"""
    result = subprocess.run(["pbpaste"], capture_output=True, text=True)
    return result.stdout.strip()


def is_amazon_url(text: str) -> bool:
    """AmazonのURLかどうか判定"""
    amazon_domains = [
        "amazon.co.jp",
        "amazon.com",
        "amzn.asia",
        "amzn.to",
        "a.co",
    ]
    return any(domain in text for domain in amazon_domains)


def run_scraper(url: str):
    """スクレイパーを実行"""
    script_dir = Path(__file__).parent
    cmd = [sys.executable, str(script_dir / "main.py"), "scrape-only", url]
    subprocess.run(cmd, cwd=str(script_dir))


def notify(title: str, message: str):
    """Mac通知を表示"""
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script])


def main():
    print("=" * 50)
    print("📋 クリップボード監視中...")
    print("=" * 50)
    print("iPhoneでAmazonのURLをコピーすると自動実行します")
    print("終了するには Ctrl+C を押してください")
    print()

    last_clipboard = get_clipboard()
    last_url = ""

    notify("✅ 監視スタート", "iPhoneでAmazon URLをコピーしてください")

    while True:
        try:
            current = get_clipboard()

            if current != last_clipboard:
                last_clipboard = current

                if is_amazon_url(current) and current != last_url:
                    last_url = current
                    print(f"\n🔗 Amazon URLを検出: {current[:60]}...")
                    notify("🛍️ Amazon URL検出！", "画像取得を開始します...")
                    run_scraper(current)
                    print("\n📋 次のURLをコピーするのを待っています...")

            time.sleep(2)

        except KeyboardInterrupt:
            print("\n\n監視を終了しました。")
            break


if __name__ == "__main__":
    main()
