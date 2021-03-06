from setuptools import setup

setup(
    name="beorgtest",
    version="0.0",
    description="удаленный монитор содержимого каталога",
    author="Марк Гуревич",
    packages=[ "beorgtest" ],
    install_requires=[
        "amqp",
        "click",
    ],
    entry_points={
        "console_scripts": [
            "bt-server = beorgtest.server:server",
            "bt-client = beorgtest.client:client",
        ],
    },
)
