# ====================================
# 🔧 ライブラリと初期設定の読み込み
# ====================================
import os
import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
model = os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")

print("✅ APIキー:", openai.api_key[:8] + "..." if openai.api_key else "None")
print("✅ API BASE:", openai.api_base)
print("✅ 使用モデル:", model)

# ======================
# 📦 リクエストモデル定義
# ======================
class AnalysisRequest(BaseModel):
    prompt: str

class ImageRequest(BaseModel):
    analysis_summary: str
    
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

# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
