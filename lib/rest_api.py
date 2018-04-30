from flask import Flask, jsonify
from flask_restplus import Api, Resource

from lib.JSONEncoder import JSONEncoder
from lib.flask_thread import FlaskAppWrapper
from lib.media_file_state import MediaFileState
from lib.utils import pretty_time_delta, QueueIDs

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


@ns.route('/current')
class MediaProcessing(Resource):

    @ns.doc('get information about current media processing operation')
    def get(self):
        if mp.system_call_thread:
            response = jsonify(mp.get_queue_files())

            response = jsonify({
                'file': mp.system_call_thread.current_processing_file_path,
                'status': MediaFileState.PROCESSING,
                'elapsed_time': pretty_time_delta(mp.system_call_thread.get_processing_time()),
                'suspended': mp.system_call_thread.system_call_thread.suspended
            })
            response.status_code = 200
        else:
            response = jsonify('No processing operation found at the moment')
            response.status_code = 200
        return response


@ns.route('/current/suspend')
class MediaProcessingSuspend(Resource):

    @ns.doc('suspends media processing')
    @ns.response(201, '')
    def put(self):
        mp.suspend_media_processing()
        return 'suspend command sent', 201


@ns.route('/current/resume')
class MediaProcessingResume(Resource):

    @ns.doc('resumes media processing')
    @ns.response(201, '')
    def put(self):
        mp.resume_media_processing()
        return 'resume command sent', 201


@ns.route('/queue')
class Queue(Resource):

    @ns.doc('get information about media processing queue state')
    def get(self):
        result = {}
        for file in mp.get_queue_files():
            result[QueueIDs.encrypt(file[0])] = {'file': file[0], 'status': file[1]}

        response = jsonify(result)
        response.status_code = 200

        return response


@ns.route('/queue/size')
class QueueSize(Resource):

    @ns.doc('get size of media processing queue')
    def get(self):
        return mp.get_queue_size(), 200


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
        decrypted_id = QueueIDs.decrypt(id)
        mp.retry_media_files(media_file=decrypted_id)
        return 'Media file {} retried'.format(id), 200

    @ns.doc('delete a media file(not in {}) from processing queue'.format(MediaFileState.PROCESSING.value))
    def delete(self, id):
        decrypted_id = QueueIDs.decrypt(id)
        existed = mp.delete_media_file(media_file=decrypted_id)
        if existed:
            response = jsonify('Media file {} deleted'.format(id))
            response.status_code = 200
        else:
            response = jsonify('Media file {} not found or in status: '.format(id, MediaFileState.PROCESSING))
            response.status_code = 404
        return response
