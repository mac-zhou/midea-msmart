#!/bin/python
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='msmart',
    version='0.1.17',
    author="mac_zhou",
    author_email="mac.zfl@gmail.com",
    description="A library to control Midea appliances via the Local area network",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mac-zhou/midea-msmart-py",
    packages=setuptools.find_packages(),
    classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
    ],
    entry_points='''
        [console_scripts]
        midea-discover=msmart.cli:discover
    ''',
)
