
import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, cast
from types import TracebackType

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAI

# Constants
DEFAULT_CONFIG_PATH = "mcp_config.json"
DEFAULT_ENCODING = "utf-8"
DEFAULT_ENCODING_ERROR_HANDLER = "strict"
DEFAULT_HTTP_TIMEOUT = 5
DEFAULT_SSE_READ_TIMEOUT = 60 * 5

class ConfigManager:
    """Manages loading and validating MCP server configurations from JSON files."""
    
    @staticmethod
    def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
        """Load MCP server configurations from a JSON file.
        
        Args:
            config_path: Path to the configuration JSON file
            
        Returns:
            Dictionary containing server configurations
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in configuration file: {config_path}")

    @staticmethod
    def get_server_configs(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract server configurations from the loaded config.
        
        Args:
            config: Loaded configuration dictionary
            
        Returns:
            Dictionary mapping server names to their configurations
        """
        if "mcpServers" not in config:
            raise ValueError("Configuration must contain 'mcpServers' key")
            
        return config["mcpServers"]


class MultiMCPClient:
    """Client for connecting to multiple MCP servers with configurations loaded from a JSON file."""
    
    def __init__(self, 
                 config_path: str = DEFAULT_CONFIG_PATH,
                 llm_api_key: Optional[str] = None,
                 llm_base_url: Optional[str] = "https://api.deepseek.com",
                 llm_model: str = "deepseek-chat"):
        """Initialize a MultiMCPClient with configurations from a JSON file.
        
        Args:
            config_path: Path to the configuration JSON file
            llm_api_key: API key for the LLM service
            llm_base_url: Base URL for the LLM service
            llm_model: Model name for the LLM service
        """
        self.config_path = config_path
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}
        self.server_name_to_tools: Dict[str, List[BaseTool]] = {}
        
        # LLM client setup — never hardcode credentials in source.
        resolved_api_key = llm_api_key or os.getenv("DEEPSEEK_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "Missing API key: pass llm_api_key or set the DEEPSEEK_API_KEY environment variable"
            )
        self.llm_client = OpenAI(
            api_key=resolved_api_key,
            base_url=llm_base_url,
        )
        self.llm_model = llm_model

    async def initialize_from_config(self) -> None:
        """Initialize connections to all servers defined in the configuration file."""
        config = ConfigManager.load_config(self.config_path)
        server_configs = ConfigManager.get_server_configs(config)
        
        for server_name, server_config in server_configs.items():
            # Determine transport type (default to stdio if not specified)
            transport_type = server_config.get("transport", "stdio")
            
            if transport_type == "stdio":
                if "command" not in server_config or "args" not in server_config:
                    print(f"Warning: Skipping server '{server_name}' due to missing required parameters")
                    continue
                    
                await self.connect_to_server_via_stdio(
                    server_name,
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config.get("env"),
                    encoding=server_config.get("encoding", DEFAULT_ENCODING),
                    encoding_error_handler=server_config.get("encoding_error_handler", DEFAULT_ENCODING_ERROR_HANDLER),
                    session_kwargs=server_config.get("session_kwargs"),
                )
            elif transport_type == "sse":
                if "url" not in server_config:
                    print(f"Warning: Skipping server '{server_name}' due to missing required parameters")
                    continue
                    
                await self.connect_to_server_via_sse(
                    server_name,
                    url=server_config["url"],
                    headers=server_config.get("headers"),
                    timeout=server_config.get("timeout", DEFAULT_HTTP_TIMEOUT),
                    sse_read_timeout=server_config.get("sse_read_timeout", DEFAULT_SSE_READ_TIMEOUT),
                    session_kwargs=server_config.get("session_kwargs"),
                )
            else:
                print(f"Warning: Skipping server '{server_name}' due to unsupported transport type: {transport_type}")


    async def tool_calls(self,tool_calls,setp_callback):
        final_text=[]
        messages=[]
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                # 尝试解析参数
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                # 如果解析失败，提供错误信息
                error_msg = f"无效的工具参数格式: {tool_call.function.arguments}"
                final_text.append(f"[错误: {error_msg}]")
                messages.append({
                    "role": "user",
                    "content": f"错误: {error_msg}"
                })
                continue
                
            setp_callback(f"Tool call: {tool_name} with args {tool_args}")
            # Find which server has this tool
            target_server = None
            for srv_name, srv_tools in self.server_name_to_tools.items():
                if any(t.name == tool_name for t in srv_tools):
                    target_server = srv_name
                    break
                    
            if not target_server:
                error_msg = f"Tool '{tool_name}' not found in any connected server"
                final_text.append(f"[Error: {error_msg}]")
                messages.append({
                    "role": "user",
                    "content": f"Error: {error_msg}"
                })
                continue
            
            # Execute tool call
            result = await self.call_tool(target_server, tool_name, tool_args)
            tool_call_text = f"Calling tool {tool_name} on server {target_server}"
            final_text.append(tool_call_text)
            setp_callback(f"Tool result: {result}")
            
            # Add the tool call as a proper message
            messages.append({
                "role": "assistant",
                "content": f"<tool_use><n>{tool_name}</n><arguments>{tool_args}</arguments></tool_use>"
            })
            
            # Add the tool result as a proper message
            messages.append({
                "role": "user",
                "content": json.dumps([
                    {
                        "text": f"Here is the result of tool call {tool_name}",
                        "type": "text"
                    },
                    {
                        "type": "text",
                        "content": result.content[0].text
                    }
                ])
            })
        
        # Return both the messages and final_text
        return final_text, messages

    async def connect_to_server_via_stdio(
        self,
        server_name: str,
        *,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        encoding: str = DEFAULT_ENCODING,
        encoding_error_handler: Literal["strict", "ignore", "replace"] = DEFAULT_ENCODING_ERROR_HANDLER,
        session_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Connect to a specific MCP server using stdio.
        
        Args:
            server_name: Name to identify this server connection
            command: Command to execute
            args: Arguments for the command
            env: Environment variables for the command
            encoding: Character encoding
            encoding_error_handler: How to handle encoding errors
            session_kwargs: Additional keyword arguments to pass to the ClientSession
        """
        # Ensure PATH environment variable is set
        env = env or {}
        if "PATH" not in env:
            env["PATH"] = os.environ.get("PATH", "")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
            encoding=encoding,
            encoding_error_handler=encoding_error_handler,
        )

        # Create and store the connection
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        read, write = stdio_transport
        session_kwargs = session_kwargs or {}
        session = cast(
            ClientSession,
            await self.exit_stack.enter_async_context(ClientSession(read, write, **session_kwargs)),
        )

        await self._initialize_session_and_load_tools(server_name, session)
        print(f"Connected to server '{server_name}' via stdio")

    async def connect_to_server_via_sse(
        self,
        server_name: str,
        *,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        sse_read_timeout: float = DEFAULT_SSE_READ_TIMEOUT,
        session_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Connect to a specific MCP server using SSE.
        
        Args:
            server_name: Name to identify this server connection
            url: URL of the SSE server
            headers: HTTP headers to send to the SSE endpoint
            timeout: HTTP timeout
            sse_read_timeout: SSE read timeout
            session_kwargs: Additional keyword arguments to pass to the ClientSession
        """
        # Create and store the connection
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(url, headers, timeout, sse_read_timeout)
        )
        read, write = sse_transport
        session_kwargs = session_kwargs or {}
        session = cast(
            ClientSession,
            await self.exit_stack.enter_async_context(ClientSession(read, write, **session_kwargs)),
        )

        await self._initialize_session_and_load_tools(server_name, session)
        print(f"Connected to server '{server_name}' via SSE")

    async def _initialize_session_and_load_tools(
        self, server_name: str, session: ClientSession
    ) -> None:
        """Initialize a session and load tools from it.
        
        Args:
            server_name: Name to identify this server connection
            session: The ClientSession to initialize
        """
        # Initialize the session
        await session.initialize()
        self.sessions[server_name] = session

        # Load tools from this server
        response = await session.list_tools()
        tools = response.tools
        self.server_name_to_tools[server_name] = tools
        print(f"Loaded {len(tools)} tools from server '{server_name}': {[tool.name for tool in tools]}")

    def get_tools(self, server_name: Optional[str] = None) -> List[Any]:
        """Get a list of tools from all connected servers or a specific server.
        
        Args:
            server_name: Optional name of a specific server to get tools from
            
        Returns:
            List of tools
        """
        if server_name:
            if server_name not in self.server_name_to_tools:
                raise ValueError(f"Server '{server_name}' not found")
            return self.server_name_to_tools[server_name]
        
        all_tools = []
        for server_tools in self.server_name_to_tools.values():
            all_tools.extend(server_tools)
        return all_tools

    def get_server_names(self) -> List[str]:
        """Get a list of all connected server names.
        
        Returns:
            List of server names
        """
        return list(self.sessions.keys())

    async def get_prompt(
        self, server_name: str, prompt_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> List[HumanMessage | AIMessage]:
        """Get a prompt from a given MCP server.
        
        Args:
            server_name: Name of the server to get the prompt from
            prompt_name: Name of the prompt to get
            arguments: Optional arguments to pass to the prompt
            
        Returns:
            List of messages from the prompt
        """
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' not found")
            
        session = self.sessions[server_name]
        response = await session.get_prompt(prompt_name, arguments or {})
        
        # Convert to langchain message format
        messages = []
        for msg in response.messages:
            if msg.role == "human":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "ai":
                messages.append(AIMessage(content=msg.content))
                
        return messages

    async def call_tool(self, server_name: str, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Call a tool on a specific server.
        
        Args:
            server_name: Name of the server to call the tool on
            tool_name: Name of the tool to call
            tool_args: Arguments to pass to the tool
            
        Returns:
            Result of the tool call
        """
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' not found")
            
        session = self.sessions[server_name]
        return await session.call_tool(tool_name, tool_args)

    def get_all_tools(self,server_name:str=None):
        tools = self.get_tools(server_name)
        
        # Format tools for the LLM API
        available_tools = []
        for tool in tools:
            tool_dict = {
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.inputSchema
                }
            }
            available_tools.append(tool_dict)
        return available_tools

    async def process_query(self, query: str=None, server_name: Optional[str] = None, messages: Optional[List[Dict[str, Any]]] = None,is_stream:bool=False) -> str:
        """Process a query using the LLM and available tools.
        
        Args:
            query: The user query to process
            server_name: Optional name of a specific server to use tools from
            
        Returns:
            The response from the LLM
        """
        curr_query={
            "role": "user",
            "content": query
        }
        messages = [] if messages is None else messages
        if not is_stream:
            messages.append(curr_query)
        
        # Get tools from specified server or all servers
        # Format tools for the LLM API
        available_tools = self.get_all_tools(server_name)
        
        use_stream=True

        # Initial LLM API call
        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            tools=available_tools,
            stream=use_stream
        )
        final_text = []

                    
        chuncks=response.choices if not use_stream else response
        use_tools = False
        tool_calls = []
        temp_msg=[]
        temp_msg_format_tool=""
        
        # For collecting tool calls in streaming mode
        collected_tool_calls=[]
        current_tool_call = None
        
        for chunk in chuncks:
            choice = chunk.choices[0]
            content = choice.message if not use_stream else choice.delta.content
            if use_stream and content:
                temp_msg_format_tool+=content
                temp_msg.append(content)
                print(content, end="")
                # 检查temp_msg中是否包含tool_use标签
                tool_use_start = ''.join(temp_msg_format_tool).find('<tool_use>')
                if tool_use_start != -1:
                    # 提取完整的tool_use内容
                    tool_use_content = ''.join(temp_msg_format_tool)[tool_use_start:]
                    tool_use_end = tool_use_content.find('</tool_use>')
                    if tool_use_end != -1:
                        temp_msg_format_tool=""
                        tool_use_content = tool_use_content[:tool_use_end + len('</tool_use>')]
                        
                        # 解析tool name
                        name_start = tool_use_content.find('<n>') + len('<n>')
                        name_end = tool_use_content.find('</n>')
                        tool_name = tool_use_content[name_start:name_end]
                        
                        # 解析arguments
                        args_start = tool_use_content.find('<arguments>') + len('<arguments>')
                        args_end = tool_use_content.find('</arguments>')
                        tool_args_str = tool_use_content[args_start:args_end]
                        
                        # 确保tool_args是有效的JSON
                        try:
                            # 尝试解析JSON
                            tool_args = json.loads(tool_args_str)
                            # 如果成功解析，将其转回字符串以保持一致性
                            tool_args = json.dumps(tool_args)
                        except json.JSONDecodeError:
                            # 如果不是有效的JSON，则保持原样
                            # 尝试将单引号替换为双引号
                            tool_args_str = tool_args_str.replace("'", '"')
                            # 再次尝试解析JSON
                            try:
                                tool_args = json.loads(tool_args_str)
                                # 如果成功解析，将其转回字符串以保持一致性
                                tool_args = json.dumps(tool_args)
                            except json.JSONDecodeError:
                                # 如果仍然不是有效的JSON，则使用原始字符串
                                tool_args = tool_args_str
                        
                        # 创建tool call结构
                        from types import SimpleNamespace
                        function = SimpleNamespace(name=tool_name, arguments=tool_args)
                        tool_call = SimpleNamespace(
                            id=f"call_{len(tool_calls)}",
                            function=function,
                            type="function"
                        )
                        print('发现了一个tool call')
                        
                        tool_calls.append(tool_call)
                        use_tools = True
                
                
            if not use_stream and hasattr(content, 'tool_calls') and content.tool_calls:
                use_tools = True
                tool_calls = content.tool_calls
            elif use_stream:
                # Handle tool calls in streaming mode
                if choice.delta.tool_calls:
                    use_tools = True
                    
                    # Process each tool call in the current chunk
                    for tc_index, tc in enumerate(choice.delta.tool_calls):
                        # If this is a new tool call
                        # print(tc)
                        
                        if tc.index+1 > len(collected_tool_calls):
                            print(f'new toll call {tc.id}')
                            collected_tool_calls.append({
                                'id': tc.id,
                                'function': {
                                    'name': tc.function.name if hasattr(tc.function, 'name') and tc.function.name else "",
                                    'arguments': tc.function.arguments if hasattr(tc.function, 'arguments') and tc.function.arguments else ""
                                },
                                'type': tc.type if hasattr(tc, 'type') and tc.type else "function"
                            })
                        else:
                            # Update existing tool call
                            if hasattr(tc, 'id') and tc.id:
                                collected_tool_calls[tc.index]['id'] = tc.id
                            if hasattr(tc.function, 'name') and tc.function.name:
                                collected_tool_calls[tc.index]['function']['name'] = tc.function.name
                            if hasattr(tc.function, 'arguments') and tc.function.arguments:
                                collected_tool_calls[tc.index]['function']['arguments'] += tc.function.arguments
                            if hasattr(tc, 'type') and tc.type:
                                collected_tool_calls[tc.index]['type'] = tc.type
                
                # When we get the finish_reason of tool_calls, convert collected tool calls to the format expected by tool_calls method
                if choice.finish_reason == 'tool_calls':
                    use_tools = True
                    # Convert collected tool calls to the format expected by tool_calls method
                    from types import SimpleNamespace
                    tool_calls = []
                    for tc in collected_tool_calls:
                        function = SimpleNamespace(name=tc['function']['name'], arguments=tc['function']['arguments'])
                        tool_calls.append(SimpleNamespace(id=tc['id'], function=function, type=tc['type']))
                    
                    print(f"Collected tool calls: {tool_calls}")
            
            if use_stream and choice.finish_reason == 'stop':
                final_text.extend(temp_msg)
        if not use_tools:
            messages.append({
                "role": "assistant",
                "content": "".join(final_text)
            })
        elif tool_calls:
            if use_tools and tool_calls:
                # Note: tool_calls method now returns final_text, messages (in that order)
                call_texts, call_res = await self.tool_calls(tool_calls, setp_callback=(lambda msg: print(msg)))
                final_text.extend(call_texts)
                messages.extend(call_res)
                # Process the next query with the updated messages
                sub_final_text, updated_messages = await self.process_query(None, server_name, messages, is_stream=True)
                
                return "".join(final_text)+(sub_final_text), updated_messages
        print("final_text:", "".join(final_text))
        return "".join(final_text), messages

    async def chat_loop(self) -> None:
        """Run an interactive chat loop."""
        print("\nMulti-MCP Client Started!")
        print(f"Connected to {len(self.sessions)} servers: {', '.join(self.get_server_names())}")
        print("Type your queries or 'quit' to exit.")
        # 读取text message_file = "chat_history.txt"
        message_file = "chat_history.txt"
        if os.path.exists(message_file):
            with open(message_file, 'r', encoding='utf-8') as file:
                message = json.load(file)
        else:
            message=[
                {
                    "role": "system",
                    "content": """You are a helpful assistant, you have some built-in tools, you can call them, if the user's question involves tools, you can call the tools to help.
                        你有一些内置工具，你可以调用它们，如果用户的问题涉及工具，你可以调用工具来帮助。
                        当你使用 interact_with_screen 工具时，action:tap是选择指定的元素地址，params:{"x":100,"y":200}是点击屏幕上的坐标，action:text 是输入文本，params:{"text":"hello"}是输入文本。
                    
                    """
                }
            ]
        while True:
            try:
                query = input("\nQuery: ").strip()
                if not query:
                    continue
                if query.lower() == 'quit':
                    break
                if query.lower() == 'new':
                    message=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant, you have some built-in tools, you can call them, if the user's question involves tools, you can call the tools to help"
                        }
                    ]
                    print("start a new chat")
                    
                    query=input("\nQuery: ").strip()
                # Check for server-specific queries
                parts = query.split("@", 1)
                if len(parts) > 1 and parts[0].strip() in self.sessions:
                    server_name = parts[0].strip()
                    actual_query = parts[1].strip()
                    print(f"Using server: {server_name}")
                    response, old_messages = await self.process_query(actual_query, server_name,messages=message)
                    message=old_messages
                    # 将消息持久化到文本文件
                    
                    try:
                        # 检查文件是否存在,不存在则创建
                        if not os.path.exists(message_file):
                            with open(message_file, "w", encoding="utf-8") as f:
                                f.write("[]")
                                
                        # 保存更新后的消息记录
                        with open(message_file, "w", encoding="utf-8") as f:
                            json.dump(message, f, ensure_ascii=False, indent=2)
                            
                    except Exception as e:
                        print(f"保存消息记录失败: {str(e)}")

                else:
                    response, old_messages = await self.process_query(query=query,messages=message)
                    message=old_messages

                                        # 将消息持久化到文本文件
                    
                    try:
                        # 检查文件是否存在,不存在则创建
                        if not os.path.exists(message_file):
                            with open(message_file, "w", encoding="utf-8") as f:
                                f.write("[]")
                                
                        # 保存更新后的消息记录
                        with open(message_file, "w", encoding="utf-8") as f:
                            json.dump(message, f, ensure_ascii=False, indent=2)
                            
                    except Exception as e:
                        print(f"保存消息记录失败: {str(e)}")
                print(response)
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.exit_stack.aclose()
        
    async def __aenter__(self) -> "MultiMCPClient":
        """Async context manager entry."""
        try:
            await self.initialize_from_config()
            return self
        except Exception:
            await self.exit_stack.aclose()
            raise

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Async context manager exit."""
        await self.exit_stack.aclose()


async def main() -> None:
    """Main entry point for the Multi-MCP Client."""
    client = MultiMCPClient()
    try:
        async with client:
            await client.chat_loop()
    except Exception as e:
        print(f"Fatal error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
