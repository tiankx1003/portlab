"""FastAPI 入口。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import backtest, data, health, symbols
from .schemas.common import ApiResponse

app = FastAPI(title="PortLab", version="0.1.0")

# 开发期允许前端（5173）跨域访问；同时 vite 已做 /api 代理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数校验失败也统一为 ApiResponse 格式（HTTP 200，code:1）。"""
    parts: list[str] = []
    for err in exc.errors():
        field = ".".join(str(x) for x in err["loc"] if x not in ("body", "query", "path"))
        msg = err["msg"].removeprefix("Value error, ") if err["msg"].startswith("Value error, ") else err["msg"]
        parts.append(f"{field}: {msg}" if field else msg)
    message = "; ".join(parts) or "参数校验失败"
    return JSONResponse(status_code=200, content=ApiResponse.error(message=message).model_dump())


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(symbols.router, prefix="/api/symbols", tags=["symbols"])
