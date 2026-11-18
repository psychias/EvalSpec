class AdapterError(Exception):
    """Base exception for adapter errors"""

class TransformationError(AdapterError):
    """Raised when transformation logic fails"""
