#!/usr/bin/env python3
from setuptools import setup

setup(
    name='pvm',
    version='0.2.4',
    packages=[
        'pvm',
        'pvm.http',
        'pvm.auth',
        'pvm.auth.backends',
        'pvm.auth.hierarchy',
    ],
    package_data={'pvm': ['grammars/*.g']},
    include_package_data=True,
    install_requires=[
        'Flask-Coralillo',
        'Flask-Cors',
        'Flask_PyMongo',
        'case_conversion',
        'coralillo',
        'flask',
        'itacate',
        'lark-parser',
        'ldap3',
        'pika',
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
        'pytest-mock',
    ],
)
