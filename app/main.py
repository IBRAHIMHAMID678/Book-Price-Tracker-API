import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import books, health, scrape
from app.config import settings
from app.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    logger.info("Application starting up...")
    yield
    logger.info("Application shutting down...")


app = FastAPI(
    title="Book Price Tracker API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code}",
        extra={"request_id": request_id},
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_msgs = [f"{err.get('loc', ['field'])[-1]}: {err.get('msg')}" for err in errors]
    detail = "; ".join(error_msgs)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)

    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"Unhandled error processing {request.method} {request.url.path}: {exc}",
        exc_info=True,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error (request_id={request_id})"},
    )


@app.get("/")
async def root():
    return {"name": "Book Price Tracker API", "docs": "/docs"}


app.include_router(health.router)
app.include_router(books.router)
app.include_router(scrape.router)
