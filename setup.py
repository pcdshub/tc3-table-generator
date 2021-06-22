import sys
from os import path

from setuptools import setup, find_packages

# import versioneer

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "requirements.txt")) as requirements_file:
    test_requirements = [
        line
        for line in requirements_file.read().splitlines()
        if not line.startswith("#") and not line.startswith("git+")
    ]

setup(
    name="tc3tg",
    # version=versioneer.get_version(),
    # cmdclass=versioneer.get_cmdclass(),
    author="SLAC National Accelerator Laboratory",
    description="TwinCAT 3 lookup table generator",
    packages=find_packages(where=".", exclude=["doc", ".ci"]),
    entry_points={
        "console_scripts": [
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.TcPOU"],
    },
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
)
