import os
from setuptools import setup, find_packages


def get_dependencies():
    deps=[
        'rich>=14.0.0',
    ]
    return deps

setup(
    name='ing_lib',
    packages=find_packages(),
    install_requires=get_dependencies(),
    description='Python libraries supporting OpenIngenium',
    version='0.1.0',
    python_requires='>=3.9',
    entry_points = {
    },
    author='Christopher Swan',
    author_email='open-ingenium@jpl.nasa.gov',
    url='https://github.com/OpenIngenium/ingenium-lib'
)