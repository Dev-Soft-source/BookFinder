# main.py
import sys
import asyncio

# Must run before any code creates an event loop (Windows Selector loop cannot spawn subprocess = Playwright async breaks).
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

import os
import random
import uuid
import csv
import logging
from io import StringIO
from pathlib import Path
from typing import List, Optional, Any
import time
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError, ExpiredSignatureError

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr
from fastapi.staticfiles import StaticFiles
from backend.scraper import scrape_bookfinder, send_email_alert, shutdown_playwright, pass_captcha
#from scraper import scrape_bookfinder, send_email_alert, shutdown_playwright, pass_captcha

from sqlalchemy import (
    Column, String, Float, DateTime, Boolean, select, update, func, or_, desc, delete
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Environment ---
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./bookfinder.db")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_BUILD = BASE_DIR.parent / "frontend" / "build"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- DB / SQLAlchemy setup ---
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

csv_list = []
profitable_list = []
scraper_status = {"running_loop": False}
restart_state = {"requested": False}

RECAPTCHA_TITLE_MARKER = "confirm you are human"

# SCRAPER_RUNNING = False
# SCRAPER_TASK = None

def generate_uuid() -> str:
    return str(uuid.uuid4())


def request_server_restart(reason: str) -> None:
    """
    Restart the current process once (used for hard captcha recovery).
    """
    if restart_state["requested"]:
        return
    restart_state["requested"] = True
    logger.error("Server restart requested: %s", reason)
    python = sys.executable
    os.execv(python, [python] + sys.argv)

class UserORM(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ISBNORM(Base):
    __tablename__ = "isbns"

    id = Column(String, primary_key=True, default=generate_uuid)
    isbn = Column(String, unique=True, nullable=False)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ISBNORM(id={self.id}, isbn='{self.isbn}', last_checked={self.last_checked})>"

class ProfitableFindORM(Base):
    __tablename__ = "profitable_finds"
    id = Column(String, primary_key=True, default=generate_uuid)
    isbn = Column(String)
    title = Column(String, nullable=True)
    buy_price = Column(Float)
    buyback_price = Column(Float)
    profit = Column(Float)
    buy_link = Column(String, nullable=True)
    buyback_link = Column(String, nullable=True)
    seller_name = Column(String, nullable=True)
    seller_country = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    found_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notified = Column(Boolean, default=False)

class BannedEntityORM(Base):
    __tablename__ = "banned_entities"
    id = Column(String, primary_key=True, default=generate_uuid)
    entity_type = Column(String, nullable=False)
    value = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ScraperLogORM(Base):
    __tablename__ = "logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    log_type = Column(String)  # 'info', 'error', 'success'
    message = Column(String)
    isbn = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ScraperCheckpointORM(Base):
    __tablename__ = "scraper_checkpoint"
    id = Column(String, primary_key=True, default=generate_uuid)
    state_key = Column(String, unique=True, nullable=False)  # e.g. "isbn_resume"
    last_isbn = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# --- Pydantic schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ISBNItemSchema(BaseModel):
    id: str
    isbn: str
    added_at: Optional[datetime] = None
    last_checked: Optional[datetime] = None

    class Config:
        from_attributes = True

class ISBNBulkUpload(BaseModel):
    isbns: List[str]
    
class BannedEntityBulkUpload(BaseModel):
    entity_type: str
    values: List[str]

class BannedEntitySchema(BaseModel):
    id: str
    entity_type: str
    value: str
    created_at: Optional[datetime] = None

    class Config:
       from_attributes = True

class BannedEntityCreate(BaseModel):
    entity_type: str
    value: str

class ProfitableFindSchema(BaseModel):
    id: str
    isbn: str
    title: Optional[str] = None
    buy_price: float
    buyback_price: float
    profit: float
    buy_link: Optional[str] = None
    buyback_link: Optional[str] = None
    seller_name: Optional[str] = None
    seller_country: Optional[str] = None
    condition: Optional[str] = None
    found_at: Optional[datetime] = None
    notified: Optional[bool] = False

    class Config:
        from_attributes = True

class ScraperLogSchema(BaseModel):
    id: str
    log_type: str
    message: str
    isbn: Optional[str] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScraperStatsSchema(BaseModel):
    total_isbns: int
    checked_today: int
    profitable_finds: int
    last_check: Optional[datetime] = None
    running: bool

# --- Security / Auth helpers ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserCreate:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with async_session() as session:
        q = await session.execute(select(UserORM).where(UserORM.email == email))
        user = q.scalars().first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # return an object with needed fields; we return ORM for convenience to update password later
        return user

# --- Scraper import (user must supply scraper.py with these coros) ---
# scraper.py should expose async def scrape_bookfinder(isbn: str, filters: dict) -> dict
# and async def send_email_alert(email: str, find: ProfitableFindORM)


async def scraper_task():
    global csv_list, profitable_list # fix UnboundLocalError
    is_profitable = False
    try:
        async with async_session() as session:
            q = await session.execute(select(ISBNORM))
            isbns = q.scalars().all()

            if not isbns:
                log = ScraperLogORM(log_type="info", message="No ISBN records found in database")
                session.add(log)
                await session.commit()
                return

            checkpoint_q = await session.execute(
                select(ScraperCheckpointORM).where(ScraperCheckpointORM.state_key == "isbn_resume")
            )
            checkpoint = checkpoint_q.scalars().first()
            if not checkpoint:
                checkpoint = ScraperCheckpointORM(state_key="isbn_resume", last_isbn=None)
                session.add(checkpoint)
                await session.commit()

            # Resume from the next ISBN after the last processed one.
            if checkpoint.last_isbn:
                last_idx = next(
                    (idx for idx, item in enumerate(isbns) if item.isbn == checkpoint.last_isbn),
                    None,
                )
                if last_idx is not None and len(isbns) > 1:
                    isbns = isbns[last_idx + 1:] + isbns[:last_idx + 1]

            await pass_captcha(isbns[0].isbn)
            await asyncio.sleep(1.0)  # short pause to ensure CAPTCHA state settles

            for isbn_item in isbns:
                if not scraper_status["running_loop"]:
                    break
                 # get banned entities
                be_q = await session.execute(select(BannedEntityORM))
                banned_entities = be_q.scalars().all()
                banned_sellers = [b.value.lower() for b in banned_entities if b.entity_type == "seller"]
                banned_countries = [b.value.lower() for b in banned_entities if b.entity_type == "country"]
                banned_websites = [b.value.lower() for b in banned_entities if b.entity_type == "website"]
                filters = {"sellers": banned_sellers, "countries": banned_countries, "websites": banned_websites}

                try:
                    result = await scrape_bookfinder(isbn_item.isbn, filters)

                    title_text = str(result.get("title") or "").lower()
                    if RECAPTCHA_TITLE_MARKER in title_text:
                        warn_msg = f"Captcha page detected for {isbn_item.isbn}; restarting server"
                        logger.warning(warn_msg)
                        session.add(ScraperLogORM(log_type="error", message=warn_msg, isbn=isbn_item.isbn))
                        await session.commit()
                        request_server_restart(warn_msg)

                    # Retry once if both prices are 0
                    if result.get("buy_price", 0) == 0 and result.get("buyback_price", 0) == 0:
                        logger.warning(f"No prices found for {isbn_item.isbn}. Retrying once...")
                        await asyncio.sleep(
                            float(os.environ.get("BOOKFINDER_EMPTY_RETRY_DELAY", "10"))
                        )
                        result = await scrape_bookfinder(isbn_item.isbn, filters)
                    
                    if result.get("buy_price", 0) == 0:
                        continue

                    csv_list.append(result)

                    if csv_list and len(csv_list) > len(isbns):
                        csv_list.pop(0)

                    # update last_checked
                    isbn_item.last_checked = datetime.now(timezone.utc)
                    session.add(isbn_item)
                    await session.commit()

                    profit_value = result.get("profit", 0.0)
                    if profit_value < 5.0:
                        continue

                    if result and result.get("is_profitable"):
                        is_profitable = True
                        profitable_list.append(result)
                        find = ProfitableFindORM(
                            isbn=isbn_item.isbn,
                            title=result.get("title"),
                            buy_price=result.get("buy_price", 0.0),
                            buyback_price=result.get("buyback_price", 0.0),
                            profit=result.get("profit", 0.0),
                            buy_link=result.get("buy_link"),
                            buyback_link=result.get("buyback_link"),
                            seller_name=result.get("seller_name"),
                            seller_country=result.get("seller_country"),
                            condition=result.get("condition"),
                        )
                        session.add(find)
                        await session.commit()


                        log = ScraperLogORM(log_type="success", message=f"Profitable find: ${profit_value}", isbn=isbn_item.isbn)
                        session.add(log)
                        await session.commit()

                        admin_email = os.environ.get("ADMIN_EMAIL")
                        if admin_email:
                            # send email alert (async)
                            try:
                                await send_email_alert(admin_email, profitable_list)
                            except Exception as e:
                                logger.exception("Failed to send email alert: %s", e)
                            is_profitable = False
                            profitable_list.clear()
                    else:
                        log = ScraperLogORM(log_type="info", message="Not profitable or missing data", isbn=isbn_item.isbn)
                        session.add(log)
                        await session.commit()
                except Exception as e:
                    error_msg = f"Error scraping {isbn_item.isbn}: {str(e)}"
                    logger.exception(error_msg)
                    session.add(ScraperLogORM(log_type="error", message=error_msg, isbn=isbn_item.isbn))
                    await session.commit()
                finally:
                    # Persist progress after each ISBN so restart resumes from next item.
                    checkpoint.last_isbn = isbn_item.isbn
                    checkpoint.updated_at = datetime.now(timezone.utc)
                    session.add(checkpoint)
                    await session.commit()

                # Add delay between scrapes to avoid rate limits (shared datacenter IPs need more).
                _scrape_inter_isbn_delay()
            
            # final info log
            info_log = ScraperLogORM(log_type="info", message=f"Completed scraping {len(isbns)} ISBNs")
            session.add(info_log)
            await session.commit()
            print("Scraper task completed")
    except Exception as e:
        async with async_session() as session:
            log = ScraperLogORM(log_type="error", message=f"Scraper error: {str(e)}")
            session.add(log)
            await session.commit()
        logger.exception("Scraper main error: %s", e)

def _human_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def _scrape_inter_isbn_delay() -> None:
    """Pause between ISBNs to reduce 429s (tune with BOOKFINDER_SCRAPE_DELAY_MIN / _MAX)."""
    lo = float(os.environ.get("BOOKFINDER_SCRAPE_DELAY_MIN", "8"))
    hi = float(os.environ.get("BOOKFINDER_SCRAPE_DELAY_MAX", "22"))
    if hi < lo:
        lo, hi = hi, lo
    _human_delay(lo, hi)

# --- FastAPI app & router ---
app = FastAPI()
api_router = APIRouter(prefix="/api")

# if FRONTEND_BUILD.exists():
#     app.mount("/", StaticFiles(directory=FRONTEND_BUILD, html=True), name="frontend")
# else:
#     print("⚠️ Warning: React build folder not found. Run `npm run build` in frontend/")

# --- Routes: Auth ---
@api_router.post("/auth/register", response_model=Token)
async def register(user_create: UserCreate):
    async with async_session() as session:
        q = await session.execute(select(UserORM).where(UserORM.email == user_create.email))
        existing = q.scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = UserORM(email=user_create.email, hashed_password=hash_password(user_create.password))
        session.add(user)
        await session.commit()
        token = create_access_token({"sub": user.email})
        return {"access_token": token, "token_type": "bearer"}

@api_router.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin):
    async with async_session() as session:
        q = await session.execute(select(UserORM).where(UserORM.email == user_login.email))
        user = q.scalars().first()
        if not user or not verify_password(user_login.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token({"sub": user.email})
        return {"access_token": token, "token_type": "bearer"}

@api_router.post("/auth/change-password")
async def change_password(password_data: dict, current_user: UserORM = Depends(get_current_user)):
    # expects {"old_password": "...", "new_password": "..."} OR use PasswordChange schema
    old = password_data.get("old_password") or password_data.get("oldPassword") or password_data.get("old")
    new = password_data.get("new_password") or password_data.get("newPassword") or password_data.get("new")
    if not old or not new:
        raise HTTPException(status_code=400, detail="old_password and new_password are required")
    if not verify_password(old, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    async with async_session() as session:
        current_user.hashed_password = hash_password(new)
        session.add(current_user)
        await session.commit()
    return {"message": "Password changed successfully"}

# --- ISBN endpoints ---
@api_router.get("/isbns", response_model=List[ISBNItemSchema])
async def get_isbns(current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        q = await session.execute(select(ISBNORM))
        items = q.scalars().all()
        return [ISBNItemSchema.from_orm(i) for i in items]

@api_router.post("/isbns", response_model=ISBNItemSchema)
async def add_isbn(isbn: str, current_user: Any = Depends(get_current_user)):
    isbn = isbn.strip()
    async with async_session() as session:
        q = await session.execute(select(ISBNORM).where(ISBNORM.isbn == isbn))
        existing = q.scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="ISBN already exists")
        item = ISBNORM(isbn=isbn)
        session.add(item)
        await session.commit()
        return ISBNItemSchema.from_orm(item)

@api_router.post("/isbns/bulk")
async def bulk_upload_isbns(upload: ISBNBulkUpload, current_user: Any = Depends(get_current_user)):
    added = 0
    duplicates = 0
    async with async_session() as session:
        for raw in upload.isbns:
            isbn = raw.strip()
            if not isbn:
                continue
            q = await session.execute(select(ISBNORM).where(ISBNORM.isbn == isbn))
            if q.scalars().first():
                duplicates += 1
                continue
            item = ISBNORM(isbn=isbn)
            session.add(item)
            added += 1
        await session.commit()
    return {"added": added, "duplicates": duplicates}

@api_router.post("/banned/bulk")
async def bulk_upload_banner(upload: BannedEntityBulkUpload, current_user: Any = Depends(get_current_user)):
    if upload.entity_type not in ["seller", "country", "website"]:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    added = 0
    duplicates = 0
    async with async_session() as session:
        for raw in upload.values:
            value = raw.strip()
            if not value:
                continue

            q = await session.execute(select(BannedEntityORM).where(BannedEntityORM.entity_type == upload.entity_type, BannedEntityORM.value == value)
            )
            if q.scalars().first():
                duplicates += 1
                continue

            entity = BannedEntityORM(entity_type=upload.entity_type, value=value)
            session.add(entity)
            added += 1

        await session.commit()

    return {"added": added, "duplicates": duplicates}

@api_router.delete("/banned/reset")
async def reset_banners():
    async with async_session() as session:
        await session.execute(delete(BannedEntityORM))  # Assuming SQLAlchemy
        await session.commit()
        return {"message": "All Banners deleted"}


@api_router.delete("/isbns/reset")
async def reset_isbns():
    async with async_session() as session:
        await session.execute(delete(ISBNORM))  # Assuming SQLAlchemy
        await session.commit()
        return {"message": "All ISBNs deleted"}

@api_router.delete("/isbns/{isbn}")
async def delete_isbn(isbn: str, current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        q = await session.execute(select(ISBNORM).where(ISBNORM.isbn == isbn))
        item = q.scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="ISBN not found")
        await session.delete(item)
        await session.commit()
    return {"message": "ISBN deleted"}

# --- Banned entities ---
@api_router.get("/banned", response_model=List[BannedEntitySchema])
async def get_banned_entities(current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        q = await session.execute(select(BannedEntityORM))
        items = q.scalars().all()
        return [BannedEntitySchema.from_orm(i) for i in items]

@api_router.post("/banned", response_model=BannedEntitySchema)
async def add_banned_entity(entity_create: BannedEntityCreate, current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        q = await session.execute(
            select(BannedEntityORM).where(
                BannedEntityORM.entity_type == entity_create.entity_type,
                BannedEntityORM.value == entity_create.value
            )
        )
        if q.scalars().first():
            raise HTTPException(status_code=400, detail="Entity already banned")
        ent = BannedEntityORM(entity_type=entity_create.entity_type, value=entity_create.value)
        session.add(ent)
        await session.commit()
        return BannedEntitySchema.from_orm(ent)

@api_router.delete("/banned/{entity_id}")
async def delete_banned_entity(entity_id: str, current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        q = await session.execute(select(BannedEntityORM).where(BannedEntityORM.id == entity_id))
        ent = q.scalars().first()
        if not ent:
            raise HTTPException(status_code=404, detail="Entity not found")
        await session.delete(ent)
        await session.commit()
    return {"message": "Entity removed"}

# --- Profitable finds ---
@api_router.get("/profitable", response_model=List[ProfitableFindSchema])
async def get_profitable_finds(current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        q = await session.execute(select(ProfitableFindORM).order_by(desc(ProfitableFindORM.found_at)).limit(100))
        finds = q.scalars().all()
        return [ProfitableFindSchema.from_orm(f) for f in finds]
    
@api_router.delete("/profitable/reset")
async def reset_profitable():
    async with async_session() as session:
        await session.execute(delete(ProfitableFindORM))  # Replace with your model name
        await session.commit()
        return {"message": "All profitable finds cleared"}


@api_router.delete("/logs/reset")
async def reset_logs():
    async with async_session() as session:
        await session.execute(delete(ScraperLogORM))  # replace with your log table/model
        await session.commit()
        return {"message": "All logs deleted"}

@api_router.get("/logs", response_model=List[ScraperLogSchema])
async def get_logs(current_user: Any = Depends(get_current_user)):
    """
    Fetch the latest 100 logs for the authenticated user.
    Returns an empty list if no logs are found.
    """
    try:
        async with async_session() as session:
            q = await session.execute(
                select(ScraperLogORM)
                .order_by(desc(ScraperLogORM.timestamp))
                .limit(100)
            )
            logs = q.scalars().all()

        # ✅ Always return a list (even if empty)
        return [ScraperLogSchema.from_orm(l) for l in logs]

    except HTTPException:
        # re-raise auth or permission errors directly
        raise
    except Exception as e:
        # Log and return a structured error
        print(f"❌ Error fetching logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching logs from database."
        )

# --- Stats ---
@api_router.get("/stats", response_model=ScraperStatsSchema)
async def get_stats(current_user: Any = Depends(get_current_user)):
    async with async_session() as session:
        total_q = await session.execute(select(func.count()).select_from(ISBNORM))
        total_isbns = total_q.scalar_one()
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        checked_q = await session.execute(select(func.count()).select_from(ISBNORM).where(ISBNORM.last_checked >= today_start))
        checked_today = checked_q.scalar_one()
        profitable_q = await session.execute(select(func.count()).select_from(ProfitableFindORM))
        profitable_finds = profitable_q.scalar_one()

        last_check_q = await session.execute(select(ISBNORM).where(ISBNORM.last_checked != None).order_by(desc(ISBNORM.last_checked)).limit(1))
        last_doc = last_check_q.scalars().first()
        last_check = last_doc.last_checked if last_doc else None

        return ScraperStatsSchema(
            total_isbns=total_isbns,
            checked_today=checked_today,
            profitable_finds=profitable_finds,
            last_check=last_check,
            running=scraper_status["running_loop"]
        )

# --- Export CSV ---
@api_router.get("/export/csv")
async def export_csv(current_user: Any = Depends(get_current_user)):

    output = StringIO()
    fieldnames = [
        "isbn", "title", "buy_price", "buyback_price", "profit",
        "seller_name", "seller_country",
        "condition", "buy_link", "buyback_link", "found_at"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for f in csv_list:
        writer.writerow({
            "isbn": f["isbn"] or "",
            "title": f["title"] or "",
            "buy_price": f["buy_price"] or 0,
            "buyback_price": f["buyback_price"] or 0,
            "profit": f["profit"] or 0,
            "seller_name": f["seller_name"] or "",
            "seller_country": f["seller_country"] or "",
            "condition": f["condition"] or "",
            "buy_link": f["buy_link"] or "",
            "buyback_link": f["buyback_link"] or "",
            "found_at": datetime.now(timezone.utc)
        })

    output.seek(0)
    csv_list.clear()
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=profitable_finds.csv"})

# --- Manual trigger scraper (background) ---
@api_router.post("/scraper/run")
async def manual_scraper_run(current_user: Any = Depends(get_current_user)):
    if scraper_status.get("running_loop", False):
        return {"message": "Scraper loop is already running"}

    # Flag to indicate loop started
    scraper_status["running_loop"] = True

    async def loop_scraper():
        while scraper_status["running_loop"]:
            try:
                await scraper_task()
            except Exception as e:
                logger.exception(f"Error in scraper loop: {e}")
            await asyncio.sleep(
                float(os.environ.get("BOOKFINDER_FULL_LOOP_PAUSE_SECONDS", "30"))
            )

    # Start the loop in the background
    asyncio.create_task(loop_scraper())
    return {"message": "Scraper started in infinite loop"}

@api_router.post("/scraper/stop")
async def stop_scraper():
    """
    Sets a stop flag which the scraper checks on each loop.
    """
    scraper_status["running_loop"] = False

    return {"message": "Scraper stop signal sent."}

# --- Include router and middlewares ---
app.include_router(api_router)

origins = [
   "https://book-arbitrage.onrender.com",  # frontend ngrok URL
   # "http://localhost:3000",  # frontend ngrok URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or only your ngrok frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Startup / Shutdown events ---
@app.on_event("startup")
async def startup_event():
    # Create tables

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create default admin if none exists
    async with async_session() as session:
        q = await session.execute(select(UserORM))
        users = q.scalars().all()
        if len(users) == 0:
            default_user = UserORM(
                email="njh1744@gmail.com",
                hashed_password=hash_password("admin123")
            )
            session.add(default_user)
            await session.commit()

@app.on_event("shutdown")
async def shutdown_event():
    try:
        await shutdown_playwright()
    except Exception:
        logger.exception("Error closing Playwright")
    try:
        await engine.dispose()
    except Exception:
        pass
