import pathlib
from setuptools import setup

root = pathlib.Path(__file__).parent

with (root / 'README.md').open() as f:
    readme = f.read()

with (root / 'requirements.txt').open() as f:
    requirements = [line for line in f.readlines()]

setup(
    name='intuno',
    version='0.1.0',
    description='Terminal-based note tuning application for pianos and other instruments',
    long_description=readme,
    author='Louka Dlagnekov',
    author_email='loukad@gmail.com',
    url='https://github.com/loukad/intuno',
    packages=['intuno'],
    install_requires=requirements,
    python_requires='>=3.7',
    entry_points={
        'console_scripts': ['intuno=intuno.__main__:main']
    }
)
