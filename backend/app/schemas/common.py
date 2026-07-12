"""统一 API 响应模型。所有接口返回 {code, message, data} 结构。"""

from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, message: str, code: int = 1, data: Any = None) -> "ApiResponse":
        return cls(code=code, message=message, data=data)
