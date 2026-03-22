import logging
import uuid

from sqlmodel import SQLModel
from sqlmodel.sql.expression import SelectOfScalar

from app.core.exceptions import ForbiddenError

logger = logging.getLogger(__name__)


def user_scoped_query(
    statement: SelectOfScalar[SQLModel],
    user_id: uuid.UUID,
    model: type[SQLModel] | None = None,
) -> SelectOfScalar[SQLModel]:
    """Add a user_id filter to any SQLModel select statement.

    Every API endpoint that queries user-owned data MUST use this helper
    (or get_current_user / get_current_user_id dependency) to scope
    queries to the authenticated user.

    Args:
        statement: An existing SQLModel select statement.
        user_id: The authenticated user's UUID.
        model: The model class to filter on. If None, inferred from the statement's
               first column entity (works for simple `select(Model)` statements).

    Returns:
        The statement with `.where(Model.user_id == user_id)` applied.
    """
    if model is not None:
        return statement.where(model.user_id == user_id)  # type: ignore[attr-defined]

    # Infer model from statement columns
    entity = statement.column_descriptions[0]["entity"]
    return statement.where(entity.user_id == user_id)


def verify_resource_ownership(
    resource: SQLModel,
    current_user_id: uuid.UUID,
    *,
    resource_type: str | None = None,
    ip: str | None = None,
) -> None:
    """Verify that the authenticated user owns the given resource.

    Raises ForbiddenError (HTTP 403) and logs the violation if
    resource.user_id != current_user_id.
    """
    resource_user_id = getattr(resource, "user_id", None)
    if resource_user_id is None:
        raise AttributeError(
            f"{type(resource).__name__} has no 'user_id' attribute"
        )

    if resource_user_id != current_user_id:
        resource_id = getattr(resource, "id", None)
        resolved_type = resource_type or type(resource).__name__

        logger.warning(
            "access_denied",
            extra={
                "action": "access_denied",
                "user_id": str(current_user_id),
                "resource_type": resolved_type,
                "resource_id": str(resource_id),
                "ip": ip or "",
                "event": "unauthorized_access_attempt",
            },
        )

        raise ForbiddenError()
