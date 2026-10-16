from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

SQLALCHEMY_DATABASE_URL = "sqlite:///./electronics_store.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'admin' или 'customer'
    full_name = Column(String, nullable=False)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    sku = Column(String, unique=True, nullable=False, index=True)
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    specs = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    warranty_months = Column(Integer, default=12)
    stock_qty = Column(Integer, default=0)
    category = relationship("Category", back_populates="products")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_date = Column(DateTime, default=datetime.now)
    customer_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)
    address = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String, default="Новый")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    order = relationship("Order", back_populates="items")

Base.metadata.create_all(bind=engine)

class LoginRequest(BaseModel):
    username: str
    password: str

class ProductCreate(BaseModel):
    category_id: int
    sku: str
    brand: str
    model: str
    specs: str
    price: float
    warranty_months: int
    stock_qty: int

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_name: str
    phone: str
    email: str
    address: str
    items: List[OrderItemCreate]

app = FastAPI(title="АИС Учёта продаж бытовой техники и электроники")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def seed_database(db: Session):
    if db.query(User).first(): return
    db.add_all([
        User(username="admin", password="123", role="admin", full_name="Соколов Павел (Продавец-Админ)"),
        User(username="client", password="123", role="customer", full_name="Иванов Алексей (Покупатель)")
    ])
    cats = [Category(name="Смартфоны"), Category(name="Ноутбуки"), Category(name="Крупная техника")]
    db.add_all(cats)
    db.commit()

    db.add_all([
        Product(category_id=1, sku="SM-S928B", brand="Samsung", model="Galaxy S24 Ultra", specs="6.8 AMOLED, 12GB", price=114990, warranty_months=12, stock_qty=8),
        Product(category_id=1, sku="APL-IP15P", brand="Apple", model="iPhone 15 Pro", specs="6.1 OLED, A17 Pro", price=104990, warranty_months=12, stock_qty=5),
        Product(category_id=2, sku="ASU-G16", brand="ASUS", model="ROG Strix G16", specs="i7, RTX 4060", price=139990, warranty_months=24, stock_qty=4),
        Product(category_id=3, sku="LG-GA-B459", brand="LG", model="DoorCooling+ GA-B459", specs="Холодильник No Frost", price=62990, warranty_months=36, stock_qty=6),
    ])
    db.commit()

@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    seed_database(db)
    db.close()

@app.post("/api/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username, User.password == data.password).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    return {"id": user.id, "username": user.username, "role": user.role, "full_name": user.full_name}

@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name} for c in db.query(Category).all()]

@app.get("/api/products")
def get_products(db: Session = Depends(get_db)):
    return [{
        "id": p.id, "category_id": p.category_id, "category_name": p.category.name if p.category else "",
        "sku": p.sku, "brand": p.brand, "model": p.model, "specs": p.specs,
        "price": p.price, "warranty_months": p.warranty_months, "stock_qty": p.stock_qty
    } for p in db.query(Product).all()]

@app.post("/api/products")
def create_product(prod: ProductCreate, db: Session = Depends(get_db)):
    if db.query(Product).filter(Product.sku == prod.sku).first():
        raise HTTPException(status_code=400, detail="Товар с таким SKU уже существует")
    new_prod = Product(**prod.dict())
    db.add(new_prod)
    db.commit()
    return {"message": "Товар успешно добавлен"}

@app.patch("/api/products/{product_id}/stock")
def update_stock(product_id: int, add_qty: int, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod: raise HTTPException(status_code=404)
    prod.stock_qty += add_qty
    db.commit()
    return {"message": "Ок"}

@app.get("/api/orders")
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.order_date.desc()).all()
    return [{
        "id": o.id,
        "order_date": o.order_date.strftime("%d.%m.%Y %H:%M"),
        "customer_name": o.customer_name,
        "phone": o.phone,
        "email": o.email,
        "address": o.address,
        "total_amount": o.total_amount,
        "status": o.status,
        "items": [{"product_name": i.product_name, "quantity": i.quantity, "price": i.price} for i in o.items]
    } for o in orders]

@app.post("/api/orders")
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    if not order_data.items: raise HTTPException(status_code=400, detail="Корзина пуста")
    total = 0.0
    items_objs = []
    for item in order_data.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        if not prod or prod.stock_qty < item.quantity:
            raise HTTPException(status_code=400, detail="Товар закончился на складе")
        prod.stock_qty -= item.quantity
        total += prod.price * item.quantity
        items_objs.append(OrderItem(product_name=f"{prod.brand} {prod.model}", quantity=item.quantity, price=prod.price))

    new_order = Order(
        customer_name=order_data.customer_name, phone=order_data.phone,
        email=order_data.email, address=order_data.address, total_amount=total, items=items_objs
    )
    db.add(new_order)
    db.commit()
    return {"message": "Заказ успешно оформлен!", "order_id": new_order.id}

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return "index.html"