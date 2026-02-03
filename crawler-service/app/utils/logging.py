"""
Structured logging utility for the Elastic Crawler Service.

Provides consistent, configurable logging across all modules with:
- Structured output with timestamps, levels, and context
- Configurable log level via LOG_LEVEL env var
- Color-coded output for development
- JSON output option for production

Usage:
    from utils.logging import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing started", domain="example.com", phase="investigation")
    logger.debug("Fetched page", url="https://example.com", status=200)
    logger.warning("Rate limited", retry_after=60)
    logger.error("Failed to fetch", url="https://example.com", error=str(e))

Environment Variables:
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO
    LOG_FORMAT: Output format ("pretty" or "json") - default: pretty
"""

import logging
import os
import sys
import json
from datetime import datetime
from typing import Any, Optional


# Configuration from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "pretty").lower()

# ANSI color codes for pretty output
COLORS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",    # Red
    "RESET": "\033[0m",     # Reset
    "DIM": "\033[2m",       # Dim
    "BOLD": "\033[1m",      # Bold
}


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured log messages.
    
    Supports two formats:
    - pretty: Human-readable colored output for development
    - json: Machine-readable JSON for production/log aggregation
    """
    
    def __init__(self, format_type: str = "pretty"):
        super().__init__()
        self.format_type = format_type
    
    def format(self, record: logging.LogRecord) -> str:
        # Get timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        
        # Extract extra context from record
        extra = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName",
            }:
                extra[key] = value
        
        # Format message with args if present
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        
        if self.format_type == "json":
            return self._format_json(timestamp, record, message, extra)
        else:
            return self._format_pretty(timestamp, record, message, extra)
    
    def _format_pretty(
        self,
        timestamp: str,
        record: logging.LogRecord,
        message: str,
        extra: dict,
    ) -> str:
        """Format as human-readable colored output."""
        level = record.levelname
        level_color = COLORS.get(level, "")
        reset = COLORS["RESET"]
        dim = COLORS["DIM"]
        
        # Shorten module name for readability
        module = record.name
        if module.startswith("app."):
            module = module[4:]
        if len(module) > 25:
            module = "..." + module[-22:]
        
        # Build output
        parts = [
            f"{dim}{timestamp}{reset}",
            f"{level_color}{level:7}{reset}",
            f"{dim}[{module:25}]{reset}",
            message,
        ]
        
        # Add extra context on same line if small, otherwise new lines
        if extra:
            if len(extra) <= 3 and all(len(str(v)) < 50 for v in extra.values()):
                # Inline format for small context
                context_parts = [f"{k}={_format_value(v)}" for k, v in extra.items()]
                parts.append(f"{dim}({', '.join(context_parts)}){reset}")
            else:
                # Multi-line format for larger context
                output = " ".join(parts)
                for key, value in extra.items():
                    output += f"\n    {dim}{key}={_format_value(value)}{reset}"
                return output
        
        return " ".join(parts)
    
    def _format_json(
        self,
        timestamp: str,
        record: logging.LogRecord,
        message: str,
        extra: dict,
    ) -> str:
        """Format as JSON for production logging."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            **extra,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str)


def _format_value(value: Any) -> str:
    """Format a value for pretty printing."""
    if isinstance(value, str):
        if len(value) > 100:
            return f'"{value[:97]}..."'
        return f'"{value}"'
    elif isinstance(value, (list, tuple)):
        if len(value) > 5:
            return f"[{len(value)} items]"
        return str(value)
    elif isinstance(value, dict):
        if len(value) > 3:
            return f"{{{len(value)} keys}}"
        return str(value)
    else:
        return str(value)


class ContextLogger:
    """
    Logger wrapper that supports structured context logging.
    
    Allows passing extra context as keyword arguments:
        logger.info("Message", key1=value1, key2=value2)
    """
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
    
    def _log(self, level: int, msg: str, *args, **kwargs) -> None:
        """Log with extra context from kwargs."""
        # Separate logging kwargs from extra context
        exc_info = kwargs.pop("exc_info", None)
        stack_info = kwargs.pop("stack_info", False)
        stacklevel = kwargs.pop("stacklevel", 1)
        
        # Everything else is extra context
        extra = kwargs
        
        self._logger.log(
            level,
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel + 1,
            extra=extra,
        )
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log at DEBUG level with optional context."""
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log at INFO level with optional context."""
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log at WARNING level with optional context."""
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log at ERROR level with optional context."""
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log at ERROR level with exception info."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    @property
    def level(self) -> int:
        """Get current log level."""
        return self._logger.level
    
    def isEnabledFor(self, level: int) -> bool:
        """Check if logging is enabled for a level."""
        return self._logger.isEnabledFor(level)


# Cache for loggers
_loggers: dict[str, ContextLogger] = {}

# Root handler (configured once)
_handler_configured = False


def _configure_handler() -> None:
    """Configure the root handler once."""
    global _handler_configured
    if _handler_configured:
        return
    
    # Create handler with our formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter(LOG_FORMAT))
    
    # Configure root logger for our app
    root_logger = logging.getLogger("app")
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root_logger.addHandler(handler)
    root_logger.propagate = False
    
    # Also handle utils.* loggers
    utils_logger = logging.getLogger("utils")
    utils_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    utils_logger.addHandler(handler)
    utils_logger.propagate = False
    
    # Handle agents.* loggers
    agents_logger = logging.getLogger("agents")
    agents_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    agents_logger.addHandler(handler)
    agents_logger.propagate = False
    
    # Handle routes.* loggers
    routes_logger = logging.getLogger("routes")
    routes_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    routes_logger.addHandler(handler)
    routes_logger.propagate = False
    
    _handler_configured = True


def get_logger(name: str) -> ContextLogger:
    """
    Get a structured logger for the given module name.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        ContextLogger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info("Processing", domain="example.com")
    """
    if name in _loggers:
        return _loggers[name]
    
    _configure_handler()
    
    # Normalize name for our app structure
    # Convert "app.agents.site_investigation" -> "agents.site_investigation"
    if name.startswith("app."):
        name = name[4:]
    
    logger = logging.getLogger(name)
    context_logger = ContextLogger(logger)
    _loggers[name] = context_logger
    
    return context_logger


# Convenience function for quick timing logs
class Timer:
    """
    Context manager for timing operations.
    
    Usage:
        with Timer(logger, "fetch_pages", url_count=5):
            await fetch_pages(urls)
    """
    
    def __init__(self, logger: ContextLogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.debug(f"Starting {self.operation}", **self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type:
            self.logger.error(
                f"Failed {self.operation}",
                duration_ms=round(duration_ms, 1),
                error=str(exc_val),
                **self.context,
            )
        else:
            self.logger.info(
                f"Completed {self.operation}",
                duration_ms=round(duration_ms, 1),
                **self.context,
            )
        
        return False  # Don't suppress exceptions
