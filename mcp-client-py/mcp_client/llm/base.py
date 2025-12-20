"""Base LLM adapter interface for MCP Client."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from ..config.models import Message, Tool, ToolCall


@dataclass
class ChatResponse:
    """Response from a chat completion request.
    
    This class represents the response from an LLM chat completion,
    including the generated content and any tool calls.
    """
    
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    
    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls.
        
        Returns:
            True if response has tool calls, False otherwise
        """
        return self.tool_calls is not None and len(self.tool_calls) > 0


@dataclass
class StreamingChatResponse:
    """Streaming response from a chat completion request.
    
    This class represents a single chunk in a streaming chat completion response.
    """
    
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None
    is_complete: bool = False


class LLMAdapterInterface(ABC):
    """Abstract base class for LLM provider adapters.
    
    This interface defines the contract that all LLM adapter implementations
    must follow, enabling support for different LLM providers while maintaining
    a consistent API.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "default",
        **kwargs
    ) -> None:
        """Initialize the LLM adapter.
        
        Args:
            api_key: API key for the LLM service
            base_url: Base URL for the LLM API
            model: Model name to use
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.config = kwargs
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[ChatResponse, AsyncIterator[StreamingChatResponse]]:
        """Generate chat completion with optional tool use.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of available tools
            stream: Whether to stream the response
            **kwargs: Additional parameters for the completion request
            
        Returns:
            ChatResponse for non-streaming, AsyncIterator for streaming
            
        Raises:
            LLMError: If the completion request fails
        """
        pass
    
    @abstractmethod
    def format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Format tools for this provider's API.
        
        Args:
            tools: List of tools to format
            
        Returns:
            List of tool definitions in provider-specific format
        """
        pass
    
    @abstractmethod
    def parse_tool_calls(self, response_data: Any) -> List[ToolCall]:
        """Parse tool calls from provider response.
        
        Args:
            response_data: Raw response data from the provider
            
        Returns:
            List of parsed tool calls
        """
        pass
    
    def get_model(self) -> str:
        """Get the current model name.
        
        Returns:
            Model name
        """
        return self.model
    
    def set_model(self, model: str) -> None:
        """Set the model name.
        
        Args:
            model: New model name
        """
        self.model = model
    
    def get_provider_name(self) -> str:
        """Get the name of this LLM provider.
        
        Returns:
            Provider name
        """
        return self.__class__.__name__.replace("Adapter", "").lower()
    
    def supports_streaming(self) -> bool:
        """Check if this adapter supports streaming responses.
        
        Returns:
            True if streaming is supported, False otherwise
        """
        return True  # Most modern LLM APIs support streaming
    
    def supports_tool_calling(self) -> bool:
        """Check if this adapter supports tool calling.
        
        Returns:
            True if tool calling is supported, False otherwise
        """
        return True  # Assume tool calling is supported by default
    
    def get_max_tokens(self) -> Optional[int]:
        """Get the maximum number of tokens for this model.
        
        Returns:
            Maximum tokens if known, None otherwise
        """
        return None  # Override in subclasses with model-specific limits
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string.
        
        This is a rough estimation. Subclasses should override with
        provider-specific tokenization if available.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated number of tokens
        """
        # Rough estimation: ~4 characters per token for English text
        return len(text) // 4
    
    def validate_messages(self, messages: List[Message]) -> None:
        """Validate that messages are properly formatted.
        
        Args:
            messages: Messages to validate
            
        Raises:
            ValidationError: If messages are invalid
        """
        from ..exceptions import ValidationError
        
        if not messages:
            raise ValidationError("At least one message is required")
        
        for i, message in enumerate(messages):
            if not isinstance(message, Message):
                raise ValidationError(
                    f"Message {i} must be a Message instance",
                    field_path=f"messages[{i}]"
                )
            
            if not message.content and not message.tool_calls:
                raise ValidationError(
                    f"Message {i} must have either content or tool calls",
                    field_path=f"messages[{i}]"
                )
    
    def create_system_message(self, content: str) -> Message:
        """Create a system message.
        
        Args:
            content: System message content
            
        Returns:
            System message
        """
        return Message(role="system", content=content)
    
    def create_user_message(self, content: str) -> Message:
        """Create a user message.
        
        Args:
            content: User message content
            
        Returns:
            User message
        """
        return Message(role="user", content=content)
    
    def create_assistant_message(
        self, 
        content: str, 
        tool_calls: Optional[List[ToolCall]] = None
    ) -> Message:
        """Create an assistant message.
        
        Args:
            content: Assistant message content
            tool_calls: Optional tool calls made by the assistant
            
        Returns:
            Assistant message
        """
        return Message(role="assistant", content=content, tool_calls=tool_calls)
    
    def create_tool_message(self, content: str) -> Message:
        """Create a tool result message.
        
        Args:
            content: Tool result content
            
        Returns:
            Tool message
        """
        return Message(role="tool", content=content)


class LLMAdapterFactory:
    """Factory for creating LLM adapter instances.
    
    This factory provides a centralized way to create LLM adapter instances
    based on provider name, supporting the open-closed principle.
    """
    
    _adapter_classes: Dict[str, type] = {}
    
    @classmethod
    def register_adapter(cls, provider_name: str, adapter_class: type) -> None:
        """Register an LLM adapter class.
        
        Args:
            provider_name: Name of the LLM provider
            adapter_class: Adapter class that implements LLMAdapterInterface
            
        Raises:
            ValidationError: If adapter_class doesn't implement LLMAdapterInterface
        """
        from ..exceptions import ValidationError
        
        if not issubclass(adapter_class, LLMAdapterInterface):
            raise ValidationError(
                f"Adapter class must implement LLMAdapterInterface, got {adapter_class.__name__}"
            )
        
        cls._adapter_classes[provider_name.lower()] = adapter_class
    
    @classmethod
    def create_adapter(
        self,
        provider_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "default",
        **kwargs
    ) -> LLMAdapterInterface:
        """Create an LLM adapter instance.
        
        Args:
            provider_name: Name of the LLM provider
            api_key: API key for the service
            base_url: Base URL for the API
            model: Model name to use
            **kwargs: Additional provider-specific configuration
            
        Returns:
            LLM adapter instance
            
        Raises:
            ValidationError: If provider is not supported
        """
        from ..exceptions import ValidationError
        
        provider_key = provider_name.lower()
        
        if provider_key not in cls._adapter_classes:
            raise ValidationError(
                f"Unsupported LLM provider: {provider_name}",
                expected_type=f"one of {list(cls._adapter_classes.keys())}",
                actual_value=provider_name
            )
        
        adapter_class = cls._adapter_classes[provider_key]
        
        try:
            return adapter_class(
                api_key=api_key,
                base_url=base_url,
                model=model,
                **kwargs
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to create {provider_name} adapter: {e}",
                cause=e
            )
    
    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported LLM providers.
        
        Returns:
            List of supported provider names
        """
        return list(cls._adapter_classes.keys())
    
    @classmethod
    def is_provider_supported(cls, provider_name: str) -> bool:
        """Check if an LLM provider is supported.
        
        Args:
            provider_name: Provider name to check
            
        Returns:
            True if supported, False otherwise
        """
        return provider_name.lower() in cls._adapter_classes