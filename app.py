# ====================================
# 🔧 ライブラリと初期設定の読み込み
# ====================================
import os
import urllib.parse
import openai
from openai import AzureOpenAI
from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter  # ← 追加　　Githubに追加！　HTTPException, Depends, APIRouter
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

# Line26～121 追加✅ Githubに追加！
from typing import Dict  # ← 追加  Githubに追加！
import bcrypt  # ← 追加  Githubに追加！ # パスワードハッシュ化のため追加
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime  # ← DateTime を追加
from sqlalchemy.ext.declarative import declarative_base # ← 追加  Githubに追加！
from sqlalchemy.orm import sessionmaker, relationship, Session  # ← Session を追加
import json # ← 追加  Githubに追加！
from passlib.context import CryptContext # ← 追加  Githubに追加！ # パスワードハッシュ化のため追加
from dotenv import load_dotenv # ← 追加  Githubに追加！
load_dotenv() # ← 追加  Githubに追加！

# =======================
# Azure 環境変数から取得
# =======================
MYSQL_DB_HOST = os.getenv("MYSQL_DB_HOST")
MYSQL_DB_USER = os.getenv("MYSQL_DB_USER")
MYSQL_DB_PASSWORD = urllib.parse.quote_plus(os.getenv("MYSQL_DB_PASSWORD"))  # URLエンコード
MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME")
MYSQL_DB_PORT = os.getenv("MYSQL_DB_PORT", "3306")
PORT = int(os.getenv("PORT", 8080))  # デフォルト 8080

print("✅ .env 読み込みチェック:")
print("MYSQL_DB_HOST:", MYSQL_DB_HOST)
print("MYSQL_DB_USER:", MYSQL_DB_USER)
print("MYSQL_DB_PASSWORD:", MYSQL_DB_PASSWORD)
print("MYSQL_DB_NAME:", MYSQL_DB_NAME)
print("MYSQL_DB_PORT:", MYSQL_DB_PORT)

# SSL 証明書のパス
SSL_CERT_PATH = os.path.join(os.path.dirname(__file__), "DigiCertGlobalRootCA.crt.pem")

# MySQL接続情報（SSL 証明書を適用）
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_DB_USER}:{MYSQL_DB_PASSWORD}@{MYSQL_DB_HOST}:{MYSQL_DB_PORT}/{MYSQL_DB_NAME}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"ssl": {"ssl_ca": SSL_CERT_PATH}}  # 👈 SSL 証明書を適用
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =============================
# テーブルモデル定義
# =============================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password = Column(String(100))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(255))

class Questionnaire(Base):
    __tablename__ = "questionnaires"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Answer(Base):  #✅追加 再々更新！
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaires.id"))
    question_key = Column(String(50))  # 例: "0-1"
    answer_value = Column(String(255))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class DiagnosisAnswer(Base): #✅追加
    __tablename__ = "diagnosis_answers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    question_key = Column(String(20))
    answer = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

# =============================
# DB初期化
# =============================
Base.metadata.create_all(bind=engine)
# Line26～121 追加✅ Githubに追加！

# ================================
# 🚀 FastAPI アプリケーション作成
# ================================
app = FastAPI()

# Line128～132 追加✅ Githubに追加！
origins = [
    "https://tech0-gen-8-step4-richconnections-front-cmg3bsdnbwegepgk.germanywestcentral-01.azurewebsites.net",  # Next.js デフォルトポート
]
# Line128～132 追加✅ Githubに追加！

# ==================================
# 🌐 CORS（クロスオリジン）設定
# ==================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 追加✅ Githubに追加！
    allow_methods=["*"],
    allow_headers=["*"]
)

# Line145～155 追加✅ Githubに追加！
# =============================
# DBセッションを取得する依存関数   
# =============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# Line145～155 追加✅ Githubに追加！

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

# Line208～238 追加✅ Githubに追加！
class UserIn(BaseModel):
    name: str
    email: str
    password: str

class AnswerIn(BaseModel):
    question_id: int
    answer_text: str

class AnswerInput(BaseModel):
    user_id: int
    store_id: int
    answers: Dict[str, str]  # 例: { "0-1": "Yes", ... }

class QuestionnaireIn(BaseModel):
    user_id: int
    store_id: int
    answers: List[AnswerIn]

class SubmitRequest(BaseModel): #✅追加
    answers: Dict # key: "0-0", value: "Yes"など ✅追加

class DiagnosisRequest(BaseModel):  #✅追加
    user_id: int
    store_id: int
    answers: Dict[str, str]

class Answers(BaseModel):
    answers: list[str]
# Line208～238 追加✅ Githubに追加！

# ============================
# 🧪 動作確認用エンドポイント
# ============================
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})

# Line248～337 追加✅ Githubに追加！
# =============================
# ユーザー登録エンドポイント （ハッシュ照合対応）
# =============================
# 🔁 register_user を修正
# パスワードハッシュ用の設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.post("/register")
def register_user(user: UserIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="すでに登録されたメールアドレスです")
    
    # パスワードをハッシュ化
    hashed_password = pwd_context.hash(user.password)

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_password,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"user_id": new_user.id}

# =============================
# ログイン　エンドポイント（ハッシュ照合対応）
# =============================
@app.post("/api/login")
def login_user(credentials: dict, db: Session = Depends(get_db)):
    email = credentials.get("email")
    password = credentials.get("password")

    # 📌 ユーザー検索
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが間違っています")

    # 🧠 パスワードハッシュを照合
    if not pwd_context.verify(password, user.password):
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが間違っています")

    return {
        "user_id": user.id,
        "email": user.email,
        "token": "sample-token"  # ✅ 将来的にJWTなどに置き換える
    }

# =============================
# アンケート送信エンドポイント
# =============================
@app.post("/submit")
async def submit_answers(payload: SubmitRequest):
    print(payload.answers)
    # DB 接続＆カーソル取得
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 3306))
    )
    cursor = db.cursor()

    # 回答リストを1件ずつ answers テーブルに INSERT
    for key, ans in payload.answers.items():
        try:
            questionnaire_id_str, question_id_str = key.split("-")
            questionnaire_id = int(questionnaire_id_str)
            question_id = int(question_id_str)
        except ValueError:
            # キーの形式が不正な場合スキップ
            continue

    # 回答リストを1件ずつ answers テーブルに INSERT
        cursor.execute(
            "INSERT INTO answers (questionnaire_id, question_id, answer_text) VALUES (%s, %s, %s)",
            (None, None, ans)  # 仮で questionnaire_id / question_id を None にしている場合
        )

    db.commit()
    cursor.close()
    db.close()

    return {"status": "保存成功"}
# Line247～337 追加✅ Githubに追加！
        
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
                {"role": "system", "content": "あなたは百戦錬磨の優秀な地方中小企業の経営コンサルタントです。"},
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
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import AzureOpenAI
import os

app = FastAPI()

class AnalysisRequest(BaseModel):
    prompt: str

class ImageRequest(BaseModel):
    analysis_summary: str

# ============================
# 🧠 経営分析APIエンドポイント
# ============================
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
                {"role": "system", "content": "あなたは百戦錬磨の優秀な地方中小企業の経営コンサルタントです。"},
                {"role": "user", "content": req.prompt}
            ],
            temperature=1.0,
            top_p=1.0,
            max_tokens=2048  # 🔧 応答長を確保
        )
        return {"result": completion.choices[0].message.content}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {str(e)}"})

# ================================
# 🖼 SNSキャンペーン画像生成API
# ================================
@app.post("/api/generate-campaign-image")
async def generate_campaign_image(req: ImageRequest):
    try:
        dalle_client = AzureOpenAI(
            api_key=os.getenv("DALLE_API_KEY"),
            api_version=os.getenv("DALLE_API_VERSION", "2024-02-01"),
            azure_endpoint=os.getenv("DALLE_API_BASE")
        )

        response = dalle_client.images.generate(
            model=os.getenv("DALLE_DEPLOYMENT_NAME", "dall-e-3"),
            prompt=req.analysis_summary,
            size="1024x1024",
            quality="hd",  # 🎯 高精細な画像生成を要求
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

@app.get("/api/dummy-campaign-report")
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
        print("❌ エラー:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})
        
# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting FastAPI on port {PORT} with DB {MYSQL_DB_NAME}") #　追加✅　Github追加
    uvicorn.run(app, host="0.0.0.0", port=port)
