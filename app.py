# ====================================
# 🔧 ライブラリと初期設定の読み込み
# ====================================
import os
import urllib.parse
import openai
from openai import AzureOpenAI
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import instaloader
import re
from collections import defaultdict
from instaloader import Instaloader, Profile
from typing import List
import csv
import tempfile
from azure.storage.blob import BlobServiceClient
import requests
from urllib.parse import urlparse
import uuid
import mysql.connector
from datetime import datetime

# ================================
# 🚀 FastAPI アプリケーション作成
# ================================
app = FastAPI()

# ==================================
# 🌐 CORS（クロスオリジン）設定
# ==================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # セキュリティ上は必要に応じて制限
    allow_methods=["*"],
    allow_headers=["*"]
)

# =======================
# 🔐 Azure 環境変数から取得
# =======================
# OpenAI API 関連
openai.api_type = "azure"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_base = os.getenv("OPENAI_API_BASE")
openai.api_version = os.getenv("OPENAI_API_VERSION")
model = os.getenv("OPENAI_MODEL")

# Azure Blob Storage 接続
azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not azure_connection_string:
    raise ValueError("❌ AZURE_STORAGE_CONNECTION_STRING が設定されていません")
blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
container_name = "instagram-posts"

# MySQL 接続情報
MYSQL_DB_CONFIG = {
    "host": os.getenv("MYSQL_DB_HOST"),
    "port": int(os.getenv("MYSQL_DB_PORT", 3306)),
    "user": os.getenv("MYSQL_DB_USER"),
    "password": urllib.parse.quote_plus(os.getenv("MYSQL_DB_PASSWORD")),
    "database": os.getenv("MYSQL_DB_NAME"),
    "ssl_ca": os.path.join(os.path.dirname(__file__), "DigiCertGlobalRootCA.crt.pem"),
    "ssl_verify_cert": True
}

# ログ出力
print("✅ OPENAI_BASE:", openai.api_base)
print("✅ MODEL:", model)
print("✅ API_VERSION:", openai.api_version)
print("✅ AZURE_STORAGE:", blob_service_client.account_name)
print("✅ MySQL HOST:", MYSQL_DB_CONFIG["host"])

# ======================
# 📦 リクエストモデル定義
# ======================
class AnalysisRequest(BaseModel):
    prompt: str

class ImageRequest(BaseModel):
    analysis_summary: str

class PostURL(BaseModel):
    url: str

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

# ============================
# 🧪 動作確認用エンドポイント
# ============================
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})

# ============================
# 🚪 会員登録API (MySQL保存)
# ============================
@app.post("/api/register")
async def register_user(user: SignupRequest):
    try:
        print("🔍 受け取ったデータ:", user.dict())

        conn = mysql.connector.connect(**MYSQL_DB_CONFIG)
        cursor = conn.cursor()

        insert_sql = """
            INSERT INTO users (name, email, password, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        now = datetime.utcnow()
        cursor.execute(insert_sql, (user.name, user.email, user.password, now, now))
        conn.commit()

        print("✅ 登録完了:", user.email)
        cursor.close()
        conn.close()

        return {"message": "User registered successfully"}

    except Exception as e:
        print("❌ MySQL Insert Error:", e)
        return JSONResponse(status_code=500, content={"message": str(e)})
        
# ============================
# 🧠 経営分析APIエンドポイント
# ============================
from openai import AzureOpenAI

@app.post("/api/analyze")
async def analyze(req: AnalysisRequest):
    try:
        client = AzureOpenAI(
            api_version=os.getenv("OPENAI_API_VERSION", "2025-01-01-preview"),
            azure_endpoint=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY")
        )

        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-3"),
            messages=[
                {"role": "system", "content": "あなたは地方中小企業の経営コンサルタントです。"},
                {"role": "user", "content": req.prompt}
            ],
            temperature=1.0,
            top_p=1.0
        )
        return {"result": completion.choices[0].message.content}

    except Exception as e:
        import traceback
        traceback.print_exc()  # ログ出力のため
        return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {str(e)}"})

# ================================
# 🖼 SNSキャンペーン画像生成API
# ================================
@app.post("/api/generate-campaign-image")
async def generate_campaign_image(req: ImageRequest):
    try:
        image_prompt = f"""
以下は地方中小企業の経営診断に基づいた要約結果です。この内容をもとに、SNSでプレゼントキャンペーンを告知するための画像を生成してください。

【目的】
「地方中小企業応援キャンペーン」のSNS投稿用プレゼント告知画像

【画像構成】
- 明るく親しみやすい雰囲気
- プレゼントキャンペーンを伝える構図（プレゼントボックス・笑顔の人々・フォローやシェアのイメージ）
- 文字例: 「今だけ！フォロー＆いいねで豪華商品をプレゼント」「#地域活性 #応援キャンペーン」
- SNSで映える正方形構図（Instagram向け）

【色・スタイル】
- 信頼感と活気を感じさせるブルー＋オレンジ
- モダンなイラストまたは手描き風

【要約】
{req.analysis_summary}
"""

        dalle_client = AzureOpenAI(
            api_key=os.getenv("DALLE_API_KEY"),
            api_version=os.getenv("DALLE_API_VERSION", "2024-02-01"),
            azure_endpoint=os.getenv("DALLE_API_BASE")
        )

        response = dalle_client.images.generate(
            model=os.getenv("DALLE_DEPLOYMENT_NAME", "dall-e-3"),
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )

        image_url = response.data[0].url
        return {"image_url": image_url}

    except Exception as e:
        print("❌ Image Generation Error:", str(e))
        return JSONResponse(status_code=500, content={"error": f"画像生成エラー: {str(e)}"})
        
# ================================
# 🖼 SNS投稿データ
# ================================
from azure.storage.blob import BlobServiceClient, ContentSettings
import requests
import uuid

@app.post("/api/fetch-instagram-post")
async def fetch_instagram_post(post: PostURL):
    try:
        # Instagram URL から shortcode を抽出
        shortcode_match = re.search(r"/p/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})

        shortcode = shortcode_match.group(1)

        # Instaloaderで投稿情報取得
        loader = instaloader.Instaloader()
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # 画像URL取得
        image_url = post_data.url

        # 画像を取得（バイナリ）
        img_data = requests.get(image_url).content
        filename = f"{shortcode}_{uuid.uuid4().hex}.jpg"

        # Azure Storage へアップロード
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        blob_client.upload_blob(
            img_data,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type="image/jpeg")
        )

        # Azure上の公開URL
        uploaded_image_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{filename}"

        # 投稿情報とアップロードした画像URLを返す
        result = {
            "image_url": uploaded_image_url,
            "caption": post_data.caption,
            "likes": post_data.likes,
            "comments": post_data.comments,
        }
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
        
# ================================
# 📊 レポート生成API
# ================================

@app.post("/api/dummy-campaign-report")
async def dummy_campaign_report():
    return JSONResponse(content={
        "likes": {
            "ranking": [
                {"user": "tomari_w", "value": 1867},
                {"user": "jihy2010", "value": 1750},
                {"user": "aozora", "value": 1719},
                {"user": "sakemaimai", "value": 1252},
                {"user": "chami_444", "value": 887},
                {"user": "jur_1027", "value": 599},
                {"user": "aopime", "value": 271},
                {"user": "aiko_body", "value": 77},
                {"user": "kayonomura_", "value": 33},
                {"user": "hatsune_yd", "value": 0},
            ],
            "total": 8455,
            "average": 939,
        },
        "comments": {
            "ranking": [
                {"user": "aozora", "value": 498},
                {"user": "kayonomura_", "value": 418},
                {"user": "aiko_body", "value": 343},
                {"user": "chami_444", "value": 316},
                {"user": "tomari_w", "value": 291},
                {"user": "aopime", "value": 212},
                {"user": "jihy2010", "value": 147},
                {"user": "jur_1027", "value": 75},
                {"user": "sakemaimai", "value": 22},
                {"user": "hatsune_yd", "value": 0},
            ],
            "total": 2322,
            "average": 258,
        },
        "engagement": {
            "ranking": [
                {"user": "tomari_w", "value": 44.44},
                {"user": "aozora", "value": 25.0},
                {"user": "kayonomura_", "value": 19.8},
                {"user": "jihy2010", "value": 6.02},
                {"user": "jur_1027", "value": 3.36},
                {"user": "aiko_body", "value": 2.87},
                {"user": "chami_444", "value": 2.72},
                {"user": "sakemaimai", "value": 2.65},
                {"user": "aopime", "value": 2.21},
                {"user": "hatsune_yd", "value": 0},
            ],
            "total": 121.12,
            "average": 12.12,
        }
    })
    
# ================================
# 📊 フォロワーリスト取得API
# ================================
@app.post("/api/export-followers")
async def export_followers(username: str):
    try:
        loader = Instaloader()
        ig_username = os.getenv("INSTAGRAM_USERNAME")
        ig_password = os.getenv("INSTAGRAM_PASSWORD")

        if not ig_username or not ig_password:
            raise ValueError("INSTAGRAM_USERNAME または INSTAGRAM_PASSWORD が未設定です")

        loader.login(ig_username, ig_password)
        profile = Profile.from_username(loader.context, username)
        followers = profile.get_followers()

        results = []
        for i, follower in enumerate(followers):
            if i >= 30:
                break
            results.append({
                "username": follower.username,
                "full_name": follower.full_name,
                "bio": follower.biography,
                "followers": follower.followers,
                "followees": follower.followees,
                "is_private": follower.is_private,
                "is_verified": follower.is_verified,
            })

        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".csv") as temp_file:
            writer = csv.DictWriter(temp_file, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            csv_path = temp_file.name

        return FileResponse(csv_path, media_type="text/csv", filename=f"{username}_followers.csv")

    except Exception as e:
        print("❌ エラー:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})
        
# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
