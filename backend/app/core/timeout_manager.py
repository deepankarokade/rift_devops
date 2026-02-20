"""
timeout_manager.py

Manages timeouts for various operations in the CI/CD pipeline healing system.
"""

import time
import sys
from typing import Callable, Any


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout limit."""
    pass


class TimeoutManager:
    """Manages timeout for operations."""
    
    def __init__(self, default_timeout: int = 120) -> None:
        """
        Initialize the timeout manager.
        
        Args:
            default_timeout: Default timeout in seconds.
        """
        self.default_timeout = default_timeout
    
    def run_with_timeout(self, func: Callable, *args, timeout: int = None, **kwargs) -> Any:
        """
        Run a function with a timeout.
        
        Args:
            func: The function to run.
            *args: Positional arguments for the function.
            timeout: Timeout in seconds (uses default if not provided).
            **kwargs: Keyword arguments for the function.
        
        Returns:
            The result of the function.
        
        Raises:
            TimeoutError: If the function exceeds the timeout.
        """
        timeout = timeout or self.default_timeout
        
        # Use threading-based timeout for cross-platform compatibility
        import threading
        
        result = [None]
        exception = [None]
        
        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Operation timed out after {timeout} seconds")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
