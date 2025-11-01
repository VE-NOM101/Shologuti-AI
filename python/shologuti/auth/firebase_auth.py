from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests


class FirebaseAuthError(Exception):
    pass

@dataclass
class FirebaseUser:
    uid: str
    email: str
    id_token: str
    refresh_token: str
    display_name: Optional[str] = None


class FirebaseAuthClient:
    _IDENTITY_BASE_URL = "https://identitytoolkit.googleapis.com/v1"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0) -> None:
        # Resolve credentials up front
        self.api_key = (api_key or os.getenv("FIREBASE_WEB_API_KEY", "")).strip()
        if not self.api_key:
            raise FirebaseAuthError(
                "Firebase API key missing. Set the FIREBASE_WEB_API_KEY environment variable."
            )
        self.timeout = timeout

    def register_user(self, name: str, email: str, password: str) -> FirebaseUser:
        # Create an email/password account
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }
        data = self._post("accounts:signUp", payload)

        user = FirebaseUser(
            uid=data["localId"],
            email=data["email"],
            id_token=data["idToken"],
            refresh_token=data["refreshToken"],
            display_name=data.get("displayName"),
        )

        name_to_apply = name.strip()
        if name_to_apply:
            user = self._apply_display_name(user, name_to_apply)

        return user

    def login_user(self, email: str, password: str) -> FirebaseUser:
        # Authenticate and fetch session tokens
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }
        data = self._post("accounts:signInWithPassword", payload)

        return FirebaseUser(
            uid=data["localId"],
            email=data["email"],
            id_token=data["idToken"],
            refresh_token=data["refreshToken"],
            display_name=data.get("displayName"),
        )

    def _apply_display_name(self, user: FirebaseUser, display_name: str) -> FirebaseUser:
        # Update the profile metadata
        payload = {
            "idToken": user.id_token,
            "displayName": display_name,
            "returnSecureToken": True,
        }
        data = self._post("accounts:update", payload)

        return FirebaseUser(
            uid=data.get("localId", user.uid),
            email=data.get("email", user.email),
            id_token=data.get("idToken", user.id_token),
            refresh_token=data.get("refreshToken", user.refresh_token),
            display_name=data.get("displayName", display_name),
        )

    def _post(self, path: str, payload: dict) -> dict:
        # Minimal wrapper over the REST call
        url = f"{self._IDENTITY_BASE_URL}/{path}?key={self.api_key}"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise FirebaseAuthError("Could not reach Firebase Authentication service.") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise FirebaseAuthError("Unexpected response from Firebase Authentication.") from exc

        if response.status_code != 200:
            raise FirebaseAuthError(self._decode_error(message=data))

        return data

    @staticmethod
    def _decode_error(message: dict | str) -> str:
        # Map Firebase errors to friendly text
        if isinstance(message, str):
            return message

        firebase_message = (
            message.get("error", {}).get("message")
            if isinstance(message.get("error"), dict)
            else None
        )

        if not firebase_message:
            return "Authentication failed."

        error_map = {
            "EMAIL_EXISTS": "An account already exists for this email address.",
            "OPERATION_NOT_ALLOWED": "Email/password accounts are not enabled for this project.",
            "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please try again later.",
            "WEAK_PASSWORD": "Choose a stronger password (at least 6 characters).",
            "INVALID_PASSWORD": "Incorrect password.",
            "EMAIL_NOT_FOUND": "No account found with that email address.",
            "USER_DISABLED": "This account has been disabled by an administrator.",
            "INVALID_EMAIL": "Enter a valid email address.",
        }

        return error_map.get(firebase_message, firebase_message.replace("_", " ").capitalize())


__all__ = ["FirebaseAuthClient", "FirebaseAuthError", "FirebaseUser"]


