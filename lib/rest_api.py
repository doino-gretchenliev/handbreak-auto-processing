from flask import Flask
from flask_restplus import Api, Resource
from lib.flask_thread import FlaskAppWrapper

app = Flask("ok")
api = Api(app, version='0.0.1', title='Handbreak auto processing tool API')
ns = api.namespace('media-processing', description='Media processing operations')

mp = None

class RestApi(object):

    def __init__(self, media_processing):
        global mp
        mp = media_processing
        self.flask_process = FlaskAppWrapper(app)
        self.flask_process.start()

    def stop(self):
        self.flask_process.join()


@ns.route('/')
class MediaProcessing(Resource):

    @ns.doc('get information about current media processing operation')
    def get(self):
        return  mp.get_current_processing_file(), 200


@ns.route('/suspend')
class MediaProcessingSuspend(Resource):

    @ns.doc('suspends media processing')
    @ns.response(201, '')
    def put(self):
        mp.suspend_media_processing()
        return 'suspend command sent', 201


@ns.route('/resume')
class MediaProcessingResume(Resource):

    @ns.doc('resumes media processing')
    @ns.response(201, '')
    def put(self):
        mp.resume_media_processing()
        return 'resume command sent', 201
