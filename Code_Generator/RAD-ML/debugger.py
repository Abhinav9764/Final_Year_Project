"""
debugger.py - Comprehensive debugging system for RAD-ML pipeline
==================================================================
Provides structured error logging, error categorization, and debugging utilities
for all agents in the pipeline.
"""

import logging
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, asdict


class ErrorCategory(Enum):
    """Error categories for classification."""
    VALIDATION_ERROR = "validation"          # Input validation failed
    NETWORK_ERROR = "network"                # API/network call failed
    PROCESSING_ERROR = "processing"          # Processing/computation failed
    RESOURCE_ERROR = "resource"              # Memory/file system/resource issue
    EXTERNAL_ERROR = "external"              # External service (SageMaker/S3) failed
    CONFIGURATION_ERROR = "configuration"    # Config/setup issue
    UNKNOWN_ERROR = "unknown"                # Unknown error type


@dataclass
class DebugEvent:
    """Structured debug event."""
    timestamp: str
    level: str          # DEBUG, INFO, WARNING, ERROR, CRITICAL
    category: str       # ErrorCategory enum value
    agent: str          # Which agent/module
    component: str      # Specific component within agent
    message: str        # Human-readable message
    error_type: Optional[str] = None    # Exception type if applicable
    context: Optional[Dict[str, Any]] = None   # Additional context
    stack_trace: Optional[str] = None   # Full stack trace for errors


class DebugLogger:
    """Comprehensive debugging logger for the pipeline."""

    def __init__(self, agent_name: str, log_dir: Optional[Path] = None):
        """Initialize debug logger for an agent.

        Parameters
        ----------
        agent_name : str
            Name of the agent using this logger
        log_dir : Path, optional
            Directory to write debug logs. Defaults to ./logs/debug
        """
        self.agent_name = agent_name
        self.log_dir = Path(log_dir or Path.cwd() / "logs" / "debug")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up standard logger
        self.logger = logging.getLogger(f"RAD-ML.{agent_name}")
        if not self.logger.handlers:
            handler = logging.FileHandler(
                self.log_dir / f"{agent_name}.log"
            )
            handler.setFormatter(logging.Formatter(
                '[%(levelname)s] %(asctime)s - %(name)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

        # Store events for structured logging
        self.events: List[DebugEvent] = []

    def _categorize_error(self, exception: Exception) -> ErrorCategory:
        """Categorize an exception."""
        exc_type = type(exception).__name__
        message = str(exception).lower()

        if exc_type == "ValueError" or "validation" in message:
            return ErrorCategory.VALIDATION_ERROR
        elif exc_type in ("ConnectionError", "TimeoutError", "HTTPError"):
            return ErrorCategory.NETWORK_ERROR
        elif "memory" in message or exc_type == "MemoryError":
            return ErrorCategory.RESOURCE_ERROR
        elif exc_type in ("FileNotFoundError", "IOError", "OSError"):
            return ErrorCategory.RESOURCE_ERROR
        elif "sagemaker" in message or "s3" in message:
            return ErrorCategory.EXTERNAL_ERROR
        elif exc_type in ("KeyError", "ConfigurationError", "ValueError"):
            return ErrorCategory.CONFIGURATION_ERROR
        else:
            return ErrorCategory.UNKNOWN_ERROR

    def debug(self, component: str, message: str, context: Optional[Dict] = None):
        """Log debug message."""
        event = DebugEvent(
            timestamp=datetime.now().isoformat(),
            level="DEBUG",
            category=ErrorCategory.UNKNOWN_ERROR.value,
            agent=self.agent_name,
            component=component,
            message=message,
            context=context,
        )
        self.events.append(event)
        self.logger.debug(f"[{component}] {message}")

    def info(self, component: str, message: str, context: Optional[Dict] = None):
        """Log info message."""
        event = DebugEvent(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            category=ErrorCategory.UNKNOWN_ERROR.value,
            agent=self.agent_name,
            component=component,
            message=message,
            context=context,
        )
        self.events.append(event)
        self.logger.info(f"[{component}] {message}")

    def warning(self, component: str, message: str, context: Optional[Dict] = None):
        """Log warning message."""
        event = DebugEvent(
            timestamp=datetime.now().isoformat(),
            level="WARNING",
            category=ErrorCategory.UNKNOWN_ERROR.value,
            agent=self.agent_name,
            component=component,
            message=message,
            context=context,
        )
        self.events.append(event)
        self.logger.warning(f"[{component}] {message}")

    def error(self, component: str, message: str, exception: Optional[Exception] = None,
              context: Optional[Dict] = None):
        """Log error with exception details."""
        category = self._categorize_error(exception) if exception else ErrorCategory.UNKNOWN_ERROR

        stack_trace = None
        error_type = None
        if exception:
            error_type = type(exception).__name__
            stack_trace = traceback.format_exc()

        event = DebugEvent(
            timestamp=datetime.now().isoformat(),
            level="ERROR",
            category=category.value,
            agent=self.agent_name,
            component=component,
            message=message,
            error_type=error_type,
            context=context,
            stack_trace=stack_trace,
        )
        self.events.append(event)

        if exception:
            self.logger.error(f"[{component}] {message}\n{stack_trace}")
        else:
            self.logger.error(f"[{component}] {message}")

    def critical(self, component: str, message: str, exception: Optional[Exception] = None,
                 context: Optional[Dict] = None):
        """Log critical error."""
        category = self._categorize_error(exception) if exception else ErrorCategory.UNKNOWN_ERROR

        stack_trace = None
        error_type = None
        if exception:
            error_type = type(exception).__name__
            stack_trace = traceback.format_exc()

        event = DebugEvent(
            timestamp=datetime.now().isoformat(),
            level="CRITICAL",
            category=category.value,
            agent=self.agent_name,
            component=component,
            message=message,
            error_type=error_type,
            context=context,
            stack_trace=stack_trace,
        )
        self.events.append(event)

        if exception:
            self.logger.critical(f"[{component}] {message}\n{stack_trace}")
        else:
            self.logger.critical(f"[{component}] {message}")

    def save_debug_report(self, filename: str = "debug_report.json"):
        """Save all debug events to JSON file."""
        report_path = self.log_dir / filename
        events_dict = [asdict(event) for event in self.events]

        with open(report_path, "w") as f:
            json.dump({
                "agent": self.agent_name,
                "generated_at": datetime.now().isoformat(),
                "event_count": len(self.events),
                "events": events_dict,
            }, f, indent=2)

        return report_path

    def get_errors(self) -> List[DebugEvent]:
        """Get all error-level events."""
        return [e for e in self.events if e.level in ("ERROR", "CRITICAL")]

    def get_warnings(self) -> List[DebugEvent]:
        """Get all warning-level events."""
        return [e for e in self.events if e.level == "WARNING"]

    def print_summary(self):
        """Print summary of debug events."""
        total = len(self.events)
        errors = len(self.get_errors())
        warnings = len(self.get_warnings())

        print(f"\nDebug Summary for {self.agent_name}:")
        print(f"  Total Events: {total}")
        print(f"  Errors: {errors}")
        print(f"  Warnings: {warnings}")
        print(f"  Log File: {self.log_dir / f'{self.agent_name}.log'}")

        if errors > 0:
            print("\n  Recent Errors:")
            for event in self.get_errors()[-3:]:
                print(f"    • [{event.component}] {event.message}")
                if event.error_type:
                    print(f"      Type: {event.error_type}")


class SafeExecutor:
    """Decorator for safe error handling with debugging."""

    def __init__(self, debug_logger: DebugLogger, component: str,
                 default_return: Any = None):
        """Initialize safe executor.

        Parameters
        ----------
        debug_logger : DebugLogger
            Logger instance
        component : str
            Component name for logging
        default_return : Any
            Default value to return on error
        """
        self.debug_logger = debug_logger
        self.component = component
        self.default_return = default_return

    def __call__(self, func):
        """Decorator implementation."""
        def wrapper(*args, **kwargs):
            try:
                self.debug_logger.debug(
                    self.component,
                    f"Executing {func.__name__}"
                )
                result = func(*args, **kwargs)
                self.debug_logger.debug(
                    self.component,
                    f"{func.__name__} completed successfully"
                )
                return result
            except Exception as e:
                self.debug_logger.error(
                    self.component,
                    f"{func.__name__} failed",
                    exception=e,
                    context={"args": str(args)[:100], "kwargs": str(kwargs)[:100]}
                )
                return self.default_return
        return wrapper


# Utility functions for common error scenarios

def handle_network_error(debug_logger: DebugLogger, component: str,
                        exception: Exception, retry_count: int = 3) -> bool:
    """Handle network error with retry logic."""
    debug_logger.warning(
        component,
        f"Network error (attempt {retry_count}): {str(exception)[:100]}",
        context={"retry_count": retry_count, "error": str(exception)}
    )
    return retry_count < 3


def handle_validation_error(debug_logger: DebugLogger, component: str,
                           exception: Exception, field: str = "unknown") -> Dict:
    """Handle validation error and provide feedback."""
    debug_logger.error(
        component,
        f"Validation failed for field '{field}'",
        exception=exception,
        context={"field": field}
    )
    return {"valid": False, "field": field, "error": str(exception)}


def handle_resource_error(debug_logger: DebugLogger, component: str,
                         exception: Exception) -> bool:
    """Handle resource error."""
    debug_logger.critical(
        component,
        "Resource error - may need cleanup",
        exception=exception
    )
    return False


# Export public API
__all__ = [
    "DebugLogger",
    "DebugEvent",
    "ErrorCategory",
    "SafeExecutor",
    "handle_network_error",
    "handle_validation_error",
    "handle_resource_error",
]
