from setuptools import setup, find_packages
from os import path
from io import open

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="nauta-cli",
    version=0.6,
    description='Utilidad en linea de comandos (CLI) para la gestion del portal cautivo Nauta de Cuba',
    long_description_content_type='text/markdown',
    url='https://github.com/atscub/nauta-cli',
    author='atscub',
    author_email='atscubacel@yahoo.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Internet',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python'
    ],
    keywords='nauta portal cautivo',
    packages=find_packages(),
    install_requires=['requests', 'bs4'],
    entry_points = {
        'console_scripts': ['nauta=nautacli:main'],
    }
)
