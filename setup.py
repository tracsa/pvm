#!/usr/bin/env python3
from setuptools import setup

setup(
    name='cacahuate',
    version='0.2.7',
    packages=[
        'cacahuate',
        'cacahuate.http',
        'cacahuate.http.views',
        'cacahuate.auth',
        'cacahuate.auth.backends',
        'cacahuate.auth.hierarchy',
    ],
    entry_points={
        'console_scripts': [
            'cacahuated = cacahuate.cacahuated:main',
        ],
    },
    package_data={'cacahuate': ['grammars/*.g']},
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
        'simplejson',
    ],
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
        'pytest-mock',
    ],
)
