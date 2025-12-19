class MetaAPIError(Exception):
    """Custom exception for Meta Graph API errors"""
    def __init__(self, message: str, error_code: int = None, subcode: int = None):
        self.message = message
        self.error_code = error_code
        self.subcode = subcode
        super().__init__(self.message)

    def __str__(self):
        return f"[Meta Error {self.error_code or ''}] {self.message}"