import pytest

from app.core.exceptions import AuthenticationError, RegistrationError
from app.core.security import get_current_user_payload
from app.main import app


# ==================== Signup Tests (Story 1.3 — preserved) ====================


@pytest.mark.asyncio
async def test_signup_valid_data(client, mock_cognito_service):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Verification email sent"
    assert "userId" in data
    mock_cognito_service.sign_up.assert_called_once_with(
        email="test@example.com", password="StrongPass1!"
    )


@pytest.mark.asyncio
async def test_signup_duplicate_email(client, mock_cognito_service):
    mock_cognito_service.sign_up.side_effect = RegistrationError(
        code="EMAIL_ALREADY_EXISTS",
        message="An account with this email already exists",
        status_code=409,
    )

    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "existing@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_signup_invalid_email(client):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "StrongPass1!"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_weak_password(client):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_valid_code(client, mock_cognito_service):
    # First create a user via signup
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "verify@example.com", "password": "StrongPass1!"},
    )

    # Now verify
    response = await client.post(
        "/api/v1/auth/verify",
        json={"email": "verify@example.com", "code": "123456"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Email verified"
    mock_cognito_service.confirm_sign_up.assert_called_once_with(
        email="verify@example.com", code="123456"
    )


@pytest.mark.asyncio
async def test_verify_invalid_code(client, mock_cognito_service):
    mock_cognito_service.confirm_sign_up.side_effect = RegistrationError(
        code="INVALID_CODE",
        message="Verification code is incorrect",
        status_code=400,
    )

    response = await client.post(
        "/api/v1/auth/verify",
        json={"email": "test@example.com", "code": "000000"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_CODE"


@pytest.mark.asyncio
async def test_resend_verification(client, mock_cognito_service):
    response = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "test@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Verification code sent"
    mock_cognito_service.resend_confirmation_code.assert_called_once_with(
        email="test@example.com"
    )


# ==================== Login Tests (Story 1.4) ====================


@pytest.mark.asyncio
async def test_login_success(client, mock_cognito_service, mock_rate_limiter):
    """9.1 Test login success with valid credentials -> 200 + tokens"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "refreshToken" in data
    assert "expiresIn" in data
    assert data["user"]["email"] == "test@example.com"
    assert "id" in data["user"]
    assert "locale" in data["user"]
    mock_cognito_service.authenticate_user.assert_called_once_with(
        email="test@example.com", password="StrongPass1!"
    )
    mock_rate_limiter.clear_attempts.assert_called_once()


@pytest.mark.asyncio
async def test_login_invalid_password(client, mock_cognito_service, mock_rate_limiter):
    """9.2 Test login with invalid password -> 401 INVALID_CREDENTIALS"""
    mock_cognito_service.authenticate_user.side_effect = AuthenticationError(
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
        status_code=401,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "WrongPass1!"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    mock_rate_limiter.record_failed_attempt.assert_called_once()


@pytest.mark.asyncio
async def test_login_unverified_email(client, mock_cognito_service):
    """9.3 Test login with unverified email -> 403 EMAIL_NOT_VERIFIED"""
    mock_cognito_service.authenticate_user.side_effect = AuthenticationError(
        code="EMAIL_NOT_VERIFIED",
        message="Please verify your email before logging in",
        status_code=403,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "unverified@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "EMAIL_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_login_nonexistent_email(client, mock_cognito_service):
    """9.4 Test login with non-existent email -> 401 INVALID_CREDENTIALS (no enumeration)"""
    mock_cognito_service.authenticate_user.side_effect = AuthenticationError(
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
        status_code=401,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 401
    data = response.json()
    # Same error as wrong password — prevents user enumeration
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_rate_limited(client, mock_rate_limiter):
    """9.5 Test rate limiting -> 429 RATE_LIMITED after 10 failed attempts"""
    mock_rate_limiter.check_rate_limit.side_effect = AuthenticationError(
        code="RATE_LIMITED",
        message="Too many login attempts. Please try again later.",
        status_code=429,
        details={"retryAfter": 600},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 429
    data = response.json()
    assert data["error"]["code"] == "RATE_LIMITED"
    assert data["error"]["details"]["retryAfter"] == 600
    assert response.headers.get("retry-after") == "600"


# ==================== Token Refresh Tests (Story 1.4) ====================


@pytest.mark.asyncio
async def test_refresh_token_success(client, mock_cognito_service):
    """9.6 Test token refresh -> 200 + new access token"""
    # Create a user first so the endpoint can resolve email -> cognito_sub.
    await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "StrongPass1!"},
    )

    response = await client.post(
        "/api/v1/auth/refresh-token",
        json={"refreshToken": "valid-refresh-token", "email": "test@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "expiresIn" in data
    # SECRET_HASH must be computed with cognito_sub, not email (REFRESH_TOKEN_AUTH
    # gotcha — Cognito validates the hash against the sub).
    mock_cognito_service.refresh_tokens.assert_called_once_with(
        refresh_token="valid-refresh-token", cognito_sub="test-cognito-sub-123"
    )


@pytest.mark.asyncio
async def test_refresh_token_invalid(client, mock_cognito_service):
    """9.7 Test token refresh with invalid token -> 401"""
    mock_cognito_service.refresh_tokens.side_effect = AuthenticationError(
        code="INVALID_CREDENTIALS",
        message="Invalid or expired refresh token",
        status_code=401,
    )

    response = await client.post(
        "/api/v1/auth/refresh-token",
        json={"refreshToken": "invalid-refresh-token", "email": "test@example.com"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


# ==================== Get Me Tests (Story 1.4) ====================


@pytest.mark.asyncio
async def test_get_me_success(client, mock_cognito_service):
    """9.8 Test GET /me with valid token -> 200 + user profile"""
    # First create a user via login
    await client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "StrongPass1!"},
    )

    # Override auth for the /me endpoint
    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    try:
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert "id" in data
        assert "locale" in data
        assert "isVerified" in data
        assert "createdAt" in data
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    """9.9 Test GET /me without token -> 401"""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code in (401, 403)


# ==================== Logout Tests (Story 1.4) ====================


@pytest.mark.asyncio
async def test_logout_success(client, mock_cognito_service):
    """9.10 Test logout -> 200"""
    # First create a user via login
    await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "StrongPass1!"},
    )

    # Override auth for the /logout endpoint
    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    try:
        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out successfully"
        mock_cognito_service.global_sign_out.assert_called_once_with(
            cognito_sub="test-cognito-sub-123"
        )
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


# ==================== Update Profile (PATCH /me) Tests (Story 1.6) ====================


@pytest.mark.asyncio
async def test_patch_me_locale_uk(client, mock_cognito_service):
    """7.1 Test PATCH /me with valid locale 'uk' -> 200, user.locale updated"""
    # Create user via login
    await client.post(
        "/api/v1/auth/login",
        json={"email": "locale-uk@example.com", "password": "StrongPass1!"},
    )

    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    try:
        response = await client.patch(
            "/api/v1/auth/me",
            json={"locale": "uk"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["locale"] == "uk"
        assert "email" in data
        assert "id" in data
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_patch_me_locale_en(client, mock_cognito_service):
    """7.2 Test PATCH /me with valid locale 'en' -> 200, user.locale updated"""
    # Create user via login
    await client.post(
        "/api/v1/auth/login",
        json={"email": "locale-en@example.com", "password": "StrongPass1!"},
    )

    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    try:
        response = await client.patch(
            "/api/v1/auth/me",
            json={"locale": "en"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["locale"] == "en"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_patch_me_invalid_locale(client, mock_cognito_service):
    """7.3 Test PATCH /me with invalid locale 'fr' -> 422"""
    # Create user via login
    await client.post(
        "/api/v1/auth/login",
        json={"email": "locale-bad@example.com", "password": "StrongPass1!"},
    )

    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    try:
        response = await client.patch(
            "/api/v1/auth/me",
            json={"locale": "fr"},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_patch_me_no_token(client):
    """7.4 Test PATCH /me without authentication -> 401"""
    response = await client.patch(
        "/api/v1/auth/me",
        json={"locale": "uk"},
    )

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_me_returns_locale(client, mock_cognito_service):
    """7.5 Test GET /me returns locale field in response"""
    # Create user via login
    await client.post(
        "/api/v1/auth/login",
        json={"email": "locale-get@example.com", "password": "StrongPass1!"},
    )

    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    try:
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert "locale" in data
        assert data["locale"] in ("uk", "en")
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)


@pytest.mark.asyncio
async def test_default_locale_is_uk(client, mock_cognito_service):
    """7.6 Test default locale is 'uk' for new users"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "default-locale@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["locale"] == "uk"


# ==================== Signup Locale Tests (Story 5.6 review) ====================


@pytest.mark.asyncio
async def test_signup_with_locale_en(client, mock_cognito_service):
    """Test signup with locale 'en' stores locale correctly"""
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "signup-en@example.com", "password": "StrongPass1!", "locale": "en"},
    )

    # Login to verify the stored locale
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "signup-en@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["locale"] == "en"


@pytest.mark.asyncio
async def test_signup_without_locale_defaults_to_uk(client, mock_cognito_service):
    """Test signup without locale field defaults to 'uk'"""
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "signup-default@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_signup_with_invalid_locale_returns_422(client, mock_cognito_service):
    """Test signup with invalid locale returns 422"""
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "signup-bad@example.com", "password": "StrongPass1!", "locale": "fr"},
    )

    assert response.status_code == 422


# ==================== Forgot Password Tests (Story 1.8) ====================


@pytest.mark.asyncio
async def test_forgot_password_registered_email(client, mock_cognito_service):
    """Forgot password for a registered email returns 200 with generic message."""
    mock_cognito_service.initiate_forgot_password.return_value = None

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "known@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "If an account exists, a reset code has been sent"
    mock_cognito_service.initiate_forgot_password.assert_called_once_with(
        email="known@example.com"
    )


@pytest.mark.asyncio
async def test_forgot_password_unknown_email(client, mock_cognito_service):
    """Unknown email returns the same generic 200 message (no enumeration)."""
    # Service silently succeeds for UserNotFoundException — simulate by
    # simply returning None; that's how the service handles unknown emails.
    mock_cognito_service.initiate_forgot_password.return_value = None

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "If an account exists, a reset code has been sent"


@pytest.mark.asyncio
async def test_forgot_password_unverified_email(client, mock_cognito_service):
    """Unverified accounts return the same generic 200 response (no enumeration)."""
    # Service silently swallows all Cognito errors (NotAuthorizedException for
    # unverified, UserNotFoundException for unknown, etc.) so the API surface
    # is indistinguishable across account states.
    mock_cognito_service.initiate_forgot_password.return_value = None

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "unverified@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "If an account exists, a reset code has been sent"


@pytest.mark.asyncio
async def test_forgot_password_invalid_email_format(client):
    """Invalid email format returns 422 validation error."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_success(client, mock_cognito_service):
    """Valid code + strong password resets successfully."""
    mock_cognito_service.confirm_forgot_password.return_value = None

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "code": "123456",
            "newPassword": "BrandNewPass1!",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Password updated successfully"
    mock_cognito_service.confirm_forgot_password.assert_called_once_with(
        email="user@example.com",
        code="123456",
        new_password="BrandNewPass1!",
    )


@pytest.mark.asyncio
async def test_reset_password_invalid_code(client, mock_cognito_service):
    """Wrong code returns RESET_CODE_INVALID."""
    mock_cognito_service.confirm_forgot_password.side_effect = AuthenticationError(
        code="RESET_CODE_INVALID",
        message="Reset code is invalid. Please request a new one",
        status_code=400,
    )

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "code": "000000",
            "newPassword": "BrandNewPass1!",
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "RESET_CODE_INVALID"


@pytest.mark.asyncio
async def test_reset_password_expired_code(client, mock_cognito_service):
    """Expired code returns RESET_CODE_EXPIRED."""
    mock_cognito_service.confirm_forgot_password.side_effect = AuthenticationError(
        code="RESET_CODE_EXPIRED",
        message="Reset code has expired. Please request a new one",
        status_code=400,
    )

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "code": "654321",
            "newPassword": "BrandNewPass1!",
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "RESET_CODE_EXPIRED"


@pytest.mark.asyncio
async def test_reset_password_weak_password(client, mock_cognito_service):
    """Cognito-rejected weak password returns PASSWORD_TOO_WEAK."""
    mock_cognito_service.confirm_forgot_password.side_effect = AuthenticationError(
        code="PASSWORD_TOO_WEAK",
        message="Password does not meet requirements",
        status_code=422,
    )

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "code": "123456",
            "newPassword": "weakpass",
        },
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "PASSWORD_TOO_WEAK"


@pytest.mark.asyncio
async def test_reset_password_rejects_short_code(client):
    """Codes shorter than 6 chars are rejected at validation layer."""
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "code": "123",
            "newPassword": "BrandNewPass1!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password(client):
    """Passwords shorter than 8 chars are rejected at validation layer."""
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "code": "123456",
            "newPassword": "short",
        },
    )
    assert response.status_code == 422
