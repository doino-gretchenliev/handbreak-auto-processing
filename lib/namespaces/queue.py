from datetime import datetime, date, time, timedelta

from flask import jsonify
from flask_restplus import Resource, Namespace, inputs
from humanize import naturalsize, naturaldelta, intcomma, apnumber, fractional

from lib.media_file_state import MediaFileState

mp = None
api = Namespace('queue', description='Control processing queue')

parser = api.parser()
parser.add_argument('humanize', type=inputs.boolean, help='return humanize results', default=True, required=False)


@api.route('/')
class Queue(Resource):
    parser = api.parser()
    parser.add_argument('humanize', type=inputs.boolean, help='return humanize results', default=True, required=False)
    parser.add_argument('full', type=inputs.boolean, help='return full details about every entry', default=True, required=False)

    @api.doc(description='get information about media processing queue state')
    @api.expect(parser)
    def get(self):
        args = self.parser.parse_args()
        if args.full:
            return mp.mfq.list(args.humanize), 200
        else:
            return [str(media_file) for media_file in mp.mfq.keys()], 200


@api.route('/stats')
class QueueStats(Resource):

    @api.doc(description='get statistic for media processing queue')
    @api.expect(parser)
    def get(self):
        args = parser.parse_args()

        start_of_the_day = datetime.combine(date.today(), time())
        end_of_the_day = start_of_the_day + timedelta(days=1) - timedelta(microseconds=1)

        processing_time = timedelta(microseconds=0)
        count = 0
        processed_count = 0
        processed_today = 0
        total_input_file_size = 0
        total_processed_file_size = 0
        for media_file in mp.mfq:
            if media_file.date_started and media_file.date_finished:
                processed_count += 1
                processing_time += media_file.date_finished - media_file.date_started

                if media_file.date_started >= start_of_the_day and media_file.date_finished <= end_of_the_day:
                    processed_today += 1
                if media_file.transcoded_file_size:
                    total_processed_file_size += media_file.transcoded_file_size
            total_input_file_size += media_file.file_size
            count += 1

        average_processing_time = QueueStats.mean(processing_time, processed_count)
        average_processed_per_day = QueueStats.mean(processed_count, (processing_time.total_seconds() / (60 * 60 * 24)))
        average_processed_file_size = total_processed_file_size / processed_count
        average_input_file_size = total_input_file_size / count
        input_to_processed_file_size_ratio = float(average_input_file_size) / max(average_processed_file_size, 1)

        return {
            'processed_today': apnumber(processed_today) if args.humanize else processed_today,
            'average_processed_per_day':  apnumber(average_processed_per_day) if args.humanize else str(average_processed_per_day),
            'average_processing_time': naturaldelta(average_processing_time) if args.humanize else str(average_processing_time),
            'average_processed_file_size': naturalsize(average_processed_file_size) if args.humanize else average_processed_file_size,
            'average_input_file_size': naturalsize(average_input_file_size) if args.humanize else average_input_file_size,
            'input_to_processed_file_size_ratio':  fractional(input_to_processed_file_size_ratio) if args.humanize else input_to_processed_file_size_ratio
        }

    @staticmethod
    def mean(items_sum, items_count):
        try:
            result = float(items_sum) / max(items_count, 1)
        except TypeError:
            result = items_sum / max(items_count, 1)
        return result


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
    @api.expect(parser)
    def get(self):
        args = parser.parse_args()
        return intcomma(len(mp.mfq)) if args.humanize else len(mp.mfq), 200


@api.route('/retry')
class QueueSize(Resource):

    @api.doc(description='retry all {} media files in processing queue'.format(MediaFileState.FAILED.value))
    def put(self):
        mp.retry_media_files()
        return 'all {} files retried'.format(MediaFileState.FAILED.value), 200


@api.route('/<string:id>')
class QueueSize(Resource):

    @api.doc(description='get information about media file')
    @api.expect(parser)
    def get(self, id):
        args = parser.parse_args()
        with mp.mfq.obtain_lock():
            if id in mp.mfq:
                response = jsonify(mp.mfq[id].dict(args.humanize))
                response.status_code = 200
            else:
                response = jsonify(
                    'Node [{}] not found'.format(id))
                response.status_code = 400
        return response

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
