"""
Yahoo!フリマ（旧PayPayフリマ）自動出品スクリプト

⚠️ 重要な注意事項:
  - Yahoo!フリマの利用規約を確認してからご使用ください
  - フォーム入力支援のみ行います。最終送信は手動で行ってください
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, Page


class YahooFleaLister:
    """Yahoo!フリマへの自動出品（フォーム入力支援）"""

    BASE_URL = "https://paypayfleamarket.yahoo.co.jp"

    async def list_item(
        self,
        listing_json_path: Path,
        images_dir: Path,
        headless: bool = False,
    ) -> None:
        """
        Yahoo!フリマのフォームを自動入力します。

        Args:
            listing_json_path: generator.pyが生成したlisting.json
            images_dir: 商品画像が入ったディレクトリ
        """
        data = json.loads(listing_json_path.read_text(encoding="utf-8"))
        yahoo_data = data.get("yahoo", data["mercari"])  # yahooデータがあればそれを使用

        image_files = sorted(images_dir.glob("image_*.jpg")) + sorted(images_dir.glob("image_*.png"))
        image_files = image_files[:10]

        print("\n🛒 Yahoo!フリマ出品フォームを開いています...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="ja-JP",
            )
            page = await context.new_page()

            await page.goto(f"{self.BASE_URL}/sell", timeout=30000)
            await page.wait_for_timeout(2000)

            # ログインチェック
            if "login" in page.url or "signin" in page.url:
                print("\n⚠️  Yahoo! IDでログインしてください。")
                print("   ログイン完了まで最大120秒待ちます...")
                try:
                    await page.wait_for_url(f"{self.BASE_URL}/**", timeout=120000)
                    await page.goto(f"{self.BASE_URL}/sell", timeout=30000)
                    await page.wait_for_timeout(3000)
                except Exception:
                    print("❌ ログインタイムアウト")
                    await browser.close()
                    return

            print("\n📝 フォームに入力中...")

            # 画像アップロード
            if image_files:
                await self._upload_images(page, image_files)

            # タイトル入力
            await self._fill_field(page, yahoo_data["title"], ["title", "商品名"], "タイトル")

            # 商品説明
            await self._fill_textarea(
                page, yahoo_data.get("description", yahoo_data.get("description", "")), "商品説明"
            )

            # 価格
            await self._fill_price(page, yahoo_data["price"])

            print("\n✅ フォームへの入力が完了しました！")
            print("=" * 50)
            print("⚠️  ブラウザを確認し、内容を確認してから出品してください。")
            print("=" * 50)
            print("\nEnterキーを押すとブラウザを閉じます...")
            input()
            await browser.close()

    async def _upload_images(self, page: Page, image_files: list[Path]) -> None:
        try:
            file_input = page.locator('input[type="file"][accept*="image"]').first
            if await file_input.is_visible(timeout=5000):
                await file_input.set_input_files([str(f) for f in image_files])
                await page.wait_for_timeout(2000)
                print(f"  ✓ 画像 {len(image_files)} 枚をアップロード")
        except Exception as e:
            print(f"  ⚠️ 画像アップロードをスキップ（手動でお願いします）: {e}")

    async def _fill_field(self, page: Page, value: str, keywords: list[str], label: str) -> None:
        for kw in keywords:
            try:
                el = page.locator(f'input[placeholder*="{kw}"], input[name*="{kw}"]').first
                if await el.is_visible(timeout=2000):
                    await el.fill(value)
                    print(f"  ✓ {label}入力: {value[:30]}...")
                    return
            except Exception:
                continue
        print(f"  ⚠️ {label}フィールドが見つかりません（手動で入力してください）")

    async def _fill_textarea(self, page: Page, value: str, label: str) -> None:
        try:
            el = page.locator("textarea").first
            if await el.is_visible(timeout=3000):
                await el.fill(value)
                print(f"  ✓ {label}入力（{len(value)}文字）")
        except Exception as e:
            print(f"  ⚠️ {label}入力エラー: {e}")

    async def _fill_price(self, page: Page, price: int) -> None:
        try:
            el = page.locator('input[placeholder*="価格"], input[placeholder*="¥"]').first
            if await el.is_visible(timeout=3000):
                await el.fill(str(price))
                print(f"  ✓ 価格入力: ¥{price:,}")
        except Exception as e:
            print(f"  ⚠️ 価格入力エラー: {e}")
