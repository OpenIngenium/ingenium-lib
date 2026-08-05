import os
from setuptools import setup, find_packages


def get_dependencies():
    deps=[
        'rich>=14.0.0',
        'requests>=2.34.2',
        'PyJWT>=2.13.0',
        'openpyxl>=3.1.5',
        'deepdiff>=9.1.0',
    ]
    return deps

setup(
    name='ing_lib',
    packages=find_packages(),
    install_requires=get_dependencies(),
    description='Python libraries supporting OpenIngenium',
    version='0.1.0',
    python_requires='>=3.10',
    entry_points = {
    },
    author='Christopher Swan',
    author_email='open-ingenium@jpl.nasa.gov',
    url='https://github.com/OpenIngenium/ingenium-lib',
    classifiers=[
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
    ],
)