#!/usr/bin/env python3
from setuptools import setup
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()

setup(
    name='cacahuate',
    description='The process virtual machine',
    long_description=long_description,
    url='https://github.com/tracsa/cacahuate',

    version='2.0.0-rc4',

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

    package_data={'cacahuate': ['grammars/*.g']},

    entry_points={
        'console_scripts': [
            'cacahuated = cacahuate.cacahuated:main',
        ],
    },

    include_package_data=True,

    install_requires=[
        'Flask-Coralillo',
        'Flask-Cors',
        'Flask_PyMongo',
        'case_conversion',
        'coralillo >= 0.8',
        'flask >= 1.0',
        'itacate',
        'lark-parser',
        'ldap3',
        'pika',
        'simplejson',
        'requests',
    ],

    setup_requires=[
        'pytest-runner',
    ],

    tests_require=[
        'pytest',
        'pytest-mock',
    ],
)
