# The Process Virtual Machine

[![Build Status](https://travis-ci.org/tracsa/pvm.svg?branch=master)](https://travis-ci.org/tracsa/pvm)

This project defines storage for an abstract _process_ in a company, and
implements a virtual machine that keeps track of the execution of instances of
the process.

## Develop

You will need the redis database, and rabbitmq for this to work

* `git clone https://github.com/tracsa/pvm.git && cd pvm`
* `virtualenv -p /usr/bin/python3 .env`
* `echo "export PVM_SETTINGS=$(pwd)/settings_develop.py" >> .env/bin/activate`
* `touch settings_develop.py`
* `source .env/bin/activate`
* `pip install -r requirements.txt`
* `pytest`

## The PVM REST API

In this same repository you will find a flask application that exposes a REST
api for controling the PVM.

**How to run**

* `FLASK_APP=pvm.http.wsgi flask run`
