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

class CampaignImageRequest(BaseModel):
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

# ====================================
# 🖼️ SNSキャンペーン画像生成APIエンドポイント
# ====================================
@app.post("/api/generate-campaign-image")
async def generate_campaign_image(req: CampaignImageRequest):
    try:
        prompt = f"Generate a promotional campaign image based on the following Japanese business analysis:\n{req.analysis_summary}\nDesign it to be visually appealing for social media, include relevant symbols, and use modern Japanese design aesthetics."

        image_response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = image_response.data[0].url
        return {"imageUrl": image_url}
    except Exception as e:
        print("❌ Server Error (generate-campaign-image):", str(e))
        return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {str(e)}"})

# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
