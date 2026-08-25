import os
import requests
from pathlib import Path
from package.module import something

class User:
    def login(self, name):
        print(name)


def main():
    user = User()
    user.login("Anupriya")


main()

async def fetch_data(url):
    print(url)


def outer_function():
    def inner_function(value):
        print(value)

    inner_function("test")


class Outer:
    class Inner:
        def inner_method(self):
            print("hello")