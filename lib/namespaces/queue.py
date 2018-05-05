from datetime import datetime, date, time, timedelta

from flask import jsonify
from flask_restplus import Resource, Namespace

from lib.media_file_state import MediaFileState

mp = None
api = Namespace('queue', description='Control processing queue')


@api.route('/')
class Queue(Resource):

    @api.doc(description='get information about media processing queue state')
    def get(self):
        return mp.mfq.list, 200


@api.route('/stats')
class QueueStats(Resource):

    @api.doc(description='get statistic for media processing queue')
    def get(self):
        start_of_the_day = datetime.combine(date.today(), time())
        end_of_the_day = start_of_the_day + timedelta(days=1) - timedelta(microseconds=1)

        processing_time = timedelta(microseconds=0)
        processed_count = 0
        processed_today = 0
        for media_file in mp.mfq:
            if media_file.date_started and media_file.date_finished:
                processed_count += 1
                processing_time += media_file.date_finished - media_file.date_started

                if media_file.date_started >= start_of_the_day and media_file.date_finished <= end_of_the_day:
                    processed_today += 1
        return {
            'processed_today': processed_today,
            'average_processed_per_day': str(
                QueueStats.mean(processed_count, (processing_time.total_seconds() / (60 * 60 * 24)))),
            'average_processing_time': str(QueueStats.mean(processing_time, processed_count))
        }

    @staticmethod
    def mean(items_sum, items_count):
        return items_sum / max(items_count, 1)


@api.route('/load')
class QueueLoad(Resource):

    @api.doc(description='get load per day(min:0, max:1)')
    def get(self):
        time_graph = {}
        for media_file in mp.mfq:
            if media_file.date_started and media_file.date_finished:
                QueueLoad.update_time_graph(time_graph, media_file.date_started, media_file.date_finished)

        return time_graph

    @staticmethod
    def update_time_graph(time_graph, start_date, finish_date):
        finish_calendar_day = datetime.combine(
            finish_date.date(), time()) + timedelta(days=1)
        start__calendar_day = datetime.combine(start_date.date(), time())
        processing_calendar_days = (finish_calendar_day - start__calendar_day).days

        for day in range(0, processing_calendar_days):
            if processing_calendar_days == 1:
                time_span_of_the_day = (finish_date - start_date) \
                                           .total_seconds() / (60 * 60 * 24)
            elif day == 0:
                time_span_of_the_day = ((datetime.combine(
                    start_date.date(), time()) + timedelta(days=1)) - start_date) \
                                           .total_seconds() / (60 * 60 * 24)
            elif day == processing_calendar_days:
                time_span_of_the_day = ((datetime.combine(
                    finish_date.date(), time()) + timedelta(days=1)) - finish_date) \
                                           .total_seconds() / (60 * 60 * 24)
            else:
                time_span_of_the_day = 1

            curr_date = str((start_date + timedelta(days=day)).date())

            if curr_date in time_graph:
                time_graph[curr_date] = time_graph[curr_date] + time_span_of_the_day
            else:
                time_graph[curr_date] = time_span_of_the_day


@api.route('/size')
class QueueSize(Resource):

    @api.doc(description='get size of media processing queue')
    def get(self):
        return len(mp.mfq), 200


@api.route('/retry')
class QueueSize(Resource):

    @api.doc(description='retry all {} media files in processing queue'.format(MediaFileState.FAILED.value))
    def put(self):
        mp.retry_media_files()
        return 'all {} files retried'.format(MediaFileState.FAILED.value), 200


@api.route('/<string:id>')
class QueueSize(Resource):

    @api.doc(description='retry a {} media file in processing queue'.format(MediaFileState.FAILED.value))
    def put(self, id):
        try:
            mp.retry_media_files(media_file=id)
            return 'Media file [{}] retried'.format(id), 200
        except Exception:
            return 'Media file [{}] not found'.format(id), 404

    @api.doc(description='delete a media file(not in [{}]) from processing queue'.format(MediaFileState.PROCESSING.value))
    def delete(self, id):
        try:
            mp.delete_media_file(id)
            response = jsonify('Media file [{}] deleted'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Media file [{}] not found or in status [{}]'.format(id, MediaFileState.PROCESSING.value))
            response.status_code = 400
        return response
