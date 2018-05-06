from flask import jsonify
from flask_restplus import Resource, Namespace, inputs


ni = None
api = Namespace('nodes', description='Control processing nodes')


@api.route('/')
class Nodes(Resource):
    parser = api.parser()
    parser.add_argument('humanize', type=inputs.boolean, help='return humanize results', default=True, required=False)
    parser.add_argument('full', type=inputs.boolean, help='return full details about every entry', default=True, required=False)

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
                response.status_code = 400
        return response

    @api.doc(description='delete processing node')
    def delete(self, id):
        try:
            del ni[id]
            response = jsonify('Node [{}] deleted'.format(id))
            response.status_code = 200
        except Exception:
            response = jsonify(
                'Node [{}] not found'.format(id))
            response.status_code = 400
        return response



