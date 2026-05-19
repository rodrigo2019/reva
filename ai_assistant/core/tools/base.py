"""Base classes for REVA assistant tools."""

import inspect
from collections.abc import Callable
from typing import Any

from asgiref.sync import sync_to_async
from langchain_core.tools import BaseTool
from pydantic import BaseModel, PrivateAttr, create_model


def build_args_schema(func: Callable[..., Any]) -> type[BaseModel]:
    """Build a Pydantic args schema from a tool implementation signature."""

    fields: dict[str, tuple[Any, Any]] = {}
    for name, parameter in inspect.signature(func).parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if name in {"self", "cls"}:
            continue

        annotation = parameter.annotation
        if annotation is inspect.Parameter.empty:
            annotation = Any

        default = parameter.default
        if default is inspect.Parameter.empty:
            default = ...

        fields[name] = (annotation, default)

    model_name = f"{func.__name__.title().replace('_', '')}Input"
    return create_model(model_name, **fields)


class DjangoOrmTool(BaseTool):
    """LangChain BaseTool wrapper for synchronous Django ORM implementations."""

    name: str
    description: str
    args_schema: type[BaseModel]
    _func: Callable[..., Any] = PrivateAttr()

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        args_schema: type[BaseModel] | None = None,
    ) -> None:
        tool_name = name or func.__name__
        super().__init__(
            name=tool_name,
            description=description or inspect.getdoc(func) or tool_name,
            args_schema=args_schema or build_args_schema(func),
        )
        self._func = func

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        kwargs.pop("run_manager", None)
        kwargs.pop("config", None)
        return self._func(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        kwargs.pop("run_manager", None)
        kwargs.pop("config", None)
        return await sync_to_async(self._func, thread_sensitive=True)(*args, **kwargs)
