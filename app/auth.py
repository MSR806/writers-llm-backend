import base64

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from .config import AUTH0_ALGORITHMS, AUTH0_API_AUDIENCE, AUTH0_DOMAIN, AUTH0_ISSUER

# Security scheme for Swagger UI
security = HTTPBearer()


def get_auth0_jwks():
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    response = requests.get(jwks_url)
    return response.json()


def get_signing_key(token):
    try:
        jwks = get_auth0_jwks()
        unverified_header = jwt.get_unverified_header(token)
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                # Convert the RSA key components to PEM format
                n = int.from_bytes(
                    base64.urlsafe_b64decode(key["n"] + "=" * (-len(key["n"]) % 4)), byteorder="big"
                )
                e = int.from_bytes(
                    base64.urlsafe_b64decode(key["e"] + "=" * (-len(key["e"]) % 4)), byteorder="big"
                )

                # Construct the RSA public key in PEM format
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

                numbers = RSAPublicNumbers(e, n)
                public_key = numbers.public_key()

                pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                return pem
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signing key",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error retrieving token signing key: {str(e)}",
        )


def verify_token(token: str):
    try:
        key = get_signing_key(token)
        payload = jwt.decode(
            token,
            key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_API_AUDIENCE,
            issuer=AUTH0_ISSUER,
        )
        return payload
    except ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token has expired: {str(e)}",
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to validate token: {str(e)}",
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)

    # Extract user information from the token
    # 'sub' is the Auth0 user ID, typically in format 'auth0|user_id'
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity",
        )

    # You can add additional user verification logic here if needed

    return {
        "user_id": user_id,
        # Add any additional user information from the token you want to pass to the routes
        "permissions": payload.get("permissions", []),
        "email": payload.get("email"),
    }


async def get_auth0_user_details(access_token: str) -> dict:
    try:
        # Make request to Auth0 UserInfo endpoint
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        response = requests.get(f"https://{AUTH0_DOMAIN}/userinfo", headers=headers)

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to fetch user details from Auth0",
            )

        user_data = response.json()
        return {
            "name": user_data.get("name")
            or user_data.get("nickname")
            or user_data.get("email", "Anonymous"),
            "email": user_data.get("email", "Anonymous"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error fetching user details: {str(e)}",
        )


async def require_write_permission(current_user: dict = Depends(get_current_user)):
    if "book:write" not in current_user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action",
        )
    return current_user


async def require_delete_permission(current_user: dict = Depends(get_current_user)):
    if "book:delete" not in current_user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action",
        )
    return current_user


async def require_storyboard_write_permission(current_user: dict = Depends(get_current_user)):
    if "storyboard:write" not in current_user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action",
        )
    return current_user


async def require_storyboard_read_permission(current_user: dict = Depends(get_current_user)):
    if "storyboard:read" not in current_user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action",
        )
    return current_user


async def require_template_write_permission(current_user: dict = Depends(get_current_user)):
    if "template:write" not in current_user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action",
        )
    return current_user


async def require_template_read_permission(current_user: dict = Depends(get_current_user)):
    if "template:read" not in current_user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action",
        )
    return current_user
