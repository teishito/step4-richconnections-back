# ====================================
# 🔧 ライブラリと初期設定の読み込み
# ====================================
import os
import openai
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
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
openai.api_type = "azure"  # ← 必須
model = os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")

# Azure Storage設定
azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not azure_connection_string:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING が設定されていません")

blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
container_name = "instagram-posts"  # ストレージコンテナ名（固定であればここに記述）

# ログ出力（本番ではコメントアウトしてもOK）
print("✅ OpenAI APIキー:", openai.api_key[:8] + "..." if openai.api_key else "None")
print("✅ OpenAI BASE:", openai.api_base)
print("✅ 使用モデル:", model)
print("✅ Azure Blob 接続済み")

# ======================
# 📦 リクエストモデル定義
# ======================
class AnalysisRequest(BaseModel):
    prompt: str

class ImageRequest(BaseModel):
    analysis_summary: str

class PostURL(BaseModel):
    url: str
    
# ============================
# 🧪 動作確認用エンドポイント
# ============================
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})

# ============================
# 🧠 経営分析APIエンドポイント
# ============================
@app.post("/api/analyze")
async def analyze(req: AnalysisRequest):
    try:
        completion = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたは地方中小企業の経営コンサルタントです。"},
                {"role": "user", "content": req.prompt}
            ]
        )
        return {"result": completion.choices[0].message.content}
    except Exception as e:
        print("❌ Server Error:", str(e))
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
        response = openai.images.generate(
            model="dall-e-3",
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
# 📊 エンゲージメントレポート生成API
# ================================
@app.post("/api/engagement-report")
async def engagement_report(post: PostURL):
    try:
        shortcode_match = re.search(r"/p/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})

        shortcode = shortcode_match.group(1)
        loader = instaloader.Instaloader()

        # 投稿を取得
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # 直近50人のいいねユーザーを取得
        likers = []
        for index, liker in enumerate(post_data.get_likes()):
            if index >= 50:
                break
            likers.append({
                "username": liker.username,
                "followers": liker.followers,
                "followees": liker.followees,
                "engagement": 0  # 後ほど計算
            })

        # 投稿のいいね数・コメント数から全体エンゲージメントを取得
        total_likes = post_data.likes
        total_comments = post_data.comments
        total_engagement = total_likes + total_comments

        for liker in likers:
            try:
                # 仮にエンゲージメント率をフォロワー数で割って求める
                if liker["followers"] > 0:
                    liker["engagement"] = round((1 + 1) / liker["followers"] * 100, 2)  # 1 like + 1 comment (仮)
                else:
                    liker["engagement"] = 0
            except Exception as e:
                liker["engagement"] = 0

        # ランキング用に並べ替え
        likes_ranking = sorted(likers, key=lambda x: x["username"])
        comment_ranking = sorted(likers, key=lambda x: x["username"])
        engagement_ranking = sorted(likers, key=lambda x: x["engagement"], reverse=True)

        return {
            "likers": likers,
            "likes_ranking": likes_ranking[:10],
            "comment_ranking": comment_ranking[:10],
            "engagement_ranking": engagement_ranking[:10],
            "average_engagement": round(sum([l["engagement"] for l in likers]) / len(likers), 2) if likers else 0
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ================================
# 📊 フォロワーリスト取得API
# ================================
@app.post("/api/export-followers")
async def export_followers(username: str):
    try:
        loader = Instaloader()
        profile = Profile.from_username(loader.context, username)
        followers = profile.get_followers()

        results = []
        for follower in followers:
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
        return JSONResponse(status_code=500, content={"error": str(e)})

# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
