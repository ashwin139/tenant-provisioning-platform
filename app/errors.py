"""Domain errors. The API layer maps each to an HTTP status and error code."""


class DomainError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TenantNotFound(DomainError):
    status_code = 404
    code = "tenant_not_found"


class DuplicateTenantName(DomainError):
    status_code = 409
    code = "duplicate_tenant_name"


class UnsupportedTenantModel(DomainError):
    status_code = 422
    code = "unsupported_tenant_model"


class InvalidTenantState(DomainError):
    """e.g. retry on a tenant that is not FAILED."""

    status_code = 409
    code = "invalid_tenant_state"
