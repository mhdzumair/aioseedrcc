Usage
=====

Getting Started
---------------

To use AIOSeedrcc, you first need to obtain a token. There are two ways to do this:

1. Login with username and password
2. Authorize with a device code

Login with Username and Password
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import asyncio
    from aioseedrcc import Login

    async def main():
        async with Login('your_email@example.com', 'your_password') as login:
            response = await login.authorize()
            print(response)
            print(login.token)

    asyncio.run(main())

Authorize with Device Code
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import asyncio
    from aioseedrcc import Login

    async def main():
        async with Login() as login:
            device_code = await login.get_device_code()
            print(f"Please go to {device_code['verification_url']} and enter code: {device_code['user_code']}")

            response = await login.authorize(device_code['device_code'])
            print(response)
            print(login.token)

    asyncio.run(main())

Using the Seedr API
-------------------

Once you have a token, you can use the Seedr class to interact with the API:

.. code-block:: python

    import asyncio
    from aioseedrcc import Seedr

    async def main():
        async with Seedr('your_token_here') as seedr:
            # Get user settings
            settings = await seedr.get_settings()
            print(settings)

            # Add a torrent
            torrent = await seedr.add_torrent(magnet_link='your_magnet_link_here')
            print(torrent)

            # List contents
            contents = await seedr.list_contents()
            print(contents)

    asyncio.run(main())



Managing token
--------------

The access token may expire after a certain time and need to be refreshed. However, this process is handled by the module and you don't have to worry about it.

**⚠️ The token is updated after this process and if you are storing the token in a file/database and reading the token from it, It is recommended to update the token in the database/file using the callback function. If you do not update the token in such case, the module will refresh the token in each session which will cost extra request and increase the response time.**

Callback function
^^^^^^^^^^^^^^^^^

You can set a callback function which will be called automatically each time the token is refreshed. You can use such function to deal with the refreshed token.

**✏️ Note: The callback function must be asynchronous and have at least one parameter. The first parameter of the callback function will be the `Seedr` class instance.**

Callback function with single argument
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here is an example of a callback function with a single argument which reads and updates the token in a file called `token.txt`.

.. code-block:: python

    import asyncio
    from aioseedrcc import Seedr

    # Read the token from token.txt
    with open('token.txt', 'r') as f:
        token = f.read().strip()

    # Defining the callback function
    async def after_refresh(seedr):
        with open('token.txt', 'w') as f:
            f.write(seedr.token)

    async def main():
        async with Seedr(token, token_refresh_callback=after_refresh) as account:
            # Your code here
            pass

    asyncio.run(main())


Callback function with multiple arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In situations where you need to pass multiple arguments to the callback function, you can use the `token_refresh_callback_kwargs` argument. This can be useful if your app is dealing with multiple users.

Here is an example of a callback function with multiple arguments which will update the token of a certain user in the database after the token of that user is refreshed.

.. code-block:: python

    import asyncio
    from aioseedrcc import Seedr

    # Defining the callback function
    async def after_refresh(seedr, user_id):
        # Add your code to deal with the database
        print(f'Token of the user {user_id} is updated.')

    async def main():
        # Creating a Seedr object for user 12345
        async with Seedr(token='token', token_refresh_callback=after_refresh, token_refresh_callback_kwargs={'user_id': '12345'}) as account:
            # Your code here
            pass

    asyncio.run(main())


For more detailed information on available methods, please refer to the API Reference section.