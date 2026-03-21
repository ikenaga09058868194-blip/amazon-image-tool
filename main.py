#!/usr/bin/env python3
"""
Amazon → メルカリ/Yahoo!フリマ 自動出品ツール

使い方:
  # 商品情報・画像取得 + 説明文生成
  python main.py scrape "https://www.amazon.co.jp/dp/XXXXXXXXXX"

  # 商品状態を指定
  python main.py scrape "https://..." --condition "未使用に近い"

  # メルカリへの出品（フォーム自動入力）
  python main.py list-mercari ./output/ASIN_xxxxx/

  # Yahoo!フリマへの出品（フォーム自動入力）
  python main.py list-yahoo ./output/ASIN_xxxxx/

  # 取得のみ（説明文生成なし）
  python main.py scrape-only "https://..."
"""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scraper import AmazonScraper
from generator import DescriptionGenerator
from mercari_lister import MercariLister
from yahoo_lister import YahooFleaLister

load_dotenv()


CONDITIONS = [
    "新品、未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い",
]


def open_and_select_for_airdrop(images_dir: Path):
    """Finderで画像フォルダを開いて全選択し、AirDropパネルまで自動で開く"""
    images_path = str(images_dir)

    # 日本語メニュー用
    script_ja = f'''
tell application "Finder"
    activate
    open (POSIX file "{images_path}" as alias)
    delay 2
end tell
tell application "System Events"
    tell process "Finder"
        keystroke "a" using command down
        delay 0.8
        tell menu bar 1
            tell menu bar item "ファイル"
                click
                delay 0.4
                tell menu "ファイル"
                    tell menu item "共有"
                        click
                        delay 0.4
                        tell menu "共有"
                            click menu item "AirDrop"
                        end tell
                    end tell
                end tell
            end tell
        end tell
    end tell
end tell
'''

    # 英語メニュー用（フォールバック）
    script_en = f'''
tell application "Finder"
    activate
    open (POSIX file "{images_path}" as alias)
    delay 2
end tell
tell application "System Events"
    tell process "Finder"
        keystroke "a" using command down
        delay 0.8
        tell menu bar 1
            tell menu bar item "File"
                click
                delay 0.4
                tell menu "File"
                    tell menu item "Share"
                        click
                        delay 0.4
                        tell menu "Share"
                            click menu item "AirDrop"
                        end tell
                    end tell
                end tell
            end tell
        end tell
    end tell
end tell
'''

    # Terminal経由で実行（アクセシビリティ権限を持つTerminalから動かす）
    scpt_path = Path(__file__).parent / "airdrop.scpt"
    result = subprocess.run(
        ["osascript", "-e", f'tell application "Terminal" to do script "osascript {scpt_path}"'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("\n📱 AirDropパネルを開いています...")
        print("   ▶ 「iPhone 12 (2)」をクリックして送信完了！")
    else:
        subprocess.run(["open", images_path])
        print("\n📂 Finderに画像フォルダを開きました")
        print("   Command+A で全選択 → 右クリック → 共有 → AirDrop → iPhone 12 (2)")


def print_banner():
    print("""
╔══════════════════════════════════════════════════╗
║   Amazon → メルカリ/Yahoo!フリマ 出品ツール      ║
╚══════════════════════════════════════════════════╝
""")


def print_product_summary(product):
    print("\n" + "=" * 60)
    print("📦 取得した商品情報")
    print("=" * 60)
    print(f"タイトル : {product.title}")
    print(f"価格     : {product.price or '取得失敗'}")
    print(f"ブランド : {product.brand or '不明'}")
    print(f"カテゴリ : {product.category}")
    print(f"ASIN     : {product.asin}")
    print(f"画像数   : {len(product.images)} 枚")
    if product.features:
        print(f"特徴     : {product.features[0][:60]}..." if len(product.features[0]) > 60 else f"特徴: {product.features[0]}")
    print("=" * 60)


def print_listing_summary(listing):
    print("\n" + "=" * 60)
    print("🏷️  生成した出品データ")
    print("=" * 60)
    print(f"【メルカリ タイトル】\n{listing.title}")
    print(f"\n【カテゴリ】{listing.category}")
    print(f"【状態】{listing.condition}")
    print(f"【推奨価格】¥{listing.price:,}")
    print(f"\n【商品説明（最初の200文字）】")
    print(listing.description[:200] + "...")
    print("=" * 60)


async def cmd_scrape(args):
    """Amazon商品情報取得 + Claude説明文生成"""
    url = args.url
    condition = args.condition

    if condition not in CONDITIONS:
        print(f"❌ 無効な商品状態: {condition}")
        print(f"選択可能: {', '.join(CONDITIONS)}")
        sys.exit(1)

    # 出力ディレクトリ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) / f"product_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print_banner()
    print(f"🔗 URL: {url}")
    print(f"📋 商品状態: {condition}")
    print(f"📁 出力先: {output_dir}")

    # Step 1: Amazon スクレイピング
    scraper = AmazonScraper()
    product = await scraper.scrape(url, output_dir)
    print_product_summary(product)

    # ASIN別にディレクトリ名を変更
    if product.asin != "UNKNOWN":
        new_dir = output_dir.parent / f"ASIN_{product.asin}_{timestamp}"
        output_dir.rename(new_dir)
        output_dir = new_dir
        # productのimagesパスを更新
        product.images = [output_dir / "images" / p.name for p in product.images]

    if not product.images:
        print("\n⚠️  画像を取得できませんでした。URLを確認してください。")
        sys.exit(1)

    # Step 2: 説明文生成
    generator = DescriptionGenerator()
    listing = generator.generate(product, condition=condition)
    print_listing_summary(listing)

    # Step 3: 保存
    print("\n💾 データを保存中...")
    generator.save_listing(listing, output_dir)
    generator.save_listing_json(listing, output_dir)

    print(f"\n✅ 完了！出力先: {output_dir}")

    # 画像フォルダをFinderで開いて全選択
    open_and_select_for_airdrop(output_dir / "images")
    print("\n次のステップ:")
    print(f"  メルカリ出品: python main.py list-mercari {output_dir}")
    print(f"  Yahoo!出品 : python main.py list-yahoo {output_dir}")


async def cmd_scrape_only(args):
    """説明文生成なしでAmazonから画像と情報だけ取得"""
    url = args.url
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) / f"product_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print_banner()
    print(f"🔗 URL: {url}")

    scraper = AmazonScraper()
    product = await scraper.scrape(url, output_dir)
    print_product_summary(product)

    # product_info.jsonを保存（app.pyが読み取る）
    import json as _json
    info_path = output_dir / "product_info.json"
    info_path.write_text(_json.dumps({
        "title": product.title,
        "price": product.price,
        "original_price": product.original_price,
        "brand": product.brand,
        "category": product.category,
        "features": product.features,
        "description": product.description,
        "asin": product.asin,
        "url": product.url,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ 画像と情報を保存しました: {output_dir}")

    # macOS環境のみAirDrop処理を実行
    import platform
    if platform.system() == "Darwin":
        open_and_select_for_airdrop(output_dir / "images")


async def cmd_list_mercari(args):
    """メルカリのフォームを自動入力"""
    product_dir = Path(args.product_dir)
    json_path = product_dir / "listing.json"
    images_dir = product_dir / "images"

    if not json_path.exists():
        print(f"❌ listing.jsonが見つかりません: {json_path}")
        print("先に 'python main.py scrape URL' を実行してください。")
        sys.exit(1)

    if not images_dir.exists() or not list(images_dir.glob("image_*")):
        print(f"❌ 画像ファイルが見つかりません: {images_dir}")
        sys.exit(1)

    print_banner()
    lister = MercariLister()
    await lister.list_item(json_path, images_dir)


async def cmd_list_yahoo(args):
    """Yahoo!フリマのフォームを自動入力"""
    product_dir = Path(args.product_dir)
    json_path = product_dir / "listing.json"
    images_dir = product_dir / "images"

    if not json_path.exists():
        print(f"❌ listing.jsonが見つかりません: {json_path}")
        sys.exit(1)

    print_banner()
    lister = YahooFleaLister()
    await lister.list_item(json_path, images_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Amazon商品をメルカリ/Yahoo!フリマに出品するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        default="./output",
        help="出力ディレクトリ（デフォルト: ./output）",
    )

    subparsers = parser.add_subparsers(dest="command")

    # scrape コマンド
    p_scrape = subparsers.add_parser(
        "scrape",
        help="Amazon商品情報を取得してメルカリ用説明文を生成",
    )
    p_scrape.add_argument("url", help="AmazonのURL（例: https://www.amazon.co.jp/dp/XXXXXXXXXX）")
    p_scrape.add_argument(
        "--condition",
        default="新品、未使用",
        choices=CONDITIONS,
        help="商品の状態（デフォルト: 新品、未使用）",
    )

    # scrape-only コマンド
    p_scrape_only = subparsers.add_parser(
        "scrape-only",
        help="Amazon商品情報と画像のみ取得（説明文生成なし）",
    )
    p_scrape_only.add_argument("url", help="AmazonのURL")

    # list-mercari コマンド
    p_mercari = subparsers.add_parser(
        "list-mercari",
        help="メルカリのフォームを自動入力",
    )
    p_mercari.add_argument("product_dir", help="出品データのディレクトリ（listing.jsonとimages/を含む）")

    # list-yahoo コマンド
    p_yahoo = subparsers.add_parser(
        "list-yahoo",
        help="Yahoo!フリマのフォームを自動入力",
    )
    p_yahoo.add_argument("product_dir", help="出品データのディレクトリ")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "scrape": cmd_scrape,
        "scrape-only": cmd_scrape_only,
        "list-mercari": cmd_list_mercari,
        "list-yahoo": cmd_list_yahoo,
    }

    asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    main()
