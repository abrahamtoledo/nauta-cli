from setuptools import setup, find_packages
from os import path
from io import open


about = {}
with open("nautacli/__about__.py") as fp:
    exec(fp.read(), about)


here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name=about["__name__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=about["__url__"],
    author=about["__author__"],
    author_email=about["__email__"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python"
    ],
    keywords="nauta portal cautivo",
    packages=find_packages(),
    install_requires=["requests", "bs4"],
    entry_points = {
        "console_scripts": [about["__cli__"] + "=nautacli:main"],
    }
)
