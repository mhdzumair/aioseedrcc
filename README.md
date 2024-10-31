<p align="center">
<img src="https://raw.githubusercontent.com/mhdzumair/aioseedrcc/main/docs/images/AIOSeedrCC.png" align="center" height=250 alt="AIOSeedrcc logo" />
</p>

<h2 align='center'>Asynchronous Python API Wrapper for Seedr.cc</h2>

<p align="center">
<a href="https://pypi.org/project/aioseedrcc">
<img src='https://img.shields.io/pypi/v/aioseedrcc.svg'>
</a>
<a href="https://pepy.tech/project/aioseedrcc">
<img src='https://pepy.tech/badge/aioseedrcc'>
</a>
<a href="https://github.com/mhdzumair/aioseedrcc/stargazers">
<img src="https://img.shields.io/github/stars/mhdzumair/aioseedrcc" alt="Stars"/>
</a>
<a href="https://github.com/mhdzumair/aioseedrcc/issues">
<img src="https://img.shields.io/github/issues/mhdzumair/aioseedrcc" alt="Issues"/>
</a>
<br>

## Table of Contents
- [Installation](#installation)
- [Start Guide](#start-guide)
    - [Getting Token](#getting-token)
        - [Logging with Username and Password](#logging-with-username-and-password)
        - [Authorizing with device code](#authorizing-with-device-code)
    - [Basic Examples](#basic-examples)
    - [Managing token](#managing-token)
        - [Callback function](#callback-function)
            - [Function with single argument](#callback-function-with-single-argument)
            - [Function with multiple arguments](#callback-function-with-multiple-arguments)
- [Detailed Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Installation
- Install via [PyPi](https://www.pypi.org/project/aioseedrcc)
    ```bash
    pip install aioseedrcc
    ```

- Install from the source
    ```bash
    pip install git+https://github.com/mhdzumair/aioseedrcc.git
    ```

## Start guide

### Getting Token

There are two methods to get the account token. You can login with username/password or by authorizing with device code. 

#### Logging with Username and Password

This method uses the seedr Chrome extension API.

```python
import asyncio
from aioseedrcc import Login

async def main():
    async with Login('foo@bar.com', 'password') as seedr:
        response = await seedr.authorize()
        print(response)

        # Getting the token 
        print(seedr.token)

asyncio.run(main())
```

### Authorizing with device code

This method uses the seedr kodi API.

**To use this method, generate a device & user code. Paste the user code in https://seedr.cc/devices and authorize with the device code.**

```python
import asyncio
from aioseedrcc import Login

async def main():
    async with Login() as seedr:
        device_code = await seedr.get_device_code()
        # Go to https://seedr.cc/devices and paste the user code
        print(device_code)

        # Authorize with device code
        response = await seedr.authorize(device_code['device_code'])
        print(response)

        # Getting the token
        print(seedr.token)

asyncio.run(main())
```

**✏️ Note: You must use the token from the instance variable 'token' instead of the 'access_token' or 'refresh_token' from the response.**

### Basic Examples

For all available methods, please refer to the [documentation](https://aioseedrcc.readthedocs.org/en/latest/). Also, it is recommended to set a callback function, read more about it [here](#managing-token).

```python
import asyncio
from aioseedrcc import Seedr

async def main():
    async with Seedr(token='token') as account:
        # Getting user settings
        settings = await account.get_settings()
        print(settings)

        # Adding torrent
        response = await account.add_torrent('magnetlink')
        print(response)

        # Listing folder contents
        contents = await account.list_contents()
        print(contents)

asyncio.run(main())
```

### Managing token

The access token may expire after a certain time and need to be refreshed. However, this process is handled by the module and you don't have to worry about it. 

**⚠️ The token is updated after this process and if you are storing the token in a file/database and reading the token from it, It is recommended to update the token in the database/file using the callback function. If you do not update the token in such case, the module will refresh the token in each session which will cost extra request and increase the response time.**


### Callback function

You can set a callback function which will be called automatically each time the token is refreshed. You can use such function to deal with the refreshed token.

**✏️ Note: The callback function must be asynchronous and have at least one parameter. The first parameter of the callback function will be the `Seedr` class instance.**

#### Callback function with single argument

Here is an example of a callback function with a single argument which reads and updates the token in a file called `token.txt`.

```python
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
```

#### Callback function with multiple arguments

In situations where you need to pass multiple arguments to the callback function, you can use the `token_refresh_callback_kwargs` argument. This can be useful if your app is dealing with multiple users.

Here is an example of a callback function with multiple arguments which will update the token of a certain user in the database after the token of that user is refreshed.

```python
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
```

## Documentation

The detailed documentation of each method is available [here](https://aioseedrcc.readthedocs.org/en/latest/).

## Contributing

Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See [LICENSE](https://github.com/mhdzumair/aioseedrcc/blob/main/LICENSE) for more information.
