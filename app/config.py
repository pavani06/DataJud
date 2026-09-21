"""Environment configuration; credentials never appear in the settings repr."""

from dataclasses import dataclass, field
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    timeout_seconds: float = 30
    data_dir: Path = Path("data")
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str):
            raise ValueError("DATAJUD_API_KEY deve ser texto.")
        key = self.api_key.strip()
        if any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise ValueError("DATAJUD_API_KEY contém caracteres inválidos.")
        object.__setattr__(self, "api_key", key)
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("DATAJUD_TIMEOUT_SECONDS deve ser finito e positivo.")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 3:
            raise ValueError("DATAJUD_MAX_RETRIES deve ser um inteiro entre 0 e 3.")
        if not isinstance(self.data_dir, (str, Path)) or not str(self.data_dir).strip():
            raise ValueError("DATAJUD_DATA_DIR deve indicar um diretório.")
        if "\x00" in str(self.data_dir):
            raise ValueError("DATAJUD_DATA_DIR contém caracteres inválidos.")
        object.__setattr__(self, "data_dir", Path(self.data_dir))

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            timeout = float(os.getenv("DATAJUD_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ValueError("DATAJUD_TIMEOUT_SECONDS deve ser numérico.") from None
        try:
            retries = int(os.getenv("DATAJUD_MAX_RETRIES", "2"))
        except ValueError:
            raise ValueError("DATAJUD_MAX_RETRIES deve ser inteiro.") from None
        return cls(
            api_key=os.getenv("DATAJUD_API_KEY", ""),
            timeout_seconds=timeout,
            data_dir=os.getenv("DATAJUD_DATA_DIR", "data"),
            max_retries=retries,
        )
