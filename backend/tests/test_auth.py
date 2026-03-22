import pytest

from app.core.exceptions import RegistrationError


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
