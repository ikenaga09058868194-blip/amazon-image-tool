"""
メルカリ/Yahoo!フリマ用 商品説明文ジェネレーター
Claude APIを使用してAmazon商品情報から販売用テキストを生成します
"""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import anthropic


@dataclass
class MercariListing:
    title: str
    description: str
    category: str
    price: int
    condition: str
    # 以下はYahoo!フリマ用
    yahoo_title: Optional[str] = None
    yahoo_description: Optional[str] = None
    yahoo_category: Optional[str] = None


# メルカリのカテゴリマッピング（主要なもの）
MERCARI_CATEGORIES = """
- スマートフォン/携帯電話 > iPhone
- スマートフォン/携帯電話 > Android
- PC/タブレット > タブレット
- PC/タブレット > ノートPC
- 家電/カメラ > デジタルカメラ
- 家電/カメラ > スマートウォッチ
- 家電/カメラ > オーディオ機器
- おもちゃ/ホビー/ゲーム > ゲーム機
- ファッション > バッグ
- ファッション > 腕時計
- キッチン/日用品/その他 > 生活家電
- その他
"""

# メルカリの商品状態（選択肢）
CONDITIONS = [
    "新品、未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い",
]


class DescriptionGenerator:
    """Claude APIを使ってメルカリ/Yahoo!フリマ用商品説明を生成"""

    def __init__(self):
        self.client = anthropic.Anthropic()

    def generate(self, product, condition: str = "新品、未使用") -> MercariListing:
        """
        商品データを受け取り、メルカリ/Yahoo!フリマ用のリスティングを生成

        Args:
            product: ProductData (scraper.pyで取得したデータ)
            condition: 商品の状態
        """
        print("🤖 Claude APIで商品説明を生成中...")

        # 画像をbase64エンコード（最大3枚まで）
        image_content = []
        for img_path in product.images[:3]:
            if img_path.exists():
                try:
                    data = base64.standard_b64encode(img_path.read_bytes()).decode()
                    media_type = (
                        "image/jpeg"
                        if img_path.suffix.lower() in (".jpg", ".jpeg")
                        else "image/png"
                    )
                    image_content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data,
                            },
                        }
                    )
                except Exception as e:
                    print(f"  (画像読み込みエラー: {e})")

        # 商品情報テキスト構築
        features_text = "\n".join(f"・{f}" for f in product.features[:10])
        brand_text = f"ブランド: {product.brand}" if product.brand else ""
        price_info = ""
        if product.price:
            price_info = f"Amazon販売価格: {product.price}"
            if product.original_price:
                price_info += f"（定価: {product.original_price}）"

        prompt = f"""以下のAmazon商品情報を元に、日本のメルカリとYahoo!フリマで売れやすい商品出品データを作成してください。

【Amazon商品情報】
タイトル: {product.title}
{brand_text}
{price_info}
カテゴリ: {product.category}
商品の状態: {condition}

【商品の特徴・仕様】
{features_text or "（情報なし）"}

【商品説明】
{product.description[:800] if product.description else "（情報なし）"}

【出力フォーマット】
以下のJSON形式で出力してください。JSONのみ出力し、説明文などは不要です。

{{
  "mercari_title": "メルカリ用タイトル（40文字以内。商品名+ブランド+型番などの重要キーワードを含む）",
  "mercari_description": "メルカリ用商品説明（2000文字以内）\\n\\n以下の構成で作成:\\n■ 商品概要（2〜3行）\\n\\n■ 主な特徴\\n・特徴1\\n・特徴2\\n\\n■ 商品スペック（重要なもの）\\n・スペック1\\n\\n■ 商品の状態\\n{condition}です。（詳細を記載）\\n\\n■ 発送について\\nプチプチで丁寧に梱包してお送りします。\\n発送は〇〇日以内を予定しております。\\n\\n■ その他\\nご不明な点はお気軽にコメントください。",
  "mercari_category": "メルカリのカテゴリ（以下から最も適切なものを選択）:\\n{MERCARI_CATEGORIES}",
  "mercari_price": 推奨販売価格（整数、円単位。Amazonより15〜25%程度安くする。送料分を考慮）,
  "mercari_condition": "{condition}",
  "yahoo_title": "Yahoo!フリマ用タイトル（30文字以内。簡潔に）",
  "yahoo_description": "Yahoo!フリマ用商品説明（1000文字以内。メルカリ用より簡潔に）",
  "yahoo_category": "Yahoo!フリマのカテゴリ名"
}}"""

        messages_content = image_content + [{"type": "text", "text": prompt}]

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": messages_content}],
        )

        # レスポンスのJSONを解析
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        # JSON抽出
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError(f"JSONが見つかりませんでした。レスポンス: {text[:200]}")

        data = json.loads(json_match.group())

        # メルカリ価格のデフォルト値
        price = data.get("mercari_price", 0)
        if isinstance(price, str):
            price = int(re.sub(r"\D", "", price) or "0")

        return MercariListing(
            title=data.get("mercari_title", product.title[:40]),
            description=data.get("mercari_description", ""),
            category=data.get("mercari_category", "その他"),
            price=price,
            condition=data.get("mercari_condition", condition),
            yahoo_title=data.get("yahoo_title"),
            yahoo_description=data.get("yahoo_description"),
            yahoo_category=data.get("yahoo_category"),
        )

    def save_listing(self, listing: MercariListing, output_dir: Path) -> Path:
        """生成した出品データをテキストファイルに保存"""
        text = f"""=== メルカリ出品データ ===

【タイトル】（40文字以内）
{listing.title}

【カテゴリ】
{listing.category}

【商品の状態】
{listing.condition}

【販売価格】
¥{listing.price:,}

【商品説明】
{listing.description}

{'=' * 50}
=== Yahoo!フリマ出品データ ===

【タイトル】（30文字以内）
{listing.yahoo_title or listing.title[:30]}

【カテゴリ】
{listing.yahoo_category or listing.category}

【商品説明】
{listing.yahoo_description or listing.description[:1000]}
"""
        out_path = output_dir / "listing.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"  ✓ 出品データを保存: {out_path}")
        return out_path

    def save_listing_json(self, listing: MercariListing, output_dir: Path) -> Path:
        """JSON形式でも保存（自動出品スクリプト用）"""
        data = {
            "mercari": {
                "title": listing.title,
                "description": listing.description,
                "category": listing.category,
                "price": listing.price,
                "condition": listing.condition,
            },
            "yahoo": {
                "title": listing.yahoo_title or listing.title[:30],
                "description": listing.yahoo_description or listing.description[:1000],
                "category": listing.yahoo_category or listing.category,
                "price": listing.price,
            },
        }
        out_path = output_dir / "listing.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ JSONデータを保存: {out_path}")
        return out_path
