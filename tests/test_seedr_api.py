import os
import pytest
import asyncio
from dotenv import load_dotenv
from aioseedrcc.login import Login
from aioseedrcc.seedr import Seedr

# Load environment variables from a .env file
load_dotenv()

# Get credentials from environment variables
EMAIL = os.getenv("SEEDR_EMAIL")
PASSWORD = os.getenv("SEEDR_PASSWORD")

if not EMAIL or not PASSWORD:
    pytest.skip(
        "Seedr credentials not found in environment variables", allow_module_level=True
    )


@pytest.fixture(scope="function")
async def seedr_instance():
    """Fixture that provides an authenticated Seedr instance"""
    async with Login(EMAIL, PASSWORD) as login:
        auth_response = await login.authorize()
        if "access_token" not in auth_response:
            pytest.fail("Failed to authenticate with Seedr")
        token = login.token

        async with Seedr(token) as seedr_instance:
            yield seedr_instance


@pytest.mark.asyncio
async def test_get_settings(seedr_instance):
    response = await seedr_instance.get_settings()
    assert "result" in response
    assert response["result"] is True


@pytest.mark.asyncio
async def test_get_memory_bandwidth(seedr_instance):
    response = await seedr_instance.get_memory_bandwidth()
    assert "bandwidth_used" in response
    assert "space_max" in response


@pytest.mark.asyncio
async def test_list_contents(seedr_instance):
    response = await seedr_instance.list_contents()
    assert "folders" in response
    assert "files" in response


@pytest.mark.asyncio
async def test_add_and_delete_folder(seedr_instance):
    # Add a new folder
    folder_name = "Test Folder"
    add_response = await seedr_instance.add_folder(folder_name)
    assert "result" in add_response
    assert add_response["result"] is True

    # Verify the folder was added
    list_response = await seedr_instance.list_contents()
    folders = list_response["folders"]
    assert any(folder["name"] == folder_name for folder in folders)

    # Get the folder ID
    folder_id = next(
        folder["id"] for folder in folders if folder["name"] == folder_name
    )

    # Delete the folder
    delete_response = await seedr_instance.delete_item(folder_id, "folder")
    assert "result" in delete_response
    assert delete_response["result"] is True

    # Verify the folder was deleted
    list_response = await seedr_instance.list_contents()
    folders = list_response["folders"]
    assert not any(folder["id"] == folder_id for folder in folders)


@pytest.mark.asyncio
async def test_add_and_delete_torrent(seedr_instance):
    # Use a small, legal torrent for testing
    magnet_link = "magnet:?xt=urn:btih:dd8255ecdc7ca55fb0bbf81323d87062db1f6d1c&dn=Big+Buck+Bunny&tr=udp%3A%2F%2Fexplodie.org%3A6969&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969&tr=udp%3A%2F%2Ftracker.empire-js.us%3A1337&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=wss%3A%2F%2Ftracker.btorrent.xyz&tr=wss%3A%2F%2Ftracker.fastcast.nz&tr=wss%3A%2F%2Ftracker.openwebtorrent.com&ws=https%3A%2F%2Fwebtorrent.io%2Ftorrents%2F&xs=https%3A%2F%2Fwebtorrent.io%2Ftorrents%2Fbig-buck-bunny.torrent"

    # Add the torrent
    add_response = await seedr_instance.add_torrent(magnet_link=magnet_link)
    assert "result" in add_response
    assert add_response["result"] is True
    assert add_response["title"] == "Big Buck Bunny"
    assert add_response["torrent_hash"] == "dd8255ecdc7ca55fb0bbf81323d87062db1f6d1c"

    # Wait for the torrent to be processed
    await asyncio.sleep(5)

    # List contents to find the added torrent
    list_response = await seedr_instance.list_contents()
    torrents = list_response.get("torrents", [])

    if not torrents:
        # If no active torrents, check completed ones
        folders = list_response.get("folders", [])
        assert any("Big Buck Bunny" in folder["name"] for folder in folders)
        file_to_delete = next(
            folder for folder in folders if "Big Buck Bunny" == folder["name"]
        )

        # Delete the file
        delete_response = await seedr_instance.delete_item(file_to_delete["id"], "file")
    else:
        assert any("Big Buck Bunny" in torrent["name"] for torrent in torrents)
        torrent_to_delete = next(
            torrent for torrent in torrents if "Big Buck Bunny" in torrent["name"]
        )

        # Delete the torrent
        delete_response = await seedr_instance.delete_item(
            torrent_to_delete["id"], "torrent"
        )

    assert "result" in delete_response
    assert delete_response["result"] is True


@pytest.mark.asyncio
async def test_get_devices(seedr_instance):
    response = await seedr_instance.get_devices()
    assert "result" in response
    assert response["result"] is True
    assert "devices" in response
