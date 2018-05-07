import datetime
import logging
import os

from peewee import SqliteDatabase

from lib.nodes.node import Node
from lib.nodes.node import proxy
from lib.nodes.node_state import NodeState
import cpuinfo
import json

logger = logging.getLogger(__name__)


def transaction(func):
    def _execute(obj, *args, **kwargs):
        with obj.obtain_lock():
            return func(obj, *args, **kwargs)

    return _execute


class NodeInventory(object):

    def __init__(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        self.__database = SqliteDatabase(os.path.join(path, 'nodes.db'))
        proxy.initialize(self.__database)
        proxy.connect()
        Node.create_table(True)

    def obtain_lock(self):
        return self.__database.atomic('EXCLUSIVE')

    def __len__(self):
        return Node.select().count()

    @transaction
    def __delitem__(self, key, safe=True):
        if isinstance(key, tuple):
            if safe:
                query = (Node.id == key[0]) & (Node.hostname == key[1]) & (Node.status == NodeState.OFFLINE)
            else:
                query = (Node.id == key[0]) & (Node.hostname == key[1])
        else:
            if safe:
                query = ((Node.id == key) | (Node.hostname == key)) & (Node.status == NodeState.OFFLINE)
            else:
                query = (Node.id == key) | (Node.hostname == key)
        Node.delete().where(query).execute()

    @transaction
    def __setitem__(self, key, status):
        now = datetime.datetime.now()
        set_fields = {'status': status}

        if status == NodeState.ONLINE:
            set_fields['date_become_online'] = now
            set_fields['date_become_offline'] = None
        elif status == NodeState.OFFLINE:
            set_fields['date_become_online'] = None
            set_fields['date_become_offline'] = now

        if self.__contains__(key):
            if isinstance(key, tuple):
                Node.update(set_fields).where((Node.id == key[1]) | (Node.hostname == key[1])).execute()
            else:
                Node.update(set_fields).where((Node.id == key) | (Node.hostname == key)).execute()
        else:
            if isinstance(key, tuple):
                info = cpuinfo.get_cpu_info()
                set_fields['id'] = key[0]
                set_fields['hostname'] = key[1]
                set_fields['cpu_threads'] = info['count']
                set_fields['cpu_details'] = info['brand']
                Node.create(**set_fields)
            else:
                raise Exception('node doesn\'t exist, you must provide both id and hostname')

    def __getitem__(self, key):
        if isinstance(key, tuple):
            result = Node.select().where((Node.id == key[0]) & (Node.hostname == key[1])).limit(1)
        else:
            result = Node.select().where((Node.id == key) | (Node.hostname == key)).limit(1)
        return result.first() if result else None

    def __repr__(self):
        result = []
        for node in Node.select().iterator():
            result.append(node)
        return "Nodes({})".format(result)

    def serialize(self):
        result = []
        for node in Node.select().iterator():
            result.append(node.dict())
        return result

    def __iter__(self):
        return Node.select().iterator()

    def __contains__(self, item):
        if isinstance(item, tuple):
            result = Node.select().where(Node.hostname == item[1]).exists()
        else:
            result = Node.select().where((Node.id == item) | (Node.hostname == item)).exists()
        return result

    def keys(self):
        result = []
        for node in self.__iter__():
            result.append(node.id)
        return result

    def values(self):
        result = []
        for node in self.__iter__():
            result.append(node.status)
        return result

    @transaction
    def pop(self, status=None):
        result = self.peek(status)
        self.__delitem__(result.id)
        return result

    def peek(self, status=None):
        if status:
            result = Node.select().where(Node.status == status).first()
        else:
            result = Node.select().first()
        if not result:
            raise Exception('node not found')
        return result

    @transaction
    def clear(self, safe=True):
        if safe:
            Node.delete().where(Node.status != NodeState.ONLINE).execute()
        else:
            Node.delete().execute()

    def list(self, humanize=False):
        return [ node.dict(humanize) for node in Node ]

    @transaction
    def set_silent_periods(self, key, silent_periods):
        if self.__contains__(key):
            Node.update(silent_periods=json.dumps(silent_periods)).where((Node.id == key) | (Node.hostname == key)).execute()
        else:
            raise Exception('node not found')

    @transaction
    def get_silent_periods(self, key):
        if self.__contains__(key):
            return json.loads(Node.select().where((Node.id == key) | (Node.hostname == key)).first().silent_periods)
        else:
            raise Exception('node not found')

    @transaction
    def clear_silent_periods(self, key):
        if self.__contains__(key):
            Node.update(silent_periods=None).where(Node.id == key).execute()
        else:
            raise Exception('node not found')
