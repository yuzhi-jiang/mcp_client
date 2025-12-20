"""Logging configuration for MCP Client."""

import logging
import sys
from typing import Optional

import structlog


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    include_timestamp: bool = True,
    include_caller: bool = False
) -> None:
    """Configure structured logging for MCP Client.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ("json" or "console")
        include_timestamp: Whether to include timestamps
        include_caller: Whether to include caller information
    """
    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout
    )
    
    # Configure processors based on format type
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
    ]
    
    if include_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))
    
    if include_caller:
        processors.append(structlog.processors.StackInfoRenderer())
        processors.append(structlog.processors.format_exc_info)
    
    processors.append(structlog.processors.UnicodeDecoder())
    
    # Add final formatter based on format type
    if format_type.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (defaults to caller's module)
        
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def set_log_level(level: str) -> None:
    """Set the log level for all loggers.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)


def add_context(**kwargs) -> None:
    """Add context to all subsequent log messages in the current thread.
    
    Args:
        **kwargs: Context key-value pairs
    """
    logger = structlog.get_logger()
    logger = logger.bind(**kwargs)
    # Note: This doesn't persist across function calls in structlog
    # Context should be added per-logger instance or per-call