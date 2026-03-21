from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess
import os
import glob
import json
from pathlib import Path

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"


@app.route("/")
def index():
    return render_template("index.html")


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

    return {
        "success": True,
        "images": images,
        "title": product_info.get("title", ""),
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
