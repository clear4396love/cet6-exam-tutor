from dataclasses import dataclass


@dataclass(frozen=True)
class ragconfig:
    llm_name: str = "deepseek-v4-flash"
    temperature: float = 0.2
    max_tokens: int = 2048
    content_max_length: int = 1000
