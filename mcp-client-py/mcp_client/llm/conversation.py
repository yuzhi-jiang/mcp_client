"""Conversation manager for MCP Client."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import ChatResponse, LLMAdapterInterface, StreamingChatResponse
from ..config.models import Message, Tool, ToolCall, ToolResult
from ..exceptions import ValidationError
from ..tools.manager import ToolManager


logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation state and tool integration with LLMs.
    
    This class handles conversation history, tool call execution,
    and integration between LLMs and MCP tools.
    """
    
    def __init__(
        self,
        llm_adapter: LLMAdapterInterface,
        tool_manager: ToolManager,
        system_prompt: Optional[str] = None,
        max_history_length: int = 100
    ) -> None:
        """Initialize conversation manager.
        
        Args:
            llm_adapter: LLM adapter instance
            tool_manager: Tool manager instance
            system_prompt: Optional system prompt
            max_history_length: Maximum number of messages to keep in history
        """
        self.llm_adapter = llm_adapter
        self.tool_manager = tool_manager
        self.max_history_length = max_history_length
        
        # Initialize conversation history
        self.messages: List[Message] = []
        if system_prompt:
            self.messages.append(Message(role="system", content=system_prompt))
        
        # Conversation metadata
        self.conversation_id: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
    
    async def send_message(
        self,
        content: str,
        execute_tools: bool = True,
        stream: bool = False,
        **llm_kwargs
    ) -> Union[ChatResponse, List[StreamingChatResponse]]:
        """Send a message and get response with optional tool execution.
        
        Args:
            content: User message content
            execute_tools: Whether to execute tool calls automatically
            stream: Whether to stream the response
            **llm_kwargs: Additional arguments for LLM completion
            
        Returns:
            ChatResponse for non-streaming, list of chunks for streaming
        """
        # Add user message to history
        user_message = Message(role="user", content=content)
        self.add_message(user_message)
        
        # Get available tools
        tools = self.tool_manager.get_tools() if execute_tools else None
        
        try:
            if stream:
                return await self._handle_streaming_conversation(tools, **llm_kwargs)
            else:
                return await self._handle_non_streaming_conversation(tools, execute_tools, **llm_kwargs)
                
        except Exception as e:
            logger.error(f"Error in conversation: {e}")
            raise
    
    async def _handle_non_streaming_conversation(
        self,
        tools: Optional[List[Tool]],
        execute_tools: bool,
        **llm_kwargs
    ) -> ChatResponse:
        """Handle non-streaming conversation with tool execution.
        
        Args:
            tools: Available tools
            execute_tools: Whether to execute tools
            **llm_kwargs: LLM completion arguments
            
        Returns:
            Final chat response after tool execution
        """
        max_tool_iterations = 5  # Prevent infinite tool calling loops
        iteration = 0
        
        while iteration < max_tool_iterations:
            # Get LLM response
            response = await self.llm_adapter.chat_completion(
                messages=self.messages,
                tools=tools,
                stream=False,
                **llm_kwargs
            )
            
            # Add assistant message to history
            assistant_message = Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls
            )
            self.add_message(assistant_message)
            
            # Execute tool calls if present and enabled
            if execute_tools and response.has_tool_calls():
                await self._execute_tool_calls(response.tool_calls)
                iteration += 1
                continue  # Get another LLM response after tool execution
            
            # No tool calls or tool execution disabled
            return response
        
        logger.warning(f"Reached maximum tool iterations ({max_tool_iterations})")
        return response
    
    async def _handle_streaming_conversation(
        self,
        tools: Optional[List[Tool]],
        **llm_kwargs
    ) -> List[StreamingChatResponse]:
        """Handle streaming conversation.
        
        Note: Tool execution is not supported in streaming mode.
        The response will include tool calls but they won't be executed automatically.
        
        Args:
            tools: Available tools
            **llm_kwargs: LLM completion arguments
            
        Returns:
            List of streaming response chunks
        """
        chunks = []
        accumulated_content = ""
        accumulated_tool_calls = []
        
        async for chunk in await self.llm_adapter.chat_completion(
            messages=self.messages,
            tools=tools,
            stream=True,
            **llm_kwargs
        ):
            chunks.append(chunk)
            
            # Accumulate content and tool calls
            if chunk.content:
                accumulated_content += chunk.content
            
            if chunk.tool_calls:
                # Adapters may resend the full merged set on every chunk; merge
                # by tool-call id so partial and complete payloads both work.
                by_id = {tc.id: tc for tc in accumulated_tool_calls}
                for tc in chunk.tool_calls:
                    by_id[tc.id] = tc
                accumulated_tool_calls = list(by_id.values())
            
            # If this is the final chunk, add to conversation history
            if chunk.is_complete:
                assistant_message = Message(
                    role="assistant",
                    content=accumulated_content,
                    tool_calls=accumulated_tool_calls if accumulated_tool_calls else None
                )
                self.add_message(assistant_message)
                break
        
        return chunks
    
    async def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> None:
        """Execute tool calls and add results to conversation.
        
        Args:
            tool_calls: List of tool calls to execute
        """
        for tool_call in tool_calls:
            try:
                logger.info(f"Executing tool call: {tool_call.name}")
                
                # Execute the tool
                result = await self.tool_manager.execute_tool(
                    tool_call.name,
                    tool_call.arguments
                )
                
                # Format result for conversation
                result_content = self._format_tool_result(tool_call, result)
                
                # Add tool result message to history
                tool_message = Message(role="tool", content=result_content)
                self.add_message(tool_message)
                
                logger.info(f"Tool call {tool_call.name} completed successfully")
                
            except Exception as e:
                logger.error(f"Tool call {tool_call.name} failed: {e}")
                
                # Add error message to conversation
                error_content = self._format_tool_error(tool_call, e)
                error_message = Message(role="tool", content=error_content)
                self.add_message(error_message)
    
    def _format_tool_result(self, tool_call: ToolCall, result: ToolResult) -> str:
        """Format tool result for conversation.
        
        Args:
            tool_call: The tool call that was executed
            result: The tool execution result
            
        Returns:
            Formatted result string
        """
        if result.is_error:
            return f"Tool '{tool_call.name}' returned an error: {result.error_message or 'Unknown error'}"
        
        # Format successful result
        if result.content:
            try:
                # Try to extract text content from result
                text_parts = []
                for item in result.content:
                    if isinstance(item, dict):
                        if item.get("type") == "text" and "text" in item:
                            text_parts.append(item["text"])
                        elif "content" in item:
                            text_parts.append(str(item["content"]))
                        else:
                            text_parts.append(json.dumps(item, indent=2))
                    else:
                        text_parts.append(str(item))
                
                return "\n".join(text_parts) if text_parts else "Tool executed successfully (no output)"
                
            except Exception as e:
                logger.warning(f"Failed to format tool result: {e}")
                return f"Tool '{tool_call.name}' executed successfully but result formatting failed"
        
        return f"Tool '{tool_call.name}' executed successfully (no output)"
    
    def _format_tool_error(self, tool_call: ToolCall, error: Exception) -> str:
        """Format tool error for conversation.
        
        Args:
            tool_call: The tool call that failed
            error: The error that occurred
            
        Returns:
            Formatted error string
        """
        return f"Tool '{tool_call.name}' failed with error: {str(error)}"
    
    def add_message(self, message: Message) -> None:
        """Add a message to the conversation history.
        
        Args:
            message: Message to add
        """
        self.messages.append(message)
        
        # Trim history if it exceeds maximum length
        if len(self.messages) > self.max_history_length:
            # Keep system message if present
            system_messages = [msg for msg in self.messages if msg.role == "system"]
            other_messages = [msg for msg in self.messages if msg.role != "system"]
            
            # Keep the most recent messages
            keep_count = self.max_history_length - len(system_messages)
            trimmed_messages = other_messages[-keep_count:] if keep_count > 0 else []
            
            self.messages = system_messages + trimmed_messages
            
            logger.info(f"Trimmed conversation history to {len(self.messages)} messages")
    
    def get_messages(self) -> List[Message]:
        """Get conversation messages.
        
        Returns:
            List of conversation messages
        """
        return self.messages.copy()
    
    def clear_history(self, keep_system: bool = True) -> None:
        """Clear conversation history.
        
        Args:
            keep_system: Whether to keep system messages
        """
        if keep_system:
            system_messages = [msg for msg in self.messages if msg.role == "system"]
            self.messages = system_messages
        else:
            self.messages = []
        
        logger.info("Conversation history cleared")
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt.
        
        Args:
            prompt: New system prompt
        """
        # Remove existing system messages
        self.messages = [msg for msg in self.messages if msg.role != "system"]
        
        # Add new system message at the beginning
        system_message = Message(role="system", content=prompt)
        self.messages.insert(0, system_message)
        
        logger.info("System prompt updated")
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics.
        
        Returns:
            Dictionary with conversation statistics
        """
        message_counts = {}
        total_content_length = 0
        tool_calls_count = 0
        
        for message in self.messages:
            role = message.role
            message_counts[role] = message_counts.get(role, 0) + 1
            total_content_length += len(message.content)
            
            if message.tool_calls:
                tool_calls_count += len(message.tool_calls)
        
        return {
            "total_messages": len(self.messages),
            "message_counts": message_counts,
            "total_content_length": total_content_length,
            "tool_calls_count": tool_calls_count,
            "estimated_tokens": self.llm_adapter.estimate_tokens(
                "\n".join(msg.content for msg in self.messages)
            )
        }
    
    def save_conversation(self, file_path: Union[str, Path]) -> None:
        """Save conversation to a JSON file.
        
        Args:
            file_path: Path to save the conversation
        """
        file_path = Path(file_path)
        
        # Convert messages to serializable format
        messages_data = []
        for message in self.messages:
            message_data = {
                "role": message.role,
                "content": message.content
            }
            
            if message.tool_calls:
                message_data["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments
                    }
                    for tc in message.tool_calls
                ]
            
            messages_data.append(message_data)
        
        # Create conversation data
        conversation_data = {
            "conversation_id": self.conversation_id,
            "messages": messages_data,
            "metadata": self.metadata,
            "stats": self.get_conversation_stats()
        }
        
        # Save to file
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Conversation saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            raise
    
    def load_conversation(self, file_path: Union[str, Path]) -> None:
        """Load conversation from a JSON file.
        
        Args:
            file_path: Path to load the conversation from
        """
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                conversation_data = json.load(f)
            
            # Load conversation metadata
            self.conversation_id = conversation_data.get("conversation_id")
            self.metadata = conversation_data.get("metadata", {})
            
            # Load messages
            self.messages = []
            for message_data in conversation_data.get("messages", []):
                tool_calls = None
                if "tool_calls" in message_data:
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"]
                        )
                        for tc in message_data["tool_calls"]
                    ]
                
                message = Message(
                    role=message_data["role"],
                    content=message_data["content"],
                    tool_calls=tool_calls
                )
                self.messages.append(message)
            
            logger.info(f"Conversation loaded from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            raise ValidationError(f"Failed to load conversation from {file_path}: {e}", cause=e)