import re

from flask import jsonify, request
from flask_restplus import Resource, Namespace, inputs, fields

from lib.nodes.node_state import NodeState

TIME_RANGE_PATTERN = re.compile("^([0-9]|0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]-([0-9]|0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")

ni = None
api = Namespace('nodes', description='Control processing nodes')


@api.route('/')
class Nodes(Resource):
    parser = api.parser()
    parser.add_argument('humanize', type=inputs.boolean, help='return humanize results', default=True, required=False)
    parser.add_argument('full', type=inputs.boolean, help='return full details about every entry', default=True,
                        required=False)

    @api.doc(description='get information about all processing nodes')
    @api.expect(parser)
    def get(self):
        args = self.parser.parse_args()
        if args.full:
            return ni.list(args.humanize), 200
        else:
            return [str(node) for node in ni.keys()], 200


@api.route('/<string:id>')
class Node(Resource):
    parser = api.parser()
    parser.add_argument('humanize', type=inputs.boolean, help='return humanize results', default=True, required=False)

    @api.doc(description='get information about all processing nodes')
    @api.expect(parser)
    def get(self, id):
        args = self.parser.parse_args()
        with ni.obtain_lock():
            if id in ni:
                response = jsonify(ni[id].dict(args.humanize))
                response.status_code = 200
            else:
                response = jsonify(
                    'Node [{}] not found'.format(id))
                response.status_code = 404
        return response

    @api.doc(description="delete processing node(only if it's [{}])".format(NodeState.OFFLINE))
    def delete(self, id):
        try:
            del ni[id]
            if id in ni:
                response = jsonify('Node [{}] not deleted'.format(id))
            else:
                response = jsonify('Node [{}] deleted'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 404
        return response


@api.route('/<string:id>/silent')
class NodeSilentPeriods(Resource):

    @api.doc(description='get currently configured silent periods for node')
    def get(self, id):
        try:
            response = jsonify(ni.get_silent_periods(id))
            response.status_code = 200
        except Exception:
            import logging
            logging.exception("kj")
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 404
        return response

    silent_periods = api.model('silent_periods', {
        'silent_periods': fields.List(fields.String(title='silent_period'), required=True, unique=True,
                                      title='silent_periods',
                                      description='Silent periods list', example=
                                      ['12:00-16:00', '22:00-07:00'])
    })

    @api.doc(description='set silent periods for node')
    @api.expect(silent_periods)
    def put(self, id):
        args = request.get_json()
        for time_range in args['silent_periods']:
            if not TIME_RANGE_PATTERN.match(time_range):
                return "time range [{}] doesn\'t match format".format(time_range), 400

        try:
            ni.set_silent_periods(id, args['silent_periods'])
            response = jsonify('Node [{}] silent periods set'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 404
        return response

    @api.doc(description='clear currently configured silent periods for node')
    def delete(self, id):
        try:
            ni.clear_silent_periods(id)
            response = jsonify('Node [{}] silent periods cleared'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 404
        return response


@api.route('/<string:id>/suspend')
class NodeSuspend(Resource):

    @api.doc(description='suspends media processing on node')
    def put(self, id):
        try:
            ni[id] = NodeState.SUSPENDED
            response = jsonify('Node [{}] suspended'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 404
        return response


@api.route('/<string:id>/resume')
class NodeResume(Resource):

    @api.doc(description='resumes media processing on node')
    def put(self, id):
        try:
            ni[id] = NodeState.ONLINE
            response = jsonify('Node [{}] resumed'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 404
        return response
