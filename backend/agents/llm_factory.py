import asyncio
import random
import logging
from enum import Enum
from pydantic import BaseModel
from typing import Any, Callable, Literal, Type, TypeVar, cast, Union, Optional

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.exceptions import ErrorCode
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.output_parsers import PydanticToolsParser
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class OpenAIModel(Enum):
    O1_MINI = "o1-mini"
    O1 = "o1"
    O1_PRO = "o1-pro"
    O3_MINI = "o3-mini"
    O3 = "o3"
    O3_PRO = "o3-pro"
    O4_MINI = "o4-mini"
    GPT_5 = "gpt-5-2025-08-07"
    GPT_5_MINI = "gpt-5-mini-2025-08-07"
    GPT_5_NANO = "gpt-5-nano-2025-08-07"

    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    GPT_4_1 = "gpt-4.1"
    GPT_4_1_NANO = "gpt-4.1-nano"


class AnthropicModel(Enum):
    CLAUDE_HAIKU_3_5 = "claude-3-5-haiku-latest"
    CLAUDE_SONNET_3_5 = "claude-3-5-sonnet-latest"
    CLAUDE_SONNET_3_7 = "claude-3-7-sonnet-latest"
    CLAUDE_SONNET_4 = "claude-sonnet-4-0"
    CLAUDE_OPUS_4 = "claude-opus-4-0"
    CLAUDE_OPUS_4_1 = "claude-opus-4-1"


AIModel = Union[OpenAIModel, AnthropicModel]


T = TypeVar("T", bound=BaseModel)


class LLMFactory:
    def _init_openai_client(
        self,
        model: OpenAIModel,
        temperature: Optional[float] = None,
    ) -> ChatOpenAI:
        if temperature is None:
            return ChatOpenAI(
                model=model.value,
                max_retries=0,
            )
        return ChatOpenAI(
            model=model.value,
            temperature=temperature,
            max_retries=0,
        )

    def _init_anthropic_client(
        self,
        model: AnthropicModel,
        temperature: Optional[float] = None,
    ) -> ChatAnthropic:
        # ChatAnthropic has default max output token to be 1024, so we have to set it to the max token for the model.
        max_tokens_to_sample = get_max_output_token_for_model(model)

        if temperature is None:
            return ChatAnthropic(
                model_name=model.value,
                stop=["\n\nHuman:"],
                max_retries=0,
                timeout=60,
                max_tokens_to_sample=max_tokens_to_sample,
            )
        return ChatAnthropic(
            model_name=model.value,
            temperature=temperature,
            timeout=60,
            stop=["\n\nHuman:"],
            max_retries=0,
            max_tokens_to_sample=max_tokens_to_sample,
        )

    def _init_llm_client(
        self,
        model: Union[AIModel, str],
        temperature: Optional[float] = None,
    ) -> Union[ChatOpenAI, ChatAnthropic]:
        if isinstance(model, OpenAIModel):
            return self._init_openai_client(model, temperature)
        elif isinstance(model, AnthropicModel):
            return self._init_anthropic_client(model, temperature)
        else:
            raise ValueError(f"Model {model} (type: {type(model)}) is not supported")

    def _get_available_structured_output_method(
        self, model: AIModel
    ) -> Literal["json_mode", "function_calling", "json_schema"]:
        """
        As of 2025 July, OpenAI recent models all support 'structured_output' which is json_schema in LangChain's terminology.
        Anthropic models don't support any structured output methods but function calling.

        "json_mode" was used from OpenAI before structured_output(json_schema) was introduced. Now it's better to use json_schema.

        """
        if isinstance(model, OpenAIModel):
            return "json_schema"  # TODO: need to use json_schema with a new schema converter
        elif isinstance(model, AnthropicModel):
            return "function_calling"
        else:
            raise ValueError(f"Unknown model type: {type(model)}")

    async def ainvoke(
        self,
        prompts: list[BaseMessage],
        model: AIModel,
        output_schema: Optional[Type[T]] = None,
        tools: Optional[list[Type[BaseModel]]] = None,
        method: Optional[
            Literal["json_mode", "function_calling", "json_schema"]
        ] = None,
        temperature: Optional[float] = None,
        fallback_models: list[AIModel] = [],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> Any:
        if output_schema and temperature is not None:
            raise ValueError(
                "Temperature cannot be provided when output_schema is provided"
            )

        if isinstance(model, str):
            model = string_to_ai_model(model)

        llm = self._init_llm_client(model, temperature)

        # Apply structured output if schema is provided
        if output_schema:
            if method is None:
                method = self._get_available_structured_output_method(model)
            llm = llm.with_structured_output(
                schema=output_schema,
                method=method,
                include_raw=True,
            )
        elif tools:
            llm = llm.bind_tools(tools)

        if fallback_models:
            fallback_llms = []
            for fallback_model in fallback_models:
                fallback_client = self._init_llm_client(fallback_model, temperature)
                if output_schema:
                    if method is None:
                        method = self._get_available_structured_output_method(
                            fallback_model
                        )
                    fallback_client = fallback_client.with_structured_output(
                        schema=output_schema,
                        method=method,
                        include_raw=True,
                    )
                elif tools:
                    fallback_client = fallback_client.bind_tools(tools)
                fallback_llms.append(
                    cast(Runnable[LanguageModelInput, BaseMessage], fallback_client)
                )

            llm = llm.with_fallbacks(fallback_llms)

        if tools:
            llm = llm | PydanticToolsParser(tools=tools)

        response = await self._exception_handler(
            func=llm.ainvoke,
            model=model,
            prompts=prompts,
            max_retries=max_retries,
            base_delay=base_delay,
            output_schema=output_schema,
        )

        if (
            output_schema
            and isinstance(response, dict)
            and not response.get("parsing_error")
        ):
            return response["parsed"]
        elif (
            output_schema
            and isinstance(response, dict)
            and response.get("parsing_error")
        ):
            logger.error(
                f"Parsing error for model {model}: {response.get('parsing_error')}"
            )
            return response.get("raw")
        elif tools:
            return response
        elif not output_schema and not tools:
            return response
        elif response is None:
            logger.critical(
                "Got None response from the model, meaning it failed after retries."
            )
            return None
        else:
            logger.error(
                f"Unhandled response / type: {type(response)}, value: {response}"
            )
            return response

    async def _exception_handler(
        self,
        func: Callable,
        model: AIModel,
        prompts: list[BaseMessage],
        max_retries: int = 3,
        base_delay: float = 10.0,
        output_schema: Optional[Type[T]] = None,
    ) -> Union[BaseMessage, dict[str, Any], None]:
        for attempt in range(max_retries + 1):
            response = None
            try:
                response = await func(prompts)

                # We are using include_raw=True in the structured_output, which returns a dict with raw and parsing_error keys.
                # When the output schema validation fails, we get parsing_error in the response.
                if (
                    output_schema
                    and isinstance(response, dict)
                    and response.get("parsing_error")
                ):
                    try:
                        if isinstance(response["raw"].content, str):
                            response_content = response["raw"].content
                        elif isinstance(response["raw"].content, list):
                            response_content = [
                                item.model_dump_json()
                                if hasattr(item, "model_dump_json")
                                else str(item)
                                for item in response["raw"].content
                            ]
                        else:
                            response_content = (
                                response["raw"].content.model_dump_json()
                                if hasattr(response["raw"].content, "model_dump_json")
                                else str(response["raw"].content)
                            )
                    except Exception as e:
                        logger.error(
                            f"Error converting response content to string for model {model}: {e}"
                        )
                        break

                    # When the response doesn't follow the output schema, Add the response and error message to the prompt and try again.
                    prompts.extend(
                        [
                            AIMessage(content=response_content),
                            HumanMessage(
                                content=f"Your last response was invalid causing the following error:\n\n{response.get('parsing_error')}\n\nPlease fix the error and try again. Here is the correct json output schema:\n\n{output_schema.model_json_schema()}"
                            ),
                        ]
                    )
                    continue

                return response
            except Exception as e:
                error_message = str(e).lower()

                if ErrorCode.INVALID_PROMPT_INPUT.value.lower() in error_message:
                    logger.error(
                        f"Invalid prompt input for model {model}: {error_message}"
                    )
                elif ErrorCode.INVALID_TOOL_RESULTS.value.lower() in error_message:
                    logger.error(
                        f"Invalid tool results for model {model}: {error_message}"
                    )
                elif ErrorCode.MESSAGE_COERCION_FAILURE.value.lower() in error_message:
                    logger.error(
                        f"Message coercion failure for model {model}: {error_message}"
                    )
                elif (
                    ErrorCode.MODEL_AUTHENTICATION.value.lower() in error_message
                    or "401" in error_message
                    or "403" in error_message
                    or "unauthorized" in error_message
                    or "permission denied" in error_message
                ):
                    logger.error(
                        f"Authentication error with model {model}: {error_message}"
                    )
                elif (
                    ErrorCode.MODEL_NOT_FOUND.value.lower() in error_message
                    or "404" in error_message
                    or "not found" in error_message
                ):
                    logger.error(f"Model not found: {model}: {error_message}")
                    raise ValueError(f"Model not found: {model}: {error_message}")
                elif (
                    ErrorCode.MODEL_RATE_LIMIT.value.lower() in error_message
                    or "429" in error_message  # openai
                    or "529" in error_message  # anthropic
                    or "rate limit" in error_message
                    or "bad request" in error_message
                ):
                    if attempt < max_retries:
                        # Calculate exponential backoff delay with jitter
                        delay = base_delay * (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"Rate limit exceeded for model {model} (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"Rate limit exceeded for model {model} after {max_retries + 1} attempts: {error_message}"
                        )
                elif ErrorCode.OUTPUT_PARSING_FAILURE.value.lower() in error_message:
                    logger.error(
                        f"Output parsing failed for model {model}: {error_message}"
                    )
                elif "503" in error_message:
                    logger.error(
                        f"Internal server error with model {model}: {error_message}"
                    )
                elif "400" in error_message and "invalid schema" in error_message:
                    logger.error(
                        f"Invalide Schema error with model {model}: {error_message}"
                    )
                    break
                else:
                    logger.error(f"LangChain error with model {model}: {error_message}")

        logger.critical(
            f"Failed to get valid response from {model} after {max_retries + 1} attempts"
        )
        raise ValueError(
            f"Failed to get valid response from {model} after {max_retries + 1} attempts. Try again with a different model."
        )

    async def parallel_ainvoke(
        self,
        models: list[AIModel],
        total_invocations: int,
        messages: list[BaseMessage],
        output_schema: Type[T],
        temperature: float = 0.7,
        method: Literal["json_mode", "function_calling"] = "function_calling",
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> list[T]:
        """
        Makes parallel LLM calls across multiple models for majority voting.

        Args:
            models: List of AI models to use
            total_invocations: Total number of calls to make across all models
            messages: Messages to send to the models
            output_schema: Pydantic schema for structured output
            temperature: Temperature for the LLM calls
            method: Method for structured output generation
            max_retries: Maximum number of retries for rate limit errors
            base_delay: Base delay in seconds for exponential backoff

        Returns:
            List of responses from all models
        """
        average_call_per_model = total_invocations // len(models)
        remainder = total_invocations % len(models)

        model_call_count_map = {}

        for model in models:
            model_call_count_map[model] = average_call_per_model

        for model in models[:remainder]:
            model_call_count_map[model] += 1

        # Create tasks for parallel execution
        tasks = []

        for model, call_count in model_call_count_map.items():
            for _ in range(call_count):
                task = self.ainvoke(
                    prompts=messages,
                    model=model,
                    output_schema=output_schema,
                    method=method,
                    temperature=temperature,
                    max_retries=max_retries,
                    base_delay=base_delay,
                )
                tasks.append(task)

        # Execute all tasks in parallel
        responses: list[T] = await asyncio.gather(*tasks, return_exceptions=False)

        logger.debug(
            f"{len(responses)} responses received out of {total_invocations} voters"
        )
        return responses


def string_to_ai_model(model_string: str) -> AIModel:
    """
    Convert a string model name to the corresponding AIModel enum.

    Args:
        model_string: The model name as a string (e.g., "gpt-4o-mini", "claude-3-5-sonnet-latest")

    Returns:
        The corresponding AIModel enum

    Raises:
        ValueError: If the model string doesn't match any known model
    """
    # Check OpenAI models
    for openai_model in OpenAIModel:
        if openai_model.value == model_string:
            return openai_model

    # Check Anthropic models
    for anthropic_model in AnthropicModel:
        if anthropic_model.value == model_string:
            return anthropic_model

    # If no match found, raise an error with available options
    available_models = [model.value for model in OpenAIModel] + [
        model.value for model in AnthropicModel
    ]
    raise ValueError(
        f"Unknown model: {model_string}. Available models: {available_models}"
    )


def get_max_output_token_for_model(model: AIModel) -> int:
    if isinstance(model, OpenAIModel):
        return 10000
    elif isinstance(model, AnthropicModel):
        # Based on official Anthropic documentation
        if model == AnthropicModel.CLAUDE_OPUS_4_1:
            return 32000  # claude-opus-4-1-20250805
        elif model == AnthropicModel.CLAUDE_OPUS_4:
            return 32000  # claude-opus-4-20250514
        elif model == AnthropicModel.CLAUDE_SONNET_4:
            return 64000  # claude-sonnet-4-20250514
        elif model == AnthropicModel.CLAUDE_SONNET_3_7:
            return 64000  # claude-3-7-sonnet-20250219
        elif model == AnthropicModel.CLAUDE_SONNET_3_5:
            return 8192  # claude-3-5-sonnet-20241022 (upgraded version)
        elif model == AnthropicModel.CLAUDE_HAIKU_3_5:
            return 8192  # claude-3-5-haiku-20241022
        else:
            raise ValueError(f"Unknown Anthropic model: {model}")
    else:
        raise ValueError(f"Unknown model: {model}")
