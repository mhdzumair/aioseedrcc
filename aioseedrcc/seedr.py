"""
This module provides an asynchronous interface to interact with the Seedr.cc API.

It contains the Seedr class which encapsulates all the functionality to manage
a Seedr account, including adding torrents, managing files and folders, and
handling account settings.
"""

import re
from base64 import b64decode
from functools import wraps
from typing import Optional, Callable, Dict, Any

import httpx

from aioseedrcc.login import Login
from aioseedrcc.login import create_token


class Seedr:
    """
    Asynchronous client for interacting with the Seedr.cc API.

    This class provides methods to perform various operations on a Seedr account,
    such as adding torrents, managing files and folders, and handling account settings.

    Attributes:
        token (str): The authentication token for the Seedr account.

    Args:
        token (str): The authentication token for the Seedr account.
        httpx_client_args (Optional[Dict[str, Any]]): Optional arguments to pass to the HTTPX client.
        token_refresh_callback: Callable[[Seedr, **Any], Coroutine[Any, Any, None]] - async callback function to be called after token refresh
        token_refresh_callback_kwargs: Dict[str, Any] - custom arguments to be passed to the token refresh callback function

    Example:
        >>> async with Seedr(token='your_token_here') as seedr:
        ...     settings = await seedr.get_settings()
        ...     print(settings)
    """

    BASE_URL = "https://www.seedr.cc/oauth_test/resource.php"

    def __init__(
        self,
        token: str,
        httpx_client_args: Optional[Dict[str, Any]] = None,
        token_refresh_callback: Optional[Callable] = None,
        token_refresh_callback_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.token = token
        token_dict = eval(b64decode(token))
        self._token_refresh_callback = token_refresh_callback
        self._token_refresh_callback_kwargs = token_refresh_callback_kwargs or {}

        self._access_token = token_dict["access_token"]
        self._refresh_token = token_dict.get("refresh_token")
        self._device_code = token_dict.get("device_code")
        httpx_client_args = httpx_client_args or {
            "timeout": 10,
            "transport": httpx.AsyncHTTPTransport(retries=3),
        }
        self._client = httpx.AsyncClient(**httpx_client_args)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    @staticmethod
    def auto_refresh(func):
        """
        Decorator to automatically refresh the token if it's expired.

        If the API returns an 'expired_token' error, this decorator will attempt to
        refresh the token and retry the original request.

        Args:
            func: The async function to wrap.

        Returns:
            A wrapped version of the input function that handles token refreshing.
        """

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            response = await func(self, *args, **kwargs)
            try:
                response_json = response.json()
            except httpx.HTTPError:
                return {"result": False, "code": 400, "error": response.text}

            if "error" in response_json and response_json["error"] == "expired_token":
                refresh_response = await self.refresh_token()

                if "error" in refresh_response:
                    return refresh_response

                response = await func(self, *args, **kwargs)
                response_json = response.json()

            return response_json

        return wrapper

    async def test_token(self) -> Dict[str, Any]:
        """
        Test the validity of the current token.

        Returns:
            Dict[str, Any]: The API response indicating whether the token is valid.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.test_token()
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "test"}

        response = await self._client.get(self.BASE_URL, params=params)
        return response.json()

    async def refresh_token(self) -> Dict[str, Any]:
        """
        Refresh the expired token.

        This method is called automatically when needed, but can also be called manually.

        Returns:
            Dict[str, Any]: The API response containing the new token information.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     new_token_info = await seedr.refresh_token()
            ...     print(seedr.token)  # This will be the new token
        """
        if self._refresh_token:
            url = "https://www.seedr.cc/oauth_test/token.php"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": "seedr_chrome",
            }
            response = await self._client.post(url, data=data)
            response_json = response.json()
        else:
            login = Login()
            response_json = await login.authorize(device_code=self._device_code)

        if "access_token" in response_json:
            self._access_token = response_json["access_token"]
            self.token = create_token(
                response_json, self._refresh_token, self._device_code
            )
            if self._token_refresh_callback:
                await self._token_refresh_callback(
                    self, **self._token_refresh_callback_kwargs
                )

        return response_json

    @auto_refresh
    async def get_settings(self) -> httpx.Response:
        """
        Retrieve the user's account settings.

        Returns:
            httpx.Response: The API response containing the user's settings.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     settings = await seedr.get_settings()
            ...     print(settings.json())
        """
        params = {"access_token": self._access_token, "func": "get_settings"}
        return await self._client.get(self.BASE_URL, params=params)

    @auto_refresh
    async def get_memory_bandwidth(self) -> httpx.Response:
        """
        Retrieve the memory and bandwidth usage information.

        Returns:
            httpx.Response: The API response containing memory and bandwidth usage data.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     usage = await seedr.get_memory_bandwidth()
            ...     print(usage.json())
        """
        params = {"access_token": self._access_token, "func": "get_memory_bandwidth"}
        return await self._client.get(self.BASE_URL, params=params)

    @auto_refresh
    async def add_torrent(
        self,
        magnet_link: Optional[str] = None,
        torrent_file: Optional[str] = None,
        wishlist_id: Optional[str] = None,
        folder_id: str = "-1",
    ) -> httpx.Response:
        """
        Add a torrent to the Seedr account for downloading.

        Args:
            magnet_link (Optional[str]): The magnet link of the torrent.
            torrent_file (Optional[str]): Remote or local path of the torrent file.
            wishlist_id (Optional[str]): The wishlist ID to add the torrent to.
            folder_id (str): The folder ID to add the torrent to. Default to '-1' (root folder).

        Returns:
            httpx.Response: The API response after adding the torrent.

        Example:
            Adding a torrent using a magnet link:
                >>> async with Seedr(token='your_token_here') as seedr:
                ...     result = await seedr.add_torrent(magnet_link='magnet:?xt=urn:btih:...')
                ...     print(result.json())

            Adding a torrent from a local file:
                >>> async with Seedr(token='your_token_here') as seedr:
                ...     result = await seedr.add_torrent(torrent_file='/path/to/file.torrent')
                ...     print(result.json())
        """
        params = {"access_token": self._access_token, "func": "add_torrent"}
        data = {
            "torrent_magnet": magnet_link,
            "wishlist_id": wishlist_id,
            "folder_id": folder_id,
        }
        files = {}

        if torrent_file:
            if re.match(r"^https?://", torrent_file):
                file_response = await self._client.get(torrent_file)
                files = {"torrent_file": ("torrent_file", file_response.content)}
            else:
                files = {"torrent_file": open(torrent_file, "rb")}

        return await self._client.post(
            self.BASE_URL, params=params, data=data, files=files
        )

    @auto_refresh
    async def scan_page(self, url: str) -> Dict[str, Any]:
        """
        Scan a page and return a list of torrents.

        This method can be used to fetch magnet links from torrent pages.

        Args:
            url (str): The URL of the page to scan.

        Returns:
            Dict[str, Any]: The API response containing the scan results.

        Example:
            >>> async with Seedr(token='your_token') as seedr:
            ...     result = await seedr.scan_page('https://1337x.to/torrent/1234')
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "scan_page"}
        data = {"url": url}
        response = await self._client.post(self.BASE_URL, params=params, data=data)
        return response.json()

    @auto_refresh
    async def create_archive(self, folder_id: str) -> Dict[str, Any]:
        """
        Create an archive link of a folder.

        Args:
            folder_id (str): The ID of the folder to archive.

        Returns:
            Dict[str, Any]: The API response containing the archive link.

        Example:
            >>> async with Seedr(token='your_token') as seedr:
            ...     result = await seedr.create_archive('12345')
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "create_empty_archive"}
        data = {"archive_arr": f'[{{"type":"folder","id":{folder_id}}}]'}
        response = await self._client.post(self.BASE_URL, params=params, data=data)
        return response.json()

    @auto_refresh
    async def fetch_file(self, file_id: str) -> httpx.Response:
        """
        Create a download link for a file.

        Args:
            file_id (str): The ID of the file to fetch.

        Returns:
            httpx.Response: The API response containing the download link.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     file_info = await seedr.fetch_file('12345')
            ...     print(file_info.json())
        """
        params = {"access_token": self._access_token, "func": "fetch_file"}
        data = {"folder_file_id": file_id}
        return await self._client.post(self.BASE_URL, params=params, data=data)

    @auto_refresh
    async def delete_item(self, item_id: str, item_type: str) -> httpx.Response:
        """
        Delete a file, folder, or torrent.

        Args:
            item_id (str): The ID of the item to delete.
            item_type (str): The type of the item ('file', 'folder', or 'torrent').

        Returns:
            httpx.Response: The API response after deleting the item.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.delete_item('12345', 'file')
            ...     print(result.json())
        """
        params = {"access_token": self._access_token, "func": "delete"}
        data = {"delete_arr": f'[{{"type":"{item_type}","id":{item_id}}}]'}
        return await self._client.post(self.BASE_URL, params=params, data=data)

    @auto_refresh
    async def rename_item(
        self, item_id: str, new_name: str, item_type: str
    ) -> httpx.Response:
        """
        Rename a file or folder.

        Args:
            item_id (str): The ID of the item to rename.
            new_name (str): The new name for the item.
            item_type (str): The type of the item ('file' or 'folder').

        Returns:
            httpx.Response: The API response after renaming the item.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.rename_item('12345', 'New Name', 'file')
            ...     print(result.json())
        """
        params = {"access_token": self._access_token, "func": "rename"}
        data = {"rename_to": new_name, f"{item_type}_id": item_id}
        return await self._client.post(self.BASE_URL, params=params, data=data)

    @auto_refresh
    async def list_contents(self, folder_id: str = "0") -> httpx.Response:
        """
        List the contents of a folder.

        Args:
            folder_id (str): The ID of the folder to list. Defaults to '0' (root folder).

        Returns:
            httpx.Response: The API response containing the folder contents.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     contents = await seedr.list_contents()
            ...     print(contents.json())
        """
        params = {"access_token": self._access_token, "func": "list_contents"}
        data = {"content_type": "folder", "content_id": folder_id}
        return await self._client.post(self.BASE_URL, params=params, data=data)

    @auto_refresh
    async def add_folder(self, name: str) -> httpx.Response:
        """
        Create a new folder.

        Args:
            name (str): The name of the new folder.

        Returns:
            httpx.Response: The API response after creating the folder.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.add_folder('New Folder')
            ...     print(result.json())
        """
        params = {"access_token": self._access_token, "func": "add_folder"}
        data = {"name": name}
        return await self._client.post(self.BASE_URL, params=params, data=data)

    @auto_refresh
    async def delete_wishlist(self, wishlist_id: str) -> Dict[str, Any]:
        """
        Delete an item from the wishlist.

        Args:
            wishlist_id (str): The ID of the wishlist item to delete.

        Returns:
            Dict[str, Any]: The API response after deleting the wishlist item.

        Example:
            >>> async with Seedr(token='your_token') as seedr:
            ...     result = await seedr.delete_wishlist('12345')
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "remove_wishlist"}
        data = {"id": wishlist_id}
        response = await self._client.post(self.BASE_URL, params=params, data=data)
        return response.json()

    @auto_refresh
    async def search_files(self, query: str) -> Dict[str, Any]:
        """
        Search for files in the Seedr account.

        Args:
            query (str): The search query.

        Returns:
            Dict[str, Any]: The API response containing the search results.

        Example:
            >>> async with Seedr(token='your_token') as seedr:
            ...     result = await seedr.search_files('example file')
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "search_files"}
        data = {"search_query": query}
        response = await self._client.post(self.BASE_URL, params=params, data=data)
        return response.json()

    @auto_refresh
    async def change_name(self, name: str, password: str) -> Dict[str, Any]:
        """
        Change the name of the Seedr account.

        Args:
            name (str): The new name for the account.
            password (str): The current password of the account.

        Returns:
            Dict[str, Any]: The API response after changing the name.

        Example:
            >>> async with Seedr(token='your_token') as seedr:
            ...     result = await seedr.change_name('New Name', 'current_password')
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "user_account_modify"}
        data = {"setting": "fullname", "password": password, "fullname": name}
        response = await self._client.post(self.BASE_URL, params=params, data=data)
        return response.json()

    @auto_refresh
    async def change_password(
        self, old_password: str, new_password: str
    ) -> Dict[str, Any]:
        """
        Change the password of the Seedr account.

        Args:
            old_password (str): The current password of the account.
            new_password (str): The new password to set.

        Returns:
            Dict[str, Any]: The API response after changing the password.

        Example:
            >>> async with Seedr(token='your_token') as seedr:
            ...     result = await seedr.change_password('old_password', 'new_password')
            ...     print(result)
        """
        params = {"access_token": self._access_token, "func": "user_account_modify"}
        data = {
            "setting": "password",
            "password": old_password,
            "new_password": new_password,
            "new_password_repeat": new_password,
        }
        response = await self._client.post(self.BASE_URL, params=params, data=data)
        return response.json()

    @auto_refresh
    async def get_devices(self) -> httpx.Response:
        """
        Get the list of devices connected to the Seedr account.

        Returns:
            httpx.Response: The API response containing the list of connected devices.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     devices = await seedr.get_devices()
            ...     print(devices.json())
        """
        params = {"access_token": self._access_token, "func": "get_devices"}
        return await self._client.get(self.BASE_URL, params=params)
