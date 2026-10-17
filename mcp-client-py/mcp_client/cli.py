"""Command-line interface for MCP Client."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click

from .client import MCPClient
from .config.manager import ConfigManager
from .exceptions import MCPClientError


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """MCP Client - Connect to Model Context Protocol servers."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config or 'mcp_config.json'
    ctx.obj['verbose'] = verbose


@cli.command()
@click.pass_context
def list_servers(ctx):
    """List configured servers."""
    try:
        config_path = ctx.obj['config_path']
        config = ConfigManager.load_config(config_path)
        
        click.echo("Configured servers:")
        for name, server_config in config.servers.items():
            status = "disabled" if server_config.disabled else "enabled"
            click.echo(f"  {name}: {server_config.transport} ({status})")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def list_tools(ctx):
    """List available tools from connected servers."""
    async def _list_tools():
        try:
            config_path = ctx.obj['config_path']
            client = MCPClient.from_config_file(config_path)
            
            async with client:
                tools = client.get_tools()
                
                if not tools:
                    click.echo("No tools available")
                    return
                
                click.echo("Available tools:")
                for tool in tools:
                    click.echo(f"  {tool.name} (from {tool.server_name})")
                    click.echo(f"    {tool.description}")
                    
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_list_tools())


def _render_content_item(item: Any) -> str:
    """Render one tool-result content item for terminal output.

    mcp 1.x returns plain dicts, mcp 2.x returns pydantic content objects, so
    both shapes have to be handled or ``json.dumps`` raises TypeError.
    """
    if isinstance(item, dict):
        if item.get("type") == "text":
            return str(item.get("text", ""))
        return json.dumps(item, indent=2, ensure_ascii=False, default=str)

    if getattr(item, "type", None) == "text" and hasattr(item, "text"):
        return str(item.text)

    if hasattr(item, "model_dump"):
        return json.dumps(item.model_dump(), indent=2, ensure_ascii=False, default=str)

    return str(item)


@cli.command()
@click.argument('tool_name')
@click.argument('arguments', required=False)
@click.pass_context
def call_tool(ctx, tool_name: str, arguments: Optional[str]):
    """Call a tool with optional JSON arguments."""
    async def _call_tool():
        try:
            config_path = ctx.obj['config_path']
            client = MCPClient.from_config_file(config_path)
            
            # Parse arguments
            tool_args = {}
            if arguments:
                try:
                    tool_args = json.loads(arguments)
                except json.JSONDecodeError as e:
                    click.echo(f"Invalid JSON arguments: {e}", err=True)
                    sys.exit(1)
            
            async with client:
                if not client.has_tool(tool_name):
                    click.echo(f"Tool '{tool_name}' not found", err=True)
                    available_tools = client.get_tool_names()
                    if available_tools:
                        click.echo(f"Available tools: {', '.join(available_tools)}")
                    sys.exit(1)
                
                result = await client.call_tool(tool_name, tool_args)
                
                click.echo(f"Tool '{tool_name}' executed successfully:")
                if result.content:
                    for item in result.content:
                        click.echo(_render_content_item(item))
                            
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_call_tool())


@cli.command()
@click.option('--stream', is_flag=True, help='Stream the response')
@click.pass_context
def chat(ctx, stream: bool):
    """Interactive chat with LLM integration."""
    async def _chat():
        try:
            config_path = ctx.obj['config_path']
            client = MCPClient.from_config_file(config_path)
            
            if not client.has_llm_integration():
                click.echo("LLM integration not configured. Please set llm_api_key in config.", err=True)
                sys.exit(1)
            
            async with client:
                click.echo("MCP Chat started. Type 'quit' to exit.")
                click.echo(f"Connected to {len(client.get_connected_servers())} servers")
                click.echo(f"Available tools: {len(client.get_tools())}")
                click.echo()
                
                while True:
                    try:
                        message = input("You: ").strip()
                        if message.lower() in ['quit', 'exit', 'q']:
                            break
                        
                        if not message:
                            continue
                        
                        if stream:
                            click.echo("Assistant: ", nl=False)
                            chunks = await client.chat(message, stream=True)
                            for chunk in chunks:
                                if chunk.content:
                                    click.echo(chunk.content, nl=False)
                            click.echo()  # New line after streaming
                        else:
                            response = await client.chat(message, stream=False)
                            click.echo(f"Assistant: {response.content}")
                        
                        click.echo()
                        
                    except KeyboardInterrupt:
                        break
                    except EOFError:
                        break
                
                click.echo("Chat ended.")
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_chat())


@cli.command()
@click.pass_context
def status(ctx):
    """Show client status and statistics."""
    async def _status():
        try:
            config_path = ctx.obj['config_path']
            client = MCPClient.from_config_file(config_path)
            
            async with client:
                stats = client.get_client_stats()
                
                click.echo("MCP Client Status:")
                click.echo(f"  Connected: {stats['is_connected']}")
                click.echo(f"  Servers: {stats['connection_count']}")
                click.echo(f"  Tools: {stats['tool_statistics']['total_tools']}")
                click.echo(f"  LLM Integration: {stats['llm_adapter']['available']}")
                
                if stats['llm_adapter']['available']:
                    click.echo(f"    Provider: {stats['llm_adapter']['provider']}")
                    click.echo(f"    Model: {stats['llm_adapter']['model']}")
                
                click.echo("\nConnected servers:")
                for server_name in stats['connected_servers']:
                    server_info = client.get_server_info(server_name)
                    if server_info:
                        click.echo(f"  {server_name}: {server_info['tool_count']} tools")
                        
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_status())


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def create_config(output: Optional[str]):
    """Create a sample configuration file."""
    try:
        config_data = ConfigManager.create_default_config()
        
        output_path = Path(output) if output else Path('mcp_config.json')
        
        with open(output_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        click.echo(f"Sample configuration created at {output_path}")
        click.echo("Edit the file to configure your MCP servers.")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except MCPClientError as e:
        click.echo(f"MCP Client Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()