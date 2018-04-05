# The Process Virtual Machine

[![Build Status](https://travis-ci.org/tracsa/cacahuate.svg?branch=master)](https://travis-ci.org/tracsa/cacahuate)

This project defines storage for an abstract _process_ in a company, and
implements a virtual machine that keeps track of the execution of instances of
the process.

## Develop

You will need the redis database, and rabbitmq for this to work

* `git clone https://github.com/tracsa/cacahuate.git && cd cacahuate`
* `virtualenv -p /usr/bin/python3 .env`
* `echo "export CACAHUATE_SETTINGS=$(pwd)/settings_develop.py" >> .env/bin/activate`
* `touch settings_develop.py`
* `source .env/bin/activate`
* `pip install -r requirements.txt`
* `pytest`

## The Cacahuate REST API

In this same repository you will find a flask application that exposes a REST
api for controling Cacahuate.

**How to run**

* `FLASK_APP=cacahuate.http.wsgi flask run`
