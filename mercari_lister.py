"""
メルカリ 自動出品スクリプト

⚠️ 重要な注意事項:
  - メルカリの利用規約では自動化ツールの使用が制限される場合があります
  - 本スクリプトは「フォームの自動入力支援」として動作します
  - 最終的な「出品する」ボタンは手動で押す仕様にしています
  - 大量の自動出品はアカウント停止のリスクがあります
  - 個人の少量利用の範囲でお使いください
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page


MERCARI_CATEGORY_MAP = {
    "iPhone": "スマートフォン/携帯電話 > iPhone",
    "スマートフォン": "スマートフォン/携帯電話 > Android",
    "タブレット": "PC/タブレット > タブレット",
    "ノートPC": "PC/タブレット > ノートPC",
    "ゲーム": "おもちゃ/ホビー/ゲーム",
    "カメラ": "家電/カメラ > デジタルカメラ",
}

CONDITION_MAP = {
    "新品、未使用": "new",
    "未使用に近い": "like_new",
    "目立った傷や汚れなし": "good",
    "やや傷や汚れあり": "fair",
    "傷や汚れあり": "poor",
    "全体的に状態が悪い": "bad",
}


class MercariLister:
    """メルカリへの自動出品（フォーム入力支援）"""

    BASE_URL = "https://jp.mercari.com"

    async def list_item(
        self,
        listing_json_path: Path,
        images_dir: Path,
        headless: bool = False,
    ) -> None:
        """
        出品データJSONと画像ディレクトリを使ってメルカリのフォームを自動入力します。
        最終送信はユーザーが手動で行ってください。

        Args:
            listing_json_path: generator.pyが生成したlisting.json
            images_dir: 商品画像が入ったディレクトリ
            headless: Trueにするとブラウザ非表示（デバッグ時はFalse推奨）
        """
        data = json.loads(listing_json_path.read_text(encoding="utf-8"))
        mercari_data = data["mercari"]

        # 画像ファイル一覧を取得（最大10枚）
        image_files = sorted(images_dir.glob("image_*.jpg")) + sorted(images_dir.glob("image_*.png"))
        image_files = image_files[:10]

        if not image_files:
            print("❌ 画像ファイルが見つかりません")
            return

        print("\n🛒 メルカリ出品フォームを開いています...")
        print("   ブラウザにログインしてください。")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            # 出品ページを開く
            await page.goto(f"{self.BASE_URL}/sell/flow/new", timeout=30000)
            await page.wait_for_timeout(2000)

            # ログインが必要な場合
            if "login" in page.url or "signin" in page.url:
                print("\n⚠️  ログインが必要です。")
                print("   ブラウザでメルカリにログインしてください。")
                print("   ログイン完了まで最大120秒待ちます...")
                try:
                    await page.wait_for_url(
                        f"{self.BASE_URL}/**",
                        timeout=120000,
                    )
                    # ログイン後に出品ページへ再移動
                    await page.goto(f"{self.BASE_URL}/sell/flow/new", timeout=30000)
                    await page.wait_for_timeout(3000)
                except Exception:
                    print("❌ ログインタイムアウト")
                    await browser.close()
                    return

            print("\n📝 フォームに入力中...")

            # 画像アップロード
            await self._upload_images(page, image_files)

            # カテゴリ設定
            await self._set_category(page, mercari_data.get("category", "その他"))

            # 商品名
            await self._fill_title(page, mercari_data["title"])

            # 商品の状態
            await self._set_condition(page, mercari_data["condition"])

            # 商品説明
            await self._fill_description(page, mercari_data["description"])

            # 価格
            await self._fill_price(page, mercari_data["price"])

            print("\n✅ フォームへの入力が完了しました！")
            print("=" * 50)
            print("⚠️  ブラウザを確認し、内容を確認してから")
            print("   「出品する」ボタンを押してください。")
            print("=" * 50)
            print("\nEnterキーを押すとブラウザを閉じます...")
            input()
            await browser.close()

    # ------------------------------------------------------------------
    # フォーム入力ヘルパー
    # ------------------------------------------------------------------

    async def _upload_images(self, page: Page, image_files: list[Path]) -> None:
        """画像をアップロード"""
        try:
            # 画像アップロード用のinput要素を探す
            file_input = page.locator('input[type="file"][accept*="image"]').first
            if await file_input.is_visible(timeout=5000):
                await file_input.set_input_files([str(f) for f in image_files])
                await page.wait_for_timeout(2000)
                print(f"  ✓ 画像 {len(image_files)} 枚をアップロード")
            else:
                # 画像追加ボタンをクリックしてから
                add_btn = page.locator('[data-testid="image-upload"], .add-image-button, [aria-label*="画像"]').first
                if await add_btn.is_visible(timeout=3000):
                    await add_btn.click()
                    await page.wait_for_timeout(1000)
                    file_input = page.locator('input[type="file"]').first
                    await file_input.set_input_files([str(f) for f in image_files])
                    await page.wait_for_timeout(2000)
                    print(f"  ✓ 画像 {len(image_files)} 枚をアップロード")
        except Exception as e:
            print(f"  ⚠️ 画像アップロードをスキップ（手動でお願いします）: {e}")

    async def _fill_title(self, page: Page, title: str) -> None:
        """商品名を入力"""
        try:
            selectors = [
                '[data-testid="title"]',
                'input[placeholder*="タイトル"]',
                'input[placeholder*="商品名"]',
                '#title',
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.clear()
                        await el.fill(title)
                        print(f"  ✓ タイトル入力: {title}")
                        return
                except Exception:
                    continue
            print("  ⚠️ タイトル入力フィールドが見つかりません（手動で入力してください）")
        except Exception as e:
            print(f"  ⚠️ タイトル入力エラー: {e}")

    async def _fill_description(self, page: Page, description: str) -> None:
        """商品説明を入力"""
        try:
            selectors = [
                '[data-testid="description"]',
                'textarea[placeholder*="説明"]',
                'textarea[placeholder*="商品の説明"]',
                '#description',
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.clear()
                        await el.fill(description)
                        print(f"  ✓ 商品説明入力（{len(description)}文字）")
                        return
                except Exception:
                    continue
            print("  ⚠️ 商品説明フィールドが見つかりません（手動で入力してください）")
        except Exception as e:
            print(f"  ⚠️ 商品説明入力エラー: {e}")

    async def _fill_price(self, page: Page, price: int) -> None:
        """販売価格を入力"""
        try:
            selectors = [
                '[data-testid="price"]',
                'input[placeholder*="価格"]',
                'input[placeholder*="¥"]',
                '#price',
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.clear()
                        await el.fill(str(price))
                        print(f"  ✓ 価格入力: ¥{price:,}")
                        return
                except Exception:
                    continue
            print("  ⚠️ 価格入力フィールドが見つかりません（手動で入力してください）")
        except Exception as e:
            print(f"  ⚠️ 価格入力エラー: {e}")

    async def _set_category(self, page: Page, category: str) -> None:
        """カテゴリを設定（メルカリのUI変更が多いため手動案内）"""
        print(f"  📂 カテゴリ: '{category}' を手動で選択してください")

    async def _set_condition(self, page: Page, condition: str) -> None:
        """商品の状態を選択"""
        print(f"  📋 商品の状態: '{condition}' を手動で選択してください")
