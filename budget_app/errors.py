class AppError(Exception):
    """사용자에게 설명할 수 있는 예상 가능한 오류."""

    def __init__(self, message: str, hint: str = "--help로 사용법을 확인하세요.") -> None:
        super().__init__(message)
        self.hint = hint

