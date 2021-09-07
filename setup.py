import pathlib
from setuptools import setup

root = pathlib.Path(__file__).parent

with (root / 'intuno' / '__init__.py').open() as f:
    version = [line.split(' = ')[-1].strip().strip("'") for line in f.readlines() \
               if line.startswith('__version__')][0]

with (root / 'README.md').open() as f:
    readme = f.read()

with (root / 'requirements.txt').open() as f:
    requirements = [line for line in f.readlines()]

setup(
    name='intuno',
    version=version,
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
