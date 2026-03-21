from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
import subprocess
import os
import glob
import json
import zipfile
import io
from pathlib import Path

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"


@app.route("/")
def index():
    return render_template("index.html")


def generate_mercari_listing(product_info: dict) -> dict:
    """Gemini APIを使ってメルカリ出品文を生成（無料枠あり）"""
    import google.generativeai as genai
    import re
    import os

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"mercari_title": "", "mercari_description": "", "suggested_price": 0}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    title = product_info.get("title", "")
    price = product_info.get("price", "")
    features = product_info.get("features", [])
    description = product_info.get("description", "")
    brand = product_info.get("brand", "")
    features_text = "\n".join(f"- {f}" for f in features[:8]) if features else "情報なし"

    prompt = f"""あなたはメルカリ出品の専門アシスタントです。以下の商品情報からメルカリ出品用のタイトルと説明文を作成してください。

【商品情報】
商品名: {title}
ブランド: {brand}
Amazon価格: {price}
商品特徴:
{features_text}
商品説明: {description[:500] if description else "なし"}

【執筆ルール】
1. タイトル：必ず冒頭に「セール中！」をつけ、その後に商品名を記載（40文字以内）
2. 購入時期：商品説明文の中に「購入時期」は記載しないこと
3. 注意書き：必ず「※新品未使用品ですが、自宅保管のためパッケージに細かなスレ等がある場合がございます。完璧を求める方や神経質な方はご遠慮ください。」を入れること
4. 発送：最後に「24時間以内に配送いたします」を記載
5. 価格提案：市場相場を考慮しておすすめの販売価格（円）を数字のみで提示

【構成テンプレート】
【キャッチコピー】商品の概要・紹介。
【商品状態】
* 状態：新品・未使用
* 内容量：...（わかる場合のみ）
※新品未使用品ですが、自宅保管のためパッケージに細かなスレ等がある場合がございます。完璧を求める方や神経質な方はご遠慮ください。
【商品の特徴】
* 特徴1：...
* 特徴2：...
【こんな方におすすめ】
* ...
【発送について】
* 24時間以内に配送いたします。
* 匿名配送にて迅速・丁寧に発送いたします。

以下のJSON形式のみで返答してください（マークダウン不要）:
{{"mercari_title": "タイトル", "mercari_description": "説明文", "suggested_price": 推奨価格の数字}}"""

    response = model.generate_content(prompt)
    text = response.text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return {"mercari_title": "", "mercari_description": "", "suggested_price": 0}


def scrape_one(url):
    """1件のURLをスクレイピングして結果を返す"""
    before = set(OUTPUT_DIR.glob("product_*"))
    result = subprocess.run(
        ["python3", "main.py", "scrape-only", url],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return {"error": result.stderr or "取得に失敗しました", "url": url}

    after = set(OUTPUT_DIR.glob("product_*"))
    new_folders = sorted(after - before)
    if not new_folders:
        new_folders = sorted(OUTPUT_DIR.glob("product_*"))
    latest = new_folders[-1]

    images_dir = latest / "images"
    image_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    images = [f"/images/{latest.name}/{img.name}" for img in image_files]

    info_file = latest / "product_info.json"
    product_info = {}
    if info_file.exists():
        with open(info_file, "r", encoding="utf-8") as f:
            product_info = json.load(f)

    # Claude APIで説明文生成
    listing = {}
    if product_info:
        try:
            listing = generate_mercari_listing(product_info)
        except Exception as e:
            print(f"説明文生成エラー: {e}")

    return {
        "success": True,
        "images": images,
        "title": product_info.get("title", ""),
        "mercari_title": listing.get("mercari_title", ""),
        "mercari_description": listing.get("mercari_description", ""),
        "suggested_price": listing.get("suggested_price", 0),
        "url": url,
    }


@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URLが入力されていません"}), 400
    try:
        return jsonify(scrape_one(url))
    except subprocess.TimeoutExpired:
        return jsonify({"error": "タイムアウトしました"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/scrape_bulk", methods=["POST"])
def scrape_bulk():
    data = request.get_json()
    urls = [u.strip() for u in data.get("urls", []) if u.strip()]
    if not urls:
        return jsonify({"error": "URLが入力されていません"}), 400

    results = []
    for url in urls:
        try:
            results.append(scrape_one(url))
        except subprocess.TimeoutExpired:
            results.append({"error": "タイムアウト", "url": url})
        except Exception as e:
            results.append({"error": str(e), "url": url})

    return jsonify({"results": results})


@app.route("/images/<folder>/<filename>")
def serve_image(folder, filename):
    image_dir = OUTPUT_DIR / folder / "images"
    return send_from_directory(str(image_dir), filename)


@app.route("/download_zip/<folder>")
def download_zip(folder):
    images_dir = OUTPUT_DIR / folder / "images"
    if not images_dir.exists():
        return jsonify({"error": "フォルダが見つかりません"}), 404

    image_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    if not image_files:
        return jsonify({"error": "画像がありません"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in image_files:
            zf.write(img, img.name)
    buf.seek(0)

    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"{folder}_images.zip")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
