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
    """Gemini APIを使ってメルカリ出品文を生成（REST API直接呼び出し）"""
    import re
    import requests

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("GEMINI_API_KEY が設定されていません")
        return {"mercari_title": "", "mercari_description": "", "suggested_price": 0}

    title = product_info.get("title", "")
    price = product_info.get("price", "")
    features = product_info.get("features", [])
    description = product_info.get("description", "")
    brand = product_info.get("brand", "")
    features_text = "\n".join(f"- {f}" for f in features[:8]) if features else "情報なし"

    prompt = f"""あなたはメルカリ出品の専門アシスタントです。
以下のルールを厳守して商品説明文を作成してください。

【入力情報】
商品名: {title}
ブランド: {brand}
Amazon価格: {price}
商品特徴:
{features_text}
商品説明: {description[:800] if description else "なし"}

【基本構成】
①冒頭キャッチフレーズ（1〜2行）
　「【キャッチコピー】」という見出しは絶対に書かない。
　商品の魅力を端的に表した、心に刺さるフレーズをそのまま書く。
　カテゴリに応じた方向性で作成する。
　・サプリ・健康食品系：成分・効果を前面に出した信頼感重視
　・香水・コスメ系：使うシーンや感情に訴える情景描写重視
　・日用品・実用品系：手軽さ・安全性・解決感重視
②ご覧いただきありがとうございます。
③本文（なるべく詳しく、400〜800文字目安）
　・悩みへの共感または情景描写から入る
　・商品名＋どんな人向けかを紹介
　・主要成分・特徴・使用方法・使用シーンを詳しく説明
　・他商品との違い・選ばれる理由・安心感を具体的に伝える
　・使った後にどんな変化や気持ちが得られるかをイメージさせる
④【商品情報】
　状態・商品名・内容量または個数・ブランド・その他を記載
⑤【発送について】
　ご購入後24時間以内に発送いたします。
⑥ハッシュタグ20個

【執筆ルール】
・タイトルは40文字以内で作成する（冒頭に「セール中！」をつける）
・冒頭キャッチフレーズは必ず入れる（「【キャッチコピー】」とは書かない）
・購入時期は記載しない
・絵文字は使用しない
・注意書き・匿名配送・箱出し発送の文言は入れない
・ハッシュタグは検索されやすいキーワードを20個入れる
・過剰な効果訴求はしない（景品表示法・健康増進法に注意）
・「たった1粒で」などの誇大表現は使わない
・「〇〇不使用」など安全性を示す言葉は積極的に使う
・短い文を重ねてリズムよく読めるよう意識する
・読んでいるうちに欲しくなる「共感→紹介→信頼」の流れを作る
・説明の羅列にならず、買う人の気持ちに刺さる文章にする

【価格設定】
・Amazon価格の約60%を販売価格とする（例：Amazon価格3000円なら1800円）
・Amazon価格が不明な場合はメルカリ相場の80%程度を目安にする

以下のJSON形式のみで返答してください（マークダウン不要）:
{{"mercari_title": "タイトル（40文字以内）", "mercari_description": "説明文", "suggested_price": 推奨価格の数字}}"""

    url_api = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url_api, json=payload, timeout=60)
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
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

    listing = {}
    if product_info:
        try:
            listing = generate_mercari_listing(product_info)
            listing_file = latest / "mercari_listing.json"
            with open(listing_file, "w", encoding="utf-8") as f:
                json.dump(listing, f, ensure_ascii=False, indent=2)
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


@app.route("/test_gemini")
def test_gemini():
    try:
        import requests
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY が設定されていません"})
        url_api = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "こんにちは"}]}]}
        resp = requests.post(url_api, json=payload, timeout=30)
        if resp.status_code != 200:
            return jsonify({"error": f"{resp.status_code}: {resp.text[:300]}"})
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"ok": True, "response": text[:100]})
    except Exception as e:
        return jsonify({"error": str(e)})


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


@app.route("/api/latest_product")
def latest_product():
    """最新の商品データをJSONで返す（Tampermonkey用）"""
    folders = sorted(OUTPUT_DIR.glob("product_*"))
    if not folders:
        return jsonify({"error": "商品データがありません"}), 404
    latest = folders[-1]
    info_file = latest / "product_info.json"
    product_info = {}
    if info_file.exists():
        with open(info_file, "r", encoding="utf-8") as f:
            product_info = json.load(f)
    listing_file = latest / "mercari_listing.json"
    listing = {}
    if listing_file.exists():
        with open(listing_file, "r", encoding="utf-8") as f:
            listing = json.load(f)
    images_dir = latest / "images"
    image_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    image_urls = [f"https://amazon-image-tool.onrender.com/images/{latest.name}/{img.name}" for img in image_files]
    response = jsonify({
        "title": listing.get("mercari_title", product_info.get("title", "")),
        "description": listing.get("mercari_description", ""),
        "price": listing.get("suggested_price", 0),
        "images": image_urls,
        "folder": latest.name,
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
