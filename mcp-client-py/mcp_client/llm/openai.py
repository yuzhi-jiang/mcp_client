"""OpenAI adapter for MCP Client."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .base import (
    ChatResponse,
    LLMAdapterFactory,
    LLMAdapterInterface,
    StreamingChatResponse,
)
from ..config.models import Message, Tool, ToolCall
from ..exceptions import AuthenticationError, ValidationError


logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMAdapterInterface):
    """OpenAI-compatible API adapter for LLM integration.
    
    This adapter works with OpenAI's API and compatible services
    (like DeepSeek, Together AI, etc.) that follow the OpenAI API format.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4",
        timeout: float = 60.0,
        max_retries: int = 3,
        **kwargs
    ) -> None:
        """Initialize OpenAI adapter.
        
        Args:
            api_key: OpenAI API key
            base_url: Base URL for the API (for compatible services)
            model: Model name to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            **kwargs: Additional OpenAI client configuration
        """
        super().__init__(api_key, base_url, model, **kwargs)
        
        if not api_key:
            raise AuthenticationError(
                "OpenAI API key is required",
                auth_type="api_key"
            )
        
        # Initialize OpenAI client
        client_kwargs = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
            **kwargs
        }
        
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        self.timeout = timeout
        
        # Model-specific configurations
        self._model_configs = {
            "gpt-4": {"max_tokens": 8192, "supports_tools": True},
            "gpt-4-turbo": {"max_tokens": 128000, "supports_tools": True},
            "gpt-4o": {"max_tokens": 128000, "supports_tools": True},
            "gpt-3.5-turbo": {"max_tokens": 4096, "supports_tools": True},
            "deepseek-chat": {"max_tokens": 32768, "supports_tools": True},
            "deepseek-coder": {"max_tokens": 32768, "supports_tools": True},
        }
    
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Union[ChatResponse, AsyncIterator[StreamingChatResponse]]:
        """Generate chat completion with optional tool use.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of available tools
            stream: Whether to stream the response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI API parameters
            
        Returns:
            ChatResponse for non-streaming, AsyncIterator for streaming
            
        Raises:
            ValidationError: If request parameters are invalid
            AuthenticationError: If API key is invalid
            LLMError: If the completion request fails
        """
        self.validate_messages(messages)
        
        # Convert messages to OpenAI format
        openai_messages = self._convert_messages_to_openai(messages)
        
        # Prepare request parameters
        request_params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "stream": stream,
            **kwargs
        }
        
        # Add tools if provided and supported
        if tools and self.supports_tool_calling():
            formatted_tools = self.format_tools(tools)
            if formatted_tools:
                request_params["tools"] = formatted_tools
                request_params["tool_choice"] = "auto"
        
        # Set max_tokens if provided
        if max_tokens:
            request_params["max_tokens"] = max_tokens
        
        try:
            if stream:
                return self._handle_streaming_response(request_params)
            else:
                return await self._handle_non_streaming_response(request_params)
                
        except Exception as e:
            await self._handle_api_error(e)
    
    async def _handle_non_streaming_response(self, request_params: Dict[str, Any]) -> ChatResponse:
        """Handle non-streaming chat completion response.
        
        Args:
            request_params: Request parameters for OpenAI API
            
        Returns:
            ChatResponse with the completion result
        """
        logger.debug(f"Making OpenAI chat completion request: {request_params}")
        
        response: ChatCompletion = await self.client.chat.completions.create(**request_params)
        
        choice = response.choices[0]
        message = choice.message
        
        # Extract content
        content = message.content or ""
        
        # Parse tool calls if present
        tool_calls = []
        if message.tool_calls:
            tool_calls = self.parse_tool_calls(message.tool_calls)
        
        # Extract usage information
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return ChatResponse(
            content=content,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=choice.finish_reason,
            usage=usage,
            model=response.model
        )
    
    async def _handle_streaming_response(
        self, 
        request_params: Dict[str, Any]
    ) -> AsyncIterator[StreamingChatResponse]:
        """Handle streaming chat completion response.
        
        Args:
            request_params: Request parameters for OpenAI API
            
        Yields:
            StreamingChatResponse chunks
        """
        logger.debug(f"Making OpenAI streaming chat completion request: {request_params}")
        
        accumulated_content = ""
        accumulated_tool_calls: Dict[int, Dict[str, Any]] = {}
        
        async for chunk in await self.client.chat.completions.create(**request_params):
            chunk: ChatCompletionChunk
            
            if not chunk.choices:
                continue
            
            choice = chunk.choices[0]
            delta = choice.delta
            
            # Handle content
            content_chunk = None
            if delta.content:
                content_chunk = delta.content
                accumulated_content += content_chunk
            
            # Handle tool calls
            tool_calls_chunk = None
            if delta.tool_calls:
                tool_calls_chunk = []
                
                for tc in delta.tool_calls:
                    tc_index = tc.index
                    
                    # Initialize tool call if new
                    if tc_index not in accumulated_tool_calls:
                        accumulated_tool_calls[tc_index] = {
                            "id": tc.id or "",
                            "type": tc.type or "function",
                            "function": {
                                "name": "",
                                "arguments": ""
                            }
                        }
                    
                    # Update tool call data
                    if tc.id:
                        accumulated_tool_calls[tc_index]["id"] = tc.id
                    if tc.type:
                        accumulated_tool_calls[tc_index]["type"] = tc.type
                    if tc.function:
                        if tc.function.name:
                            accumulated_tool_calls[tc_index]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            accumulated_tool_calls[tc_index]["function"]["arguments"] += tc.function.arguments
                
                # Convert to ToolCall objects for this chunk
                if accumulated_tool_calls:
                    tool_calls_chunk = []
                    for tc_data in accumulated_tool_calls.values():
                        if tc_data["function"]["name"]:  # Only include if we have a name
                            try:
                                arguments = json.loads(tc_data["function"]["arguments"]) if tc_data["function"]["arguments"] else {}
                            except json.JSONDecodeError:
                                arguments = {}
                            
                            tool_call = ToolCall(
                                id=tc_data["id"],
                                name=tc_data["function"]["name"],
                                arguments=arguments
                            )
                            tool_calls_chunk.append(tool_call)
            
            # Check if this is the final chunk
            is_complete = choice.finish_reason is not None
            
            yield StreamingChatResponse(
                content=content_chunk,
                tool_calls=tool_calls_chunk,
                finish_reason=choice.finish_reason,
                is_complete=is_complete
            )
            
            if is_complete:
                break
    
    def format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Format tools for OpenAI API.
        
        Args:
            tools: List of tools to format
            
        Returns:
            List of tool definitions in OpenAI format
        """
        formatted_tools = []
        
        for tool in tools:
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            }
            formatted_tools.append(tool_def)
        
        return formatted_tools
    
    def parse_tool_calls(self, tool_calls_data: Any) -> List[ToolCall]:
        """Parse tool calls from OpenAI response.
        
        Args:
            tool_calls_data: Raw tool calls data from OpenAI
            
        Returns:
            List of parsed tool calls
        """
        tool_calls = []
        
        for tc in tool_calls_data:
            try:
                # Parse arguments JSON
                arguments = {}
                if hasattr(tc.function, 'arguments') and tc.function.arguments:
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse tool call arguments: {e}")
                        arguments = {"raw_arguments": tc.function.arguments}
                
                tool_call = ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=arguments
                )
                tool_calls.append(tool_call)
                
            except Exception as e:
                logger.error(f"Failed to parse tool call: {e}")
                continue
        
        return tool_calls
    
    def _convert_messages_to_openai(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert internal Message objects to OpenAI format.
        
        Args:
            messages: List of internal messages
            
        Returns:
            List of messages in OpenAI format
        """
        openai_messages = []
        
        for message in messages:
            openai_message = {
                "role": message.role,
                "content": message.content
            }
            
            # Add tool calls if present
            if message.tool_calls:
                openai_message["tool_calls"] = []
                for tc in message.tool_calls:
                    openai_tool_call = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    openai_message["tool_calls"].append(openai_tool_call)
            
            openai_messages.append(openai_message)
        
        return openai_messages
    
    async def _handle_api_error(self, error: Exception) -> None:
        """Handle OpenAI API errors and convert to appropriate exceptions.
        
        Args:
            error: The original exception
            
        Raises:
            Appropriate MCP client exception
        """
        from ..exceptions import LLMError, TimeoutError
        
        error_message = str(error)
        
        # Handle authentication errors
        if "401" in error_message or "unauthorized" in error_message.lower():
            raise AuthenticationError(
                f"OpenAI API authentication failed: {error_message}",
                auth_type="api_key",
                cause=error
            )
        
        # Handle timeout errors
        if "timeout" in error_message.lower():
            raise TimeoutError(
                f"OpenAI API request timed out: {error_message}",
                timeout_seconds=self.timeout,
                operation="chat_completion",
                cause=error
            )
        
        # Handle validation errors
        if "400" in error_message or "invalid" in error_message.lower():
            raise ValidationError(
                f"Invalid request to OpenAI API: {error_message}",
                cause=error
            )
        
        # Generic LLM error for other cases
        raise LLMError(
            f"OpenAI API error: {error_message}",
            cause=error
        )
    
    def supports_tool_calling(self) -> bool:
        """Check if the current model supports tool calling.
        
        Returns:
            True if tool calling is supported
        """
        model_config = self._model_configs.get(self.model, {})
        return model_config.get("supports_tools", True)
    
    def get_max_tokens(self) -> Optional[int]:
        """Get maximum tokens for the current model.
        
        Returns:
            Maximum tokens if known, None otherwise
        """
        model_config = self._model_configs.get(self.model, {})
        return model_config.get("max_tokens")
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens using OpenAI's approximation.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated number of tokens
        """
        # OpenAI's rough estimation: ~4 characters per token for English
        # This is more accurate for OpenAI models
        return len(text) // 4


# Custom exception for LLM-related errors
class LLMError(Exception):
    """Exception raised for LLM-related errors."""
    
    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


# Register the OpenAI adapter with the factory
LLMAdapterFactory.register_adapter("openai", OpenAIAdapter)