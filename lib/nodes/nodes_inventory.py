import datetime
import json

import cpuinfo

from lib.connection_manager import ConnectionManager
from lib.nodes.node import Node
from lib.nodes.node import proxy
from lib.nodes.node_state import NodeState


class NodeInventory(object):

    def __init__(self):
        ConnectionManager.initialize_proxy(proxy)
        self.__create_table()

    @ConnectionManager.connection(transaction=True)
    def __create_table(self):
        Node.create_table(True)

    @ConnectionManager.connection
    def __len__(self):
        return Node.select().count()

    @ConnectionManager.connection(transaction=True)
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

    @ConnectionManager.connection(transaction=True)
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

    @ConnectionManager.connection
    def __getitem__(self, key):
        if isinstance(key, tuple):
            result = Node.select().where((Node.id == key[0]) & (Node.hostname == key[1])).limit(1)
        else:
            result = Node.select().where((Node.id == key) | (Node.hostname == key)).limit(1)
        return result.first() if result else None

    @ConnectionManager.connection
    def __repr__(self):
        result = []
        for node in Node.select().iterator():
            result.append(node)
        return "Nodes({})".format(result)

    @ConnectionManager.connection
    def serialize(self):
        result = []
        for node in Node.select().iterator():
            result.append(node.dict())
        return result

    @ConnectionManager.connection
    def __iter__(self):
        return Node.select().iterator()

    @ConnectionManager.connection
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

    @ConnectionManager.connection(transaction=True)
    def pop(self, status=None):
        result = self.peek(status)
        self.__delitem__(result.id)
        return result

    @ConnectionManager.connection
    def peek(self, status=None):
        if status:
            result = Node.select().where(Node.status == status).first()
        else:
            result = Node.select().first()
        if not result:
            raise Exception('node not found')
        return result

    @ConnectionManager.connection(transaction=True)
    def clear(self, safe=True):
        if safe:
            Node.delete().where(Node.status != NodeState.ONLINE).execute()
        else:
            Node.delete().execute()

    @ConnectionManager.connection
    def list(self, humanize=False):
        return [node.dict(humanize) for node in Node]

    @ConnectionManager.connection(transaction=True)
    def set_silent_periods(self, key, silent_periods):
        if self.__contains__(key):
            Node.update(silent_periods=json.dumps(silent_periods)).where(
                (Node.id == key) | (Node.hostname == key)).execute()
        else:
            raise Exception('node not found')

    @ConnectionManager.connection(transaction=True)
    def get_silent_periods(self, key):
        if self.__contains__(key):
            result = Node.select().where((Node.id == key) | (Node.hostname == key)).first()
            if result:
                return json.loads(result.silent_periods)
            else:
                raise Exception("no silent periods configured for node [{}]".format(key))
        else:
            raise Exception('node not found')

    @ConnectionManager.connection(transaction=True)
    def clear_silent_periods(self, key):
        if self.__contains__(key):
            Node.update(silent_periods=None).where(Node.id == key).execute()
        else:
            raise Exception('node not found')
