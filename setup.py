#!/bin/python
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
     name='midea',  
     version='0.1.1',
     author="NeoAcheron",
     author_email="master@neoacheron.com",
     description="A library to control Midea appliances via the cloud API",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/NeoAcheron/midea-ac-py",
     packages=setuptools.find_packages(),
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
 )