from typing import Literal

from pydantic import BaseModel, Field

InputType = Literal["http", "error", "code", "ctf", "linux", "protocol", "general"]


class AnalysisRequest(BaseModel):
    """分析请求。input_type 为客户端猜测值，后端会重新识别并以 meta 事件返回最终类型。"""

    input_text: str = Field(min_length=1, max_length=8000)
    input_type: InputType | None = None
