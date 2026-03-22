import base64
import hashlib
import hmac
from typing import Any, NoReturn

import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
from app.core.exceptions import AuthenticationError, RegistrationError


class CognitoService:
    def __init__(self) -> None:
        self._client = boto3.client(
            "cognito-idp",
            region_name=settings.COGNITO_REGION,
        )
        self._user_pool_id = settings.COGNITO_USER_POOL_ID
        self._client_id = settings.COGNITO_APP_CLIENT_ID
        self._backend_client_id = settings.COGNITO_BACKEND_CLIENT_ID

    def _compute_secret_hash(self, username: str) -> str | None:
        if not settings.COGNITO_BACKEND_CLIENT_SECRET:
            return None
        message = username + self._backend_client_id
        digest = hmac.new(
            settings.COGNITO_BACKEND_CLIENT_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    def authenticate_user(self, email: str, password: str) -> dict[str, Any]:
        try:
            auth_params: dict[str, str] = {
                "USERNAME": email,
                "PASSWORD": password,
            }
            secret_hash = self._compute_secret_hash(email)
            if secret_hash:
                auth_params["SECRET_HASH"] = secret_hash

            response = self._client.admin_initiate_auth(
                UserPoolId=self._user_pool_id,
                ClientId=self._backend_client_id,
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters=auth_params,
            )

            auth_result = response["AuthenticationResult"]
            return {
                "access_token": auth_result["AccessToken"],
                "refresh_token": auth_result.get("RefreshToken", ""),
                "expires_in": auth_result["ExpiresIn"],
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self._handle_auth_error(error_code)

    def refresh_tokens(self, refresh_token: str, email: str | None = None) -> dict[str, Any]:
        try:
            auth_params: dict[str, str] = {
                "REFRESH_TOKEN": refresh_token,
            }
            if email:
                secret_hash = self._compute_secret_hash(email)
                if secret_hash:
                    auth_params["SECRET_HASH"] = secret_hash
            response = self._client.admin_initiate_auth(
                UserPoolId=self._user_pool_id,
                ClientId=self._backend_client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters=auth_params,
            )

            auth_result = response["AuthenticationResult"]
            return {
                "access_token": auth_result["AccessToken"],
                "expires_in": auth_result["ExpiresIn"],
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self._handle_auth_error(error_code)

    def global_sign_out(self, cognito_sub: str) -> dict[str, Any]:
        try:
            self._client.admin_user_global_sign_out(
                UserPoolId=self._user_pool_id,
                Username=cognito_sub,
            )
            return {"signed_out": True}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self._handle_auth_error(error_code)

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

    def _handle_auth_error(self, error_code: str) -> NoReturn:
        auth_error_map: dict[str, tuple[str, str, int]] = {
            "NotAuthorizedException": (
                "INVALID_CREDENTIALS",
                "Invalid email or password",
                401,
            ),
            "UserNotConfirmedException": (
                "EMAIL_NOT_VERIFIED",
                "Please verify your email before logging in",
                403,
            ),
            "UserNotFoundException": (
                "INVALID_CREDENTIALS",
                "Invalid email or password",
                401,
            ),
            "PasswordResetRequiredException": (
                "PASSWORD_RESET_REQUIRED",
                "You must reset your password before logging in",
                403,
            ),
        }

        if error_code in auth_error_map:
            code, message, status_code = auth_error_map[error_code]
            raise AuthenticationError(code=code, message=message, status_code=status_code)

        raise AuthenticationError(
            code="AUTH_ERROR",
            message="An unexpected error occurred during authentication",
            status_code=500,
        )
