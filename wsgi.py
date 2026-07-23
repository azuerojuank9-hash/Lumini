import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from flask_app import app as application

if __name__ == '__main__':
    application.run()
