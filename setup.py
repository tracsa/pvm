from setuptools import setup

setup(
    name='pvm',
    version='0.1.0',
    packages=['pvm'],
    include_package_data=True,
    install_requires=[
        'flask',
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
    ],
)
