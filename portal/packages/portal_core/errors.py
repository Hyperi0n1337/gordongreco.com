"""Typed errors mapped to stable HTTP problem codes by the API adapter."""


class PortalError(Exception):
    code = "portal_error"
    status = 400


class Unauthorized(PortalError):
    code = "unauthorized"
    status = 401


class Forbidden(PortalError):
    code = "forbidden"
    status = 403


class NotFound(PortalError):
    code = "not_found"
    status = 404


class Conflict(PortalError):
    code = "conflict"
    status = 409


class Expired(PortalError):
    code = "expired"
    status = 410


class ValidationError(PortalError):
    code = "validation_error"
    status = 422


class RateLimited(PortalError):
    code = "rate_limited"
    status = 429


class ScannerUnavailable(PortalError):
    code = "scanner_unavailable"
    status = 503


class IntegrityFailure(PortalError):
    code = "integrity_failure"
    status = 422
