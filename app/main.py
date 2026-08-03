import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.api.router import router

logger = logging.getLogger("tvoy-golos")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="Твой Голос — API",
    version="1.0.0",
    docs_url="/docs" if settings.env == "development" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — только разрешённые origins, без credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *settings.frontend_origins_list,
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    # Content-Disposition не входит в safelist заголовков CORS по умолчанию —
    # без явного expose_headers JS на фронтенде не может прочитать имя файла
    # из ответа /generate-document, даже при успешном запросе.
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логируем только метод, путь и IP — без тела запроса."""
    start = time.time()
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"{request.method} {request.url.path} from {client_ip}")
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000)
    logger.info(f"→ {response.status_code} ({elapsed}ms)")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})


app.include_router(router, prefix="/api")
