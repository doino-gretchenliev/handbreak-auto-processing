from flask import jsonify
from flask_restplus import Resource, Namespace

mp = None
api = Namespace('local', description='Control local media processing operations')


@api.route('/')
class LocalMediaProcessing(Resource):

    @api.doc(description='get information about current media processing operation')
    def get(self):
        try:
            response = jsonify(mp.system_call_thread.current_processing_file.dict)
            response.status_code = 200
        except Exception:
            response = jsonify('No processing operation found at the moment')
            response.status_code = 404
        return response


@api.route('/suspend')
class LocalMediaProcessingSuspend(Resource):

    @api.doc(description='suspends local media processing')
    def put(self):
        try:
            mp.suspend_media_processing()
            return 'suspend command sent', 201
        except Exception:
            return 'no running media processing found', 404


@api.route('/resume')
class LocalMediaProcessingResume(Resource):

    @api.doc(description='resumes local media processing')
    def put(self):
        try:
            mp.resume_media_processing()
            return 'resume command sent', 201
        except Exception:
            return 'no running media processing found', 404
