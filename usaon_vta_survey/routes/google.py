import os

from flask_dance.contrib.google import make_google_blueprint

blueprint = make_google_blueprint(
    client_id=os.getenv('USAON_VTA_GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('USAON_VTA_GOOGLE_CLIENT_SECRET'),
    scope=["profile", "email"],
)
