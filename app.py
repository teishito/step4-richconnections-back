import os
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# =======================
# Azure 環境変数から取得
# =======================
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = urllib.parse.quote_plus(os.getenv("DB_PASSWORD"))  # URLエンコード
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "3306")
PORT = int(os.getenv("PORT", 8080))  # デフォルト 8080

# SSL 証明書のパス
SSL_CERT_PATH = os.path.join(os.path.dirname(__file__), "DigiCertGlobalRootCA.crt.pem")

# MySQL接続情報（SSL 証明書を適用）
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"ssl": {"ssl_ca": SSL_CERT_PATH}}  # 👈 SSL 証明書を適用
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =======================
# モデル定義
# =======================
class Product(Base):
    __tablename__ = 'products'
    PRD_ID = Column(Integer, primary_key=True, index=True)
    CODE = Column(String(13), unique=True, index=True)
    NAME = Column(String(50))
    PRICE = Column(Integer)

class Transaction(Base):
    __tablename__ = 'transactions'
    TRANSACTION_ID = Column(Integer, primary_key=True, index=True)
    TOTAL_PRICE = Column(Integer)

class TransactionDetail(Base):
    __tablename__ = 'transaction_details'
    DETAIL_ID = Column(Integer, primary_key=True, index=True)
    TRANSACTION_ID = Column(Integer, ForeignKey("transactions.TRANSACTION_ID"))
    PRODUCT_CODE = Column(String(13))
    PRICE = Column(Integer)

# =======================
# FastAPI 初期化 & CORS 設定
# =======================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://tech0-gen8-step4-pos-app-71.azurewebsites.net"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =======================
# ルートエンドポイント
# =======================
@app.get("/")
async def home():
    return {"message": "Welcome to the FastAPI API!"}

# =======================
# 商品取得 API
# =======================
class ProductResponse(BaseModel):
    PRD_ID: int
    CODE: str
    NAME: str
    PRICE: int

@app.get("/api/products/{code}", response_model=ProductResponse)
async def get_product(code: str):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.CODE == code).first()
        if product:
            return {
                "PRD_ID": product.PRD_ID,
                "CODE": product.CODE,
                "NAME": product.NAME,
                "PRICE": product.PRICE
            }
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# =======================
# 購入処理 API
# =======================
class PurchaseRequest(BaseModel):
    cart: list

@app.post("/api/purchase")
async def purchase(request: PurchaseRequest):
    db = SessionLocal()
    try:
        total = sum(item["price"] for item in request.cart)
        tax = int(total * 0.1)
        total_with_tax = total + tax

        # `transactions` テーブルに保存
        transaction = Transaction(TOTAL_PRICE=total_with_tax)
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        # `transaction_details` に保存
        for item in request.cart:
            detail = TransactionDetail(
                TRANSACTION_ID=transaction.TRANSACTION_ID,
                PRODUCT_CODE=item["code"],
                PRICE=item["price"]
            )
            db.add(detail)

        db.commit()

        return {"message": "購入完了", "totalWithTax": total_with_tax}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# =======================
# アプリ起動
# =======================
if __name__ == "__main__":
    import uvicorn
    print(f"Starting FastAPI on port {PORT} with DB {DB_NAME}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
