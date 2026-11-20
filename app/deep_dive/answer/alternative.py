from pydantic import BaseModel, Field

from .prose import Prose


class Alternative(BaseModel):
    name: Prose = Field(description="The technology that could replace it, e.g. RabbitMQ.")
    trade_off: Prose = Field(description="What switching would gain and lose, in this codebase's terms.")
