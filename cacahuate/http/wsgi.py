from flask import Flask
from flask_coralillo import Coralillo
from flask_cors import CORS
from flask_pymongo import PyMongo
from cacahuate.indexes import create_indexes

import os
import time

from cacahuate.models import bind_models

# The flask application
app = Flask(__name__)
app.config.from_object('cacahuate.settings')
app.config.from_envvar('CACAHUATE_SETTINGS', silent=True)

# Enalble cross origin
CORS(app)

# Timezone
os.environ['TZ'] = app.config.get('TIMEZONE', 'UTC')
time.tzset()

# Bind the database
cora = Coralillo(app)
bind_models(cora._engine)

# The database
mongo = PyMongo(app)
create_indexes(app.config)

# Url converters
import cacahuate.http.converters  # noqa

# Views
import cacahuate.http.views.api  # noqa
import cacahuate.http.views.auth  # noqa

# Error handlers
import cacahuate.http.error_handlers  # noqa
