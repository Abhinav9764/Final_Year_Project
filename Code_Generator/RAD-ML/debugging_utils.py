"""
Comprehensive Debugging and Error Handling Utilities
======================================================
Provides structured error logging, categorization, and reporting
for all agents in the RAD-ML pipeline.
"""

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict


# ── Error Categories ──────────────────────────────────────────────────────
class ErrorCategory(Enum):
    """Categorize errors for better debugging and handling."""
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    RESOURCE_ERROR = "resource_error"
    PARSING_ERROR = "parsing_error"
    DATABASE_ERROR = "database_error"
    API_ERROR = "api_error"
    FILE_SYSTEM_ERROR = "file_system_error"
    DEPENDENCY_ERROR = "dependency_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "authentication_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorContext:
    """Structured error context for detailed debugging."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error_category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR
    error_message: str = ""
    error_type: str = ""
    stack_trace: str = ""
    context_data: Dict[str, Any] = field(default_factory=dict)
    user_message: str = ""
    recovery_action: str = ""
    component: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['error_category'] = self.error_category.value
        return data


class DebugLogger:
    """Centralized debugging and logging system."""

    def __init__(self, component_name: str, log_file: Optional[Path] = None):
        """
        Initialize the debug logger.

        Parameters
        ----------
        component_name : str
            Name of the component using this logger
        log_file : Path, optional
            File to write detailed logs to
        """
        self.component_name = component_name
        self.logger = logging.getLogger(f"RAD-ML.{component_name}")
        self.errors: List[ErrorContext] = []
        self.warnings: List[str] = []
        self.info_messages: List[str] = []
        self.debug_messages: List[str] = []

        # Set up logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

        # Optional file logging
        self.log_file = log_file
        if log_file:
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log_error(
        self,
        error: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR,
        context_data: Optional[Dict[str, Any]] = None,
        user_message: str = "",
        recovery_action: str = ""
    ) -> ErrorContext:
        """
        Log an error with full context.

        Parameters
        ----------
        error : Exception
            The exception that occurred
        category : ErrorCategory
            Category of the error
        context_data : Dict, optional
            Additional context data
        user_message : str
            User-friendly error message
        recovery_action : str
            Suggested recovery action

        Returns
        -------
        ErrorContext
            The logged error context
        """
        error_context = ErrorContext(
            error_category=category,
            error_message=str(error),
            error_type=type(error).__name__,
            stack_trace=traceback.format_exc(),
            context_data=context_data or {},
            user_message=user_message or self._get_user_message(category),
            recovery_action=recovery_action or self._get_recovery_action(category),
            component=self.component_name
        )

        self.errors.append(error_context)

        # Log with appropriate severity
        self.logger.error(
            f"[{category.value}] {error_context.error_message}",
            extra={'user_message': error_context.user_message}
        )

        return error_context

    def log_warning(self, message: str, context_data: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning."""
        self.warnings.append(message)
        self.logger.warning(message, extra=context_data or {})

    def log_info(self, message: str, context_data: Optional[Dict[str, Any]] = None) -> None:
        """Log informational message."""
        self.info_messages.append(message)
        self.logger.info(message, extra=context_data or {})

    def log_debug(self, message: str, context_data: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        self.debug_messages.append(message)
        self.logger.debug(message, extra=context_data or {})

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all logged events."""
        return {
            "component": self.component_name,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "info": self.info_messages,
            "debug": self.debug_messages,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }

    def save_report(self, output_file: Path) -> None:
        """Save debugging report to file."""
        report = self.get_summary()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        self.logger.info(f"Debug report saved to: {output_file}")

    @staticmethod
    def _get_user_message(category: ErrorCategory) -> str:
        """Get user-friendly message for error category."""
        messages = {
            ErrorCategory.VALIDATION_ERROR: "Invalid input provided. Please check your parameters.",
            ErrorCategory.NETWORK_ERROR: "Network error occurred. Please check your connection.",
            ErrorCategory.RESOURCE_ERROR: "System is out of resources. Please try again later.",
            ErrorCategory.PARSING_ERROR: "Failed to parse input. Invalid format provided.",
            ErrorCategory.DATABASE_ERROR: "Database error occurred. Data may be unavailable.",
            ErrorCategory.API_ERROR: "API request failed. Please try again.",
            ErrorCategory.FILE_SYSTEM_ERROR: "File system error. Unable to access file.",
            ErrorCategory.DEPENDENCY_ERROR: "Required dependency is missing. Please install it.",
            ErrorCategory.TIMEOUT_ERROR: "Operation timed out. Please try again.",
            ErrorCategory.AUTHENTICATION_ERROR: "Authentication failed. Please provide valid credentials.",
            ErrorCategory.CONFIGURATION_ERROR: "Configuration error. Please check your settings.",
            ErrorCategory.UNKNOWN_ERROR: "An unexpected error occurred. Please contact support.",
        }
        return messages.get(category, "An error occurred.")

    @staticmethod
    def _get_recovery_action(category: ErrorCategory) -> str:
        """Get recovery action for error category."""
        actions = {
            ErrorCategory.VALIDATION_ERROR: "Validate input and retry",
            ErrorCategory.NETWORK_ERROR: "Check connection and retry",
            ErrorCategory.RESOURCE_ERROR: "Free up resources and retry",
            ErrorCategory.PARSING_ERROR: "Check input format and retry",
            ErrorCategory.DATABASE_ERROR: "Check database connection and retry",
            ErrorCategory.API_ERROR: "Check API status and retry",
            ErrorCategory.FILE_SYSTEM_ERROR: "Check file permissions and retry",
            ErrorCategory.DEPENDENCY_ERROR: "Install missing dependency and retry",
            ErrorCategory.TIMEOUT_ERROR: "Increase timeout and retry",
            ErrorCategory.AUTHENTICATION_ERROR: "Provide valid credentials and retry",
            ErrorCategory.CONFIGURATION_ERROR: "Fix configuration and retry",
            ErrorCategory.UNKNOWN_ERROR: "Contact support for assistance",
        }
        return actions.get(category, "Retry operation")


class ErrorHandler:
    """Decorator for wrapping functions with error handling."""

    def __init__(self, logger: DebugLogger, default_return: Any = None):
        """
        Initialize error handler.

        Parameters
        ----------
        logger : DebugLogger
            Logger instance for this handler
        default_return : Any
            Default value to return on error
        """
        self.logger = logger
        self.default_return = default_return

    def handle(
        self,
        category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR,
        default_return: Optional[Any] = None
    ):
        """
        Decorator for automatic error handling.

        Parameters
        ----------
        category : ErrorCategory
            Category of errors this function might throw
        default_return : Any
            Value to return if error occurs

        Returns
        -------
        callable
            Decorated function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    context_data = {
                        'function': func.__name__,
                        'args': str(args)[:100],
                        'kwargs': str(kwargs)[:100]
                    }
                    self.logger.log_error(
                        e,
                        category=category,
                        context_data=context_data
                    )
                    return default_return if default_return is not None else self.default_return
            return wrapper
        return decorator


class PerformanceMonitor:
    """Monitor performance and detect bottlenecks."""

    def __init__(self, logger: DebugLogger):
        """Initialize performance monitor."""
        self.logger = logger
        self.timings: Dict[str, List[float]] = {}

    def record_timing(self, operation_name: str, duration: float) -> None:
        """Record operation timing."""
        if operation_name not in self.timings:
            self.timings[operation_name] = []
        self.timings[operation_name].append(duration)

        # Log if slow
        if duration > 5.0:  # 5 seconds
            self.logger.log_warning(
                f"Slow operation detected: {operation_name} took {duration:.2f}s",
                context_data={'duration': duration}
            )

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get timing statistics."""
        stats = {}
        for op_name, timings in self.timings.items():
            if timings:
                stats[op_name] = {
                    'min': min(timings),
                    'max': max(timings),
                    'avg': sum(timings) / len(timings),
                    'count': len(timings),
                    'total': sum(timings)
                }
        return stats


# ── Specific Error Handlers ───────────────────────────────────────────────
def handle_validation_error(
    logger: DebugLogger,
    field_name: str,
    value: Any,
    expected_type: str
) -> None:
    """Handle validation errors."""
    error = ValueError(f"Invalid value for {field_name}: {value} (expected {expected_type})")
    logger.log_error(
        error,
        category=ErrorCategory.VALIDATION_ERROR,
        context_data={
            'field': field_name,
            'value': str(value)[:100],
            'expected': expected_type
        },
        user_message=f"Invalid {field_name}. Please provide a {expected_type}."
    )


def handle_network_error(
    logger: DebugLogger,
    endpoint: str,
    error: Exception,
    retry_count: int = 3
) -> None:
    """Handle network errors with retry information."""
    logger.log_error(
        error,
        category=ErrorCategory.NETWORK_ERROR,
        context_data={
            'endpoint': endpoint,
            'retry_count': retry_count
        },
        recovery_action=f"Retrying {retry_count} times..."
    )


def handle_database_error(
    logger: DebugLogger,
    operation: str,
    error: Exception,
    table: str = ""
) -> None:
    """Handle database errors."""
    logger.log_error(
        error,
        category=ErrorCategory.DATABASE_ERROR,
        context_data={
            'operation': operation,
            'table': table
        }
    )


def handle_api_error(
    logger: DebugLogger,
    api_name: str,
    status_code: int,
    response: str = ""
) -> None:
    """Handle API errors."""
    error = Exception(f"API Error from {api_name}: {status_code}")
    logger.log_error(
        error,
        category=ErrorCategory.API_ERROR,
        context_data={
            'api': api_name,
            'status_code': status_code,
            'response': response[:500]
        }
    )


# ── Context Managers for Debugging ────────────────────────────────────────
class DebugContext:
    """Context manager for automatic error handling and timing."""

    def __init__(
        self,
        logger: DebugLogger,
        operation_name: str,
        monitor: Optional[PerformanceMonitor] = None
    ):
        """
        Initialize debug context.

        Parameters
        ----------
        logger : DebugLogger
            Logger instance
        operation_name : str
            Name of operation for logging
        monitor : PerformanceMonitor, optional
            Performance monitor for timing
        """
        self.logger = logger
        self.operation_name = operation_name
        self.monitor = monitor
        self.start_time = None

    def __enter__(self):
        """Enter context."""
        import time
        self.start_time = time.time()
        self.logger.log_debug(f"Starting: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        import time
        duration = time.time() - self.start_time

        if exc_type is None:
            self.logger.log_debug(f"Completed: {self.operation_name} ({duration:.2f}s)")
            if self.monitor:
                self.monitor.record_timing(self.operation_name, duration)
        else:
            self.logger.log_error(
                exc_val,
                category=ErrorCategory.UNKNOWN_ERROR,
                context_data={
                    'operation': self.operation_name,
                    'duration': duration
                }
            )

        return False  # Re-raise exception


__all__ = [
    'ErrorCategory',
    'ErrorContext',
    'DebugLogger',
    'ErrorHandler',
    'PerformanceMonitor',
    'DebugContext',
    'handle_validation_error',
    'handle_network_error',
    'handle_database_error',
    'handle_api_error',
]
