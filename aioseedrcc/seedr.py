"""
This module provides an asynchronous interface to interact with the Seedr.cc API.

It contains the Seedr class which encapsulates all the functionality to manage
a Seedr account, including adding torrents, managing files and folders, and
handling account settings.
"""

import os
from base64 import b64decode
from typing import Optional, Callable, Dict, Any, Tuple

import aiohttp
import aiofiles
from aiohttp import FormData

from aioseedrcc.exception import SeedrException
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
        session_args (Optional[Dict[str, Any]]): Optional arguments to pass to the aiohttp ClientSession.
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
        session_args: Optional[Dict[str, Any]] = None,
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

        # Default session arguments
        self._session_args = session_args or {
            "timeout": aiohttp.ClientTimeout(total=10),
            "connector": aiohttp.TCPConnector(limit=10, ttl_dns_cache=300),
        }
        self._session = aiohttp.ClientSession(**self._session_args)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def _make_request(
        self,
        method: str,
        func: str,
        data: Optional[Dict[str, Any] | FormData] = None,
        retry_count: int = 1,
    ) -> Dict[str, Any]:
        """
        Make a request to the Seedr API with automatic token refresh handling.

        Args:
            method: HTTP method ("GET" or "POST")
            func: API function name
            data: Optional POST data
            files: Optional files to upload
            retry_count: Number of retries attempted (internal use)

        Returns:
            Dict[str, Any]: API response as dictionary

        Raises:
            SeedrException: If the API request fails after retries
        """
        if retry_count > 2:
            raise SeedrException("Max retry attempts reached")

        params = {"access_token": self._access_token, "func": func}

        try:
            async with self._session.request(
                method, self.BASE_URL, params=params, data=data
            ) as response:
                response.raise_for_status()
                result = await response.json(content_type=None)

                # Handle expired token
                if isinstance(result, dict) and result.get("error") == "expired_token":
                    if retry_count > 1:
                        raise SeedrException("Token refresh failed")

                    refresh_response = await self.refresh_token()
                    if "error" in refresh_response:
                        raise SeedrException(
                            f"Token refresh failed: {refresh_response['error']}"
                        )

                    # Retry the request with new token
                    return await self._make_request(method, func, data, retry_count + 1)

                return result

        except aiohttp.ClientError as e:
            raise SeedrException(f"HTTP request failed: {str(e)}") from e
        except ValueError as e:
            raise SeedrException(f"Invalid JSON response: {str(e)}") from e
        except Exception as e:
            raise SeedrException(f"Request failed: {str(e)}") from e

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
        return await self._make_request("GET", "test")

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
        try:
            if self._refresh_token:
                url = "https://www.seedr.cc/oauth_test/token.php"
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": "seedr_chrome",
                }
                async with self._session.post(url, data=data) as response:
                    response.raise_for_status()
                    response_json = await response.json(content_type=None)
            else:
                async with Login(session=self._session) as login:
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
            else:
                raise SeedrException("No access token in refresh response")

        except aiohttp.ClientError as e:
            raise SeedrException(f"Token refresh request failed: {str(e)}") from e
        except Exception as e:
            raise SeedrException(f"Token refresh failed: {str(e)}") from e

    async def get_settings(self) -> Dict[str, Any]:
        """
        Retrieve the user's account settings.

        Returns:
            Dict[str, Any]: The API response containing the user's settings.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     settings = await seedr.get_settings()
            ...     print(settings)
        """
        return await self._make_request("GET", "get_settings")

    async def get_memory_bandwidth(self) -> Dict[str, Any]:
        """
        Retrieve the memory and bandwidth usage information.

        Returns:
            Dict[str, Any]: The API response containing memory and bandwidth usage data.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     usage = await seedr.get_memory_bandwidth()
            ...     print(usage)
        """
        return await self._make_request("GET", "get_memory_bandwidth")

    async def _download_remote_torrent(self, url: str) -> bytes:
        """
        Download a torrent file from a remote URL.

        Args:
            url (str): The URL of the torrent file.

        Returns:
            bytes: The content of the torrent file.

        Raises:
            SeedrException: If the download fails.
        """
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                return await response.read()
        except aiohttp.ClientError as e:
            raise SeedrException(
                f"Failed to download remote torrent file: {str(e)}"
            ) from e

    async def _read_local_torrent(self, file_path: str) -> Tuple[bytes, str]:
        """
        Read a torrent file from the local filesystem.

        Args:
            file_path (str): Path to the local torrent file.

        Returns:
            Tuple[bytes, str]: The content of the torrent file and its filename.

        Raises:
            SeedrException: If reading the file fails.
        """
        try:
            async with aiofiles.open(file_path, mode="rb") as file:
                content = await file.read()
                return content, os.path.basename(file_path)
        except IOError as e:
            raise SeedrException(f"Failed to read local torrent file: {str(e)}") from e

    def _create_torrent_form(
        self, torrent_content: bytes, filename: str, data: Dict[str, Any]
    ) -> aiohttp.FormData:
        """
        Create a FormData object with torrent file and additional data.

        Args:
            torrent_content (bytes): The content of the torrent file.
            filename (str): Name of the torrent file.
            data (Dict[str, Any]): Additional form data.

        Returns:
            aiohttp.FormData: The prepared form data.
        """
        form = aiohttp.FormData()

        # Add the torrent file
        form.add_field(
            "torrent_file",
            torrent_content,
            filename=filename,
            content_type="application/x-bittorrent",
        )

        # Add other form fields
        for key, value in data.items():
            if value is not None:
                form.add_field(key, str(value))

        return form

    async def add_torrent(
        self,
        magnet_link: Optional[str] = None,
        torrent_file: Optional[str] = None,
        wishlist_id: Optional[str] = None,
        folder_id: str = "-1",
    ) -> Dict[str, Any]:
        """
        Add a torrent to the Seedr account for downloading.

        Args:
            magnet_link (Optional[str]): The magnet link of the torrent.
            torrent_file (Optional[str]): Remote or local path of the torrent file.
            wishlist_id (Optional[str]): The wishlist ID to add the torrent to.
            folder_id (str): The folder ID to add the torrent to. Default to '-1' (root folder).

        Returns:
            Dict[str, Any]: The API response after adding the torrent.

        Raises:
            SeedrException: If there's an error reading the torrent file or making the request.

        Example:
            Adding a torrent using a magnet link:
                >>> async with Seedr(token='your_token_here') as seedr:
                ...     result = await seedr.add_torrent(magnet_link='magnet:?xt=urn:btih:...')
                ...     print(result)

            Adding a torrent from a local file:
                >>> async with Seedr(token='your_token_here') as seedr:
                ...     result = await seedr.add_torrent(torrent_file='/path/to/file.torrent')
                ...     print(result)
        """
        data = {
            "torrent_magnet": magnet_link,
            "wishlist_id": wishlist_id,
            "folder_id": folder_id,
        }

        if not torrent_file:
            return await self._make_request("POST", "add_torrent", data=data)

        try:
            # Handle remote or local torrent file
            if torrent_file.startswith(("http://", "https://")):
                content = await self._download_remote_torrent(torrent_file)
                filename = "torrent_file"
            else:
                content, filename = await self._read_local_torrent(torrent_file)

            # Create form data with torrent file and additional data
            form = self._create_torrent_form(content, filename, data)

            return await self._make_request("POST", "add_torrent", data=form)

        except Exception as e:
            raise SeedrException(f"Error processing torrent file: {str(e)}") from e

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
        return await self._make_request("POST", "scan_page", data={"url": url})

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
        data = {"archive_arr": f'[{{"type":"folder","id":{folder_id}}}]'}
        return await self._make_request("POST", "create_empty_archive", data=data)

    async def fetch_file(self, file_id: str) -> Dict[str, Any]:
        """
        Create a download link for a file.

        Args:
            file_id (str): The ID of the file to fetch.

        Returns:
            Dict[str, Any]: The API response containing the download link.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     file_info = await seedr.fetch_file('12345')
            ...     print(file_info)
        """
        data = {"folder_file_id": file_id}
        return await self._make_request("POST", "fetch_file", data=data)

    async def delete_item(self, item_id: str, item_type: str) -> Dict[str, Any]:
        """
        Delete a file, folder, or torrent.

        Args:
            item_id (str): The ID of the item to delete.
            item_type (str): The type of the item ('file', 'folder', or 'torrent').

        Returns:
            Dict[str, Any]: The API response after deleting the item.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.delete_item('12345', 'file')
            ...     print(result)
        """
        data = {"delete_arr": f'[{{"type":"{item_type}","id":{item_id}}}]'}
        return await self._make_request("POST", "delete", data=data)

    async def rename_item(
        self, item_id: str, new_name: str, item_type: str
    ) -> Dict[str, Any]:
        """
        Rename a file or folder.

        Args:
            item_id (str): The ID of the item to rename.
            new_name (str): The new name for the item.
            item_type (str): The type of the item ('file' or 'folder').

        Returns:
            Dict[str, Any]: The API response after renaming the item.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.rename_item('12345', 'New Name', 'file')
            ...     print(result)
        """
        data = {"rename_to": new_name, f"{item_type}_id": item_id}
        return await self._make_request("POST", "rename", data=data)

    async def list_contents(self, folder_id: str = "0") -> Dict[str, Any]:
        """
        List the contents of a folder.

        Args:
            folder_id (str): The ID of the folder to list. Defaults to '0' (root folder).

        Returns:
            Dict[str, Any]: The API response containing the folder contents.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     contents = await seedr.list_contents()
            ...     print(contents)
        """
        data = {"content_type": "folder", "content_id": folder_id}
        return await self._make_request("POST", "list_contents", data=data)

    async def add_folder(self, name: str) -> Dict[str, Any]:
        """
        Create a new folder.

        Args:
            name (str): The name of the new folder.

        Returns:
            Dict[str, Any]: The API response after creating the folder.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     result = await seedr.add_folder('New Folder')
            ...     print(result)
        """
        data = {"name": name}
        return await self._make_request("POST", "add_folder", data=data)

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
        data = {"id": wishlist_id}
        return await self._make_request("POST", "remove_wishlist", data=data)

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
        data = {"search_query": query}
        return await self._make_request("POST", "search_files", data=data)

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
        data = {"setting": "fullname", "password": password, "fullname": name}
        return await self._make_request("POST", "user_account_modify", data=data)

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
        data = {
            "setting": "password",
            "password": old_password,
            "new_password": new_password,
            "new_password_repeat": new_password,
        }
        return await self._make_request("POST", "user_account_modify", data=data)

    async def get_devices(self) -> Dict[str, Any]:
        """
        Get the list of devices connected to the Seedr account.

        Returns:
            Dict[str, Any]: The API response containing the list of connected devices.

        Example:
            >>> async with Seedr(token='your_token_here') as seedr:
            ...     devices = await seedr.get_devices()
            ...     print(devices)
        """
        return await self._make_request("GET", "get_devices")
