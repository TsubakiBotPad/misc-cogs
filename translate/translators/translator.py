from abc import ABCMeta, abstractmethod
from typing import Dict, Protocol, TypeVar, Type

CLS = TypeVar("CLS")


class Translator(Protocol, metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    async def build(cls: Type[CLS], keys: Dict[str, str]) -> CLS:
        ...

    @abstractmethod
    async def translate(self, source: str, target: str, text: str) -> str:
        ...
