from typing import Any, NoReturn

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import RegistrationError


class CognitoService:
    def __init__(self) -> None:
        self._client = boto3.client(
            "cognito-idp",
            region_name=settings.COGNITO_REGION,
        )
        self._user_pool_id = settings.COGNITO_USER_POOL_ID
        self._client_id = settings.COGNITO_APP_CLIENT_ID

    def sign_up(self, email: str, password: str) -> dict[str, Any]:
        try:
            response = self._client.sign_up(
                ClientId=self._client_id,
                Username=email,
                Password=password,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                ],
            )
            return {
                "user_sub": response["UserSub"],
                "user_confirmed": response["UserConfirmed"],
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self._handle_cognito_error(error_code)

    def confirm_sign_up(self, email: str, code: str) -> dict[str, Any]:
        try:
            self._client.confirm_sign_up(
                ClientId=self._client_id,
                Username=email,
                ConfirmationCode=code,
            )
            return {"confirmed": True}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self._handle_cognito_error(error_code)

    def resend_confirmation_code(self, email: str) -> dict[str, Any]:
        try:
            self._client.resend_confirmation_code(
                ClientId=self._client_id,
                Username=email,
            )
            return {"sent": True}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self._handle_cognito_error(error_code)

    def _handle_cognito_error(self, error_code: str) -> NoReturn:
        error_map: dict[str, tuple[str, str, int]] = {
            "UsernameExistsException": (
                "EMAIL_ALREADY_EXISTS",
                "An account with this email already exists",
                409,
            ),
            "InvalidPasswordException": (
                "WEAK_PASSWORD",
                "Password does not meet requirements",
                422,
            ),
            "CodeMismatchException": (
                "INVALID_CODE",
                "Verification code is incorrect",
                400,
            ),
            "ExpiredCodeException": (
                "CODE_EXPIRED",
                "Verification code has expired. Request a new one",
                400,
            ),
            "LimitExceededException": (
                "RATE_LIMITED",
                "Too many attempts. Please try again later",
                429,
            ),
            "NotAuthorizedException": (
                "NOT_AUTHORIZED",
                "Invalid credentials",
                401,
            ),
        }

        if error_code in error_map:
            code, message, status_code = error_map[error_code]
            raise RegistrationError(code=code, message=message, status_code=status_code)

        raise RegistrationError(
            code="COGNITO_ERROR",
            message="An unexpected error occurred",
            status_code=500,
        )
