"""
This module provides functionality for authenticating with the Seedr.cc API.

It contains the Login class for generating login tokens and the create_token
function for encoding token information.
"""

import asyncio
from base64 import b64encode
from typing import Optional, Dict, Any

import aiohttp


def create_token(
    response: Dict[str, Any],
    refresh_token: Optional[str] = None,
    device_code: Optional[str] = None,
) -> str:
    """
    Create an encoded token string from the API response.

    Args:
        response (Dict[str, Any]): The API response containing token information.
        refresh_token (Optional[str]): A refresh token to include in the encoded string.
        device_code (Optional[str]): A device code to include in the encoded string.

    Returns:
        str: An encoded token string.

    Example:
        >>> response = {'access_token': 'abc123'}
        >>> token = create_token(response, refresh_token='refresh456', device_code='device789')
        >>> print(token)
    """
    token = {"access_token": response["access_token"]}

    if refresh_token or "refresh_token" in response:
        token["refresh_token"] = refresh_token or response["refresh_token"]

    if device_code:
        token["device_code"] = device_code

    return b64encode(str(token).encode()).decode()


class Login:
    """
    A class to handle authentication with the Seedr.cc API.

    This class provides methods to generate login tokens either through
    username/password authentication or device code authorization.

    Attributes:
        token (Optional[str]): The generated token after successful authorization.

    Args:
        username (Optional[str]): The username for the Seedr account.
        password (Optional[str]): The password for the Seedr account.

    Example:
        Logging in with username and password:
            >>> async with Login('user@example.com', 'password123') as login:
            ...     await login.authorize()
            ...     print(login.token)

        Authorizing with device code:
            >>> async with Login() as login:
            ...     device_code = await login.get_device_code()
            ...     print(f"Please authorize: {device_code['verification_url']}")
            ...     print(f"Your user code is: {device_code['user_code']}")
            ...     await login.authorize(device_code['device_code'])
            ...     print(login.token)
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        session_args: Optional[Dict[str, Any]] = None,
    ):
        self._username = username
        self._password = password
        self.token: Optional[str] = None

        if session:
            self._session = session
            self._should_close_session = False
        else:
            # Default session arguments if none provided
            session_args = session_args or {
                "timeout": aiohttp.ClientTimeout(total=10),
                "connector": aiohttp.TCPConnector(limit=10, ttl_dns_cache=300),
            }
            self._session = None  # Will be initialized in __aenter__
            self._session_args = session_args
            self._should_close_session = True

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(**self._session_args)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._should_close_session and self._session:
            await self._session.close()

    async def get_device_code(self) -> Dict[str, Any]:
        """
        Generate a device and user code for authorization.

        Returns:
            Dict[str, Any]: A dictionary containing the device_code, user_code,
                            verification_url, and expires_in.

        Example:
            >>> async with Login() as login:
            ...     device_code = await login.get_device_code()
            ...     print(device_code)
        """
        url = "https://www.seedr.cc/api/device/code"
        params = {"client_id": "seedr_xbmc"}

        async with self._session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def authorize(self, device_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Authorize and get a token for the Seedr account.

        This method can be used either with a username/password combination
        (set during class initialization) or with a device_code obtained from
        the get_device_code method.

        Args:
            device_code (Optional[str]): The device code obtained from get_device_code.

        Returns:
            Dict[str, Any]: The API response containing token information.

        Raises:
            ValueError: If neither username/password nor device_code is provided.
            aiohttp.ClientError: If the request fails.

        Example:
            Authorizing with username and password:
                >>> async with Login('user@example.com', 'password123') as login:
                ...     response = await login.authorize()
                ...     print(response)
                ...     print(login.token)

            Authorizing with device code:
                >>> async with Login() as login:
                ...     device_code_info = await login.get_device_code()
                ...     response = await login.authorize(device_code_info['device_code'])
                ...     print(response)
                ...     print(login.token)
        """
        if device_code:
            url = "https://www.seedr.cc/api/device/authorize"
            params = {"client_id": "seedr_xbmc", "device_code": device_code}

            async with self._session.get(url, params=params) as response:
                response.raise_for_status()
                response_json = await response.json(content_type=None)

        elif self._username and self._password:
            url = "https://www.seedr.cc/oauth_test/token.php"
            data = {
                "grant_type": "password",
                "client_id": "seedr_chrome",
                "type": "login",
                "username": self._username,
                "password": self._password,
            }

            async with self._session.post(url, data=data) as response:
                response.raise_for_status()
                response_json = await response.json(content_type=None)

        else:
            raise ValueError("No device code or email/password provided")

        if "access_token" in response_json:
            self.token = create_token(response_json, device_code=device_code)

        return response_json

    async def device_authorization_flow(self, callback) -> Dict[str, Any]:
        """
        Perform the complete device authorization flow.

        This method gets a device code, waits for user authorization, and then
        completes the authorization process.

        Args:
            callback: A callable that takes the device_code information and handles
                      user interaction (e.g., displaying the verification URL and user code).

        Returns:
            Dict[str, Any]: The final API response after successful authorization.

        Example:
            >>> async def user_interaction(device_info):
            ...     print(f"Please go to {device_info['verification_url']} and enter code: {device_info['user_code']}")
            ...     input("Press Enter after you've authorized the device...")
            >>> async with Login() as login:
            ...     response = await login.device_authorization_flow(user_interaction)
            ...     print(response)
            ...     print(login.token)
        """
        device_code_info = await self.get_device_code()
        await callback(device_code_info)

        while True:
            response = await self.authorize(device_code_info["device_code"])
            if "error" not in response or response["error"] != "authorization_pending":
                return response

            await asyncio.sleep(device_code_info["interval"])
