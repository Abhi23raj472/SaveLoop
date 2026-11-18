"""API errors with the codes the frontend understands."""


class ApiError(Exception):
    def __init__(self, code: str, status: int, message: str | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.message = message


def invalid_url(msg=None):
    return ApiError("invalid_url", 400, msg)


def unsupported_platform(msg=None):
    return ApiError("unsupported_platform", 400, msg)


def private(msg=None):
    return ApiError("private", 403, msg)


def not_found(msg=None):
    return ApiError("not_found", 404, msg)


def rate_limited(msg=None):
    return ApiError("rate_limited", 429, msg)


def extraction_failed(msg=None):
    return ApiError("extraction_failed", 502, msg)


def no_video(msg=None):
    return ApiError("no_video", 422, msg)
