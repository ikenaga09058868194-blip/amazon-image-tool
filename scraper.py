"""
Amazon商品スクレイパー
商品ページから情報・画像を取得して保存します
"""

import asyncio
import re
import json
import httpx
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext


@dataclass
class ProductData:
    title: str
    price: Optional[str]
    original_price: Optional[str]
    features: list[str]
    description: str
    category: str
    images: list[Path]
    url: str
    asin: str
    brand: Optional[str] = None


class AmazonScraper:
    """AmazonページからJavaScript内の高解像度画像URLを取得してダウンロード"""

    async def scrape(self, url: str, output_dir: Path) -> ProductData:
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
                locale="ja-JP",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = await context.new_page()

            print(f"📦 Amazon商品ページを開いています: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Cookie同意バナーを閉じる
            for selector in ["#sp-cc-accept", "#accept-cookie-announce"]:
                try:
                    btn = page.locator(selector)
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

            print("📝 商品情報を取得中...")
            title = await self._get_title(page)
            price, original_price = await self._get_price(page)
            features = await self._get_features(page)
            description = await self._get_description(page)
            category = await self._get_category(page)
            brand = await self._get_brand(page)
            asin = self._extract_asin(url)

            print("🖼️  商品画像URLを収集中...")
            image_urls = await self._get_image_urls(page, context)

            await browser.close()

        print(f"📥 画像をダウンロード中（{len(image_urls[:6])}枚）...")
        images = await self._download_images(image_urls[:6], images_dir)

        return ProductData(
            title=title,
            price=price,
            original_price=original_price,
            features=features,
            description=description,
            category=category,
            images=images,
            url=url,
            asin=asin,
            brand=brand,
        )

    # ------------------------------------------------------------------
    # 情報取得ヘルパー
    # ------------------------------------------------------------------

    async def _get_title(self, page: Page) -> str:
        for sel in ["#productTitle", "h1#title span", ".product-title-word-break"]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=3000):
                    text = await el.text_content()
                    if text:
                        return text.strip()
            except Exception:
                continue
        return "Unknown Product"

    async def _get_price(self, page: Page) -> tuple[Optional[str], Optional[str]]:
        price = None
        original_price = None

        price_selectors = [
            ".a-price[data-a-size='xl'] .a-offscreen",
            ".a-price[data-a-size='l'] .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price .a-offscreen",
        ]
        for sel in price_selectors:
            try:
                el = page.locator(sel).first
                text = await el.text_content(timeout=2000)
                if text and "¥" in text:
                    price = text.strip()
                    break
            except Exception:
                continue

        orig_selectors = [
            ".a-price.a-text-price .a-offscreen",
            "#priceblock_listprice",
            ".a-text-strike .a-offscreen",
        ]
        for sel in orig_selectors:
            try:
                el = page.locator(sel).first
                text = await el.text_content(timeout=2000)
                if text and "¥" in text:
                    original_price = text.strip()
                    break
            except Exception:
                continue

        return price, original_price

    async def _get_features(self, page: Page) -> list[str]:
        features = []
        try:
            items = page.locator("#feature-bullets li:not(.aok-hidden)")
            count = await items.count()
            for i in range(min(count, 12)):
                text = await items.nth(i).text_content()
                if text:
                    text = text.strip()
                    if text:
                        features.append(text)
        except Exception:
            pass
        return features

    async def _get_description(self, page: Page) -> str:
        for sel in [
            "#productDescription p",
            "#bookDescription_feature_div .a-expander-content p",
            "#aplus p",
        ]:
            try:
                elements = page.locator(sel)
                count = await elements.count()
                texts = []
                for i in range(min(count, 10)):
                    text = await elements.nth(i).text_content()
                    if text:
                        texts.append(text.strip())
                if texts:
                    return " ".join(texts)[:3000]
            except Exception:
                continue
        return ""

    async def _get_category(self, page: Page) -> str:
        try:
            items = page.locator("#wayfinding-breadcrumbs_feature_div a")
            count = await items.count()
            parts = []
            for i in range(count):
                text = await items.nth(i).text_content()
                if text:
                    parts.append(text.strip())
            if parts:
                return " > ".join(parts)
        except Exception:
            pass
        return "その他"

    async def _get_brand(self, page: Page) -> Optional[str]:
        for sel in [
            "#bylineInfo",
            "a#bylineInfo",
            ".po-brand .a-span9",
        ]:
            try:
                el = page.locator(sel).first
                text = await el.text_content(timeout=2000)
                if text:
                    return text.strip().replace("ブランド: ", "").replace("Visit the ", "").replace(" Store", "")
            except Exception:
                continue
        return None

    def _extract_asin(self, url: str) -> str:
        match = re.search(r"/dp/([A-Z0-9]{10})", url)
        return match.group(1) if match else "UNKNOWN"

    # ------------------------------------------------------------------
    # 画像URL取得
    # ------------------------------------------------------------------

    async def _get_image_urls(self, page: Page, context: BrowserContext) -> list[str]:
        """複数の方法でAmazon商品画像URLを取得"""
        image_urls: list[str] = []

        # 方法1: JavaScriptからcolorImagesデータを抽出
        try:
            data = await page.evaluate(
                """
                () => {
                    const scripts = Array.from(document.querySelectorAll('script'));
                    for (const script of scripts) {
                        const text = script.textContent || '';
                        const match = text.match(/"colorImages"\\s*:\\s*\\{\\s*"initial"\\s*:\\s*(\\[.*?\\])\\s*\\}/s);
                        if (match) {
                            try { return JSON.parse(match[1]); } catch(e) {}
                        }
                        const match2 = text.match(/'colorImages'\\s*:\\s*\\{\\s*'initial'\\s*:\\s*(\\[.*?\\])/s);
                        if (match2) {
                            try { return JSON.parse(match2[1]); } catch(e) {}
                        }
                    }
                    return null;
                }
            """
            )
            if data and isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        for key in ("hiRes", "large", "main"):
                            val = item.get(key)
                            if val and isinstance(val, str) and val.startswith("http"):
                                if val not in image_urls:
                                    image_urls.append(val)
                                break
        except Exception as e:
            print(f"  (JS抽出エラー: {e})")

        # 方法2: サムネイルを全部クリックして画像URLを収集
        try:
            # サムネイルボタンを全部取得
            thumb_selectors = [
                "#altImages li.item img",
                "#altImages .a-button-thumbnail img",
                "#altImages img",
            ]
            thumbnails = None
            count = 0
            for sel in thumb_selectors:
                thumbnails = page.locator(sel)
                count = await thumbnails.count()
                if count > 0:
                    break

            if count > 0:
                print(f"  サムネイル {count} 個を発見、クリック中...")
                for i in range(min(count, 10)):
                    try:
                        await thumbnails.nth(i).scroll_into_view_if_needed(timeout=2000)
                        await thumbnails.nth(i).click(timeout=3000)
                        await page.wait_for_timeout(800)

                        # メイン画像のURLを取得
                        for img_sel in ["#imgTagWrapperId img", "#landingImage", "#main-image"]:
                            try:
                                src = await page.locator(img_sel).first.get_attribute("src", timeout=2000)
                                if src and "http" in src:
                                    # 高解像度URLに変換（._SX300_ などを除去）
                                    src_hi = re.sub(r"\._[A-Z]{2}[^.]*\.", ".", src)
                                    if src_hi not in image_urls:
                                        image_urls.append(src_hi)
                                    break
                            except Exception:
                                continue
                    except Exception:
                        continue
        except Exception as e:
            print(f"  (サムネイルクリックエラー: {e})")

        # 方法3: ページ内の全img要素から大きな画像を探す
        if len(image_urls) < 2:
            try:
                all_imgs = await page.evaluate("""
                    () => {
                        const imgs = Array.from(document.querySelectorAll('img'));
                        return imgs
                            .map(img => img.src)
                            .filter(src => src && src.includes('amazon') &&
                                   (src.includes('images/I/') || src.includes('images/P/')) &&
                                   !src.includes('sprite') && !src.includes('pixel'));
                    }
                """)
                for src in all_imgs:
                    src_hi = re.sub(r"\._[A-Z]{2}[^.]*\.", ".", src)
                    if src_hi not in image_urls:
                        image_urls.append(src_hi)
            except Exception:
                pass

        # 方法4: メイン画像だけでも取得
        if not image_urls:
            try:
                for sel in ["#landingImage", "#imgTagWrapperId img", "#main-image-container img"]:
                    src = await page.locator(sel).first.get_attribute("src", timeout=3000)
                    if src and src not in image_urls:
                        image_urls.append(src)
                        break
            except Exception:
                pass

        # 重複除去
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        print(f"  → {len(unique_urls)} 枚の画像URLを取得")
        return unique_urls

    # ------------------------------------------------------------------
    # 画像ダウンロード
    # ------------------------------------------------------------------

    async def _download_images(self, urls: list[str], images_dir: Path) -> list[Path]:
        saved: list[Path] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.amazon.co.jp/",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            for i, url in enumerate(urls):
                try:
                    resp = await client.get(url, timeout=15)
                    if resp.status_code == 200:
                        ct = resp.headers.get("content-type", "")
                        ext = "jpg" if "jpeg" in ct or url.lower().endswith(".jpg") else "png"
                        path = images_dir / f"image_{i + 1:02d}.{ext}"
                        path.write_bytes(resp.content)
                        saved.append(path)
                        size_kb = len(resp.content) // 1024
                        print(f"  ✓ 画像{i + 1}: {path.name} ({size_kb}KB)")
                    else:
                        print(f"  ✗ 画像{i + 1}: HTTPエラー {resp.status_code}")
                except Exception as e:
                    print(f"  ✗ 画像{i + 1}: {e}")
        return saved
