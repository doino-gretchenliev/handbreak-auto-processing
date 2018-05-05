from flask import Flask, jsonify
from flask_restplus import Api, Resource

from lib.JSONEncoder import JSONEncoder
from lib.flask_thread import FlaskAppWrapper
from lib.media_file_state import MediaFileState

app = Flask("ok")
app.json_encoder = JSONEncoder
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


@ns.route('/local')
class MediaProcessing(Resource):

    @ns.doc('get information about current media processing operation')
    def get(self):
        try:
            response = jsonify(mp.system_call_thread.current_processing_file.dict)
            response.status_code = 200
        except Exception:
            response = jsonify('No processing operation found at the moment')
            response.status_code = 404
        return response


@ns.route('/local/suspend')
class MediaProcessingSuspend(Resource):

    @ns.doc('suspends local media processing')
    @ns.response(201, '')
    def put(self):
        try:
            mp.suspend_media_processing()
            return 'suspend command sent', 201
        except Exception:
            return 'no running media processing found', 404


@ns.route('/local/resume')
class MediaProcessingResume(Resource):

    @ns.doc('resumes local media processing')
    @ns.response(201, '')
    def put(self):
        try:
            mp.resume_media_processing()
            return 'resume command sent', 201
        except Exception:
            return 'no running media processing found', 404


@ns.route('/queue')
class Queue(Resource):

    @ns.doc('get information about media processing queue state')
    def get(self):
        return mp.mfq.list, 200


@ns.route('/queue/stats')
class QueueStats(Resource):

    @ns.doc('get statistic for media processing queue')
    def get(self):
        return {}


@ns.route('/queue/size')
class QueueSize(Resource):

    @ns.doc('get size of media processing queue')
    def get(self):
        return len(mp.mfq), 200


@ns.route('/queue/retry')
class QueueSize(Resource):

    @ns.doc('retry all {} media files in processing queue'.format(MediaFileState.FAILED.value))
    def put(self):
        mp.retry_media_files()
        return 'all {} files retried'.format(MediaFileState.FAILED.value), 200


@ns.route('/queue/<string:id>')
class QueueSize(Resource):

    @ns.doc('retry a {} media file in processing queue'.format(MediaFileState.FAILED.value))
    def put(self, id):
        try:
            mp.retry_media_files(media_file=id)
            return 'Media file [{}] retried'.format(id), 200
        except Exception:
            return 'Media file [{}] not found'.format(id), 404

    @ns.doc('delete a media file(not in [{}]) from processing queue'.format(MediaFileState.PROCESSING.value))
    def delete(self, id):
        try:
            mp.delete_media_file(id)
            response = jsonify('Media file [{}] deleted'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify('Media file [{}] not found or in status [{}]'.format(id, MediaFileState.PROCESSING.value))
            response.status_code = 400
        return response
