import os
from app import create_app

app = create_app()#Use production confiq by default
config_name= os.environ.get('FLASK_CONFIG','production')

app = create_app(config_name)