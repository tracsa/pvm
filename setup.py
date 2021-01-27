#!/usr/bin/env python3
from setuptools import setup
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()

with open(path.join(here, 'cacahuate', 'version.txt')) as f:
    version = f.read().strip()

setup(
    name='cacahuate',
    description='The process virtual machine',
    long_description=long_description,
    url='https://github.com/tracsa/cacahuate',

    version=version,

    author='Abraham Toriz Cruz',
    author_email='categulario@gmail.com',
    license='MIT',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='process',

    packages=[
        'cacahuate',
        'cacahuate.http',
        'cacahuate.http.views',
        'cacahuate.auth',
        'cacahuate.auth.backends',
        'cacahuate.auth.hierarchy',
    ],

    package_data={
        'cacahuate': ['grammars/*.g', 'xml/*.rng', 'version.txt', 'templates/*.html'],
    },

    entry_points={
        'console_scripts': [
            'cacahuated = cacahuate.main:main',
            'xml_validate = cacahuate.main:xml_validate',
            'rng_path = cacahuate.main:rng_path',
        ],
    },

    install_requires=[
        'Flask-Coralillo',
        'Flask-Cors',
        'Flask_PyMongo < 2.0',
        'case_conversion',
        'coralillo >= 0.8, < 1.0',
        'flask >= 1.0',
        'itacate',
        'lark-parser >= 0.6',
        'ldap3',
        'pika >= 1.0',
        'simplejson',
        'requests',
        'passlib',
        'yuid',
        'jsonpath-rw',
        'jinja2',
        'werkzeug < 1.0',
    ],

    setup_requires=[
        'pytest-runner',
    ],

    tests_require=[
        'pytest',
        'pytest-mock',
    ],
)
