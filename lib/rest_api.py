from flask import Flask, Blueprint
from flask_restplus import Api

from lib.JSONEncoder import JSONEncoder
from lib.flask_thread import FlaskAppWrapper
from lib.namespaces import nodes
from lib.namespaces import queue

app = Flask("ok")
app.json_encoder = JSONEncoder
app.config.SWAGGER_UI_JSONEDITOR = True

blueprint = Blueprint('api', __name__)
api = Api(blueprint, version='0.0.1', title='Handbreak auto processing tool API')
api.add_namespace(queue.api)
api.add_namespace(nodes.api)
app.register_blueprint(blueprint)


class RestApi(object):

    def __init__(self, media_processing, node_inventory):
        queue.mp = media_processing
        nodes.ni = node_inventory
        self.flask_process = FlaskAppWrapper(app)
        self.flask_process.start()

    def stop(self):
        self.flask_process.join()
