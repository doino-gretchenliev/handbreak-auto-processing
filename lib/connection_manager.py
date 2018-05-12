import functools


class ConnectionManager(object):

    __active_transactions = 0
    __database = None

    @classmethod
    def register_database(cls, database):
        cls.__database = database

    @classmethod
    def initialize_proxy(cls, proxy):
        proxy.initialize(cls.__get_database())

    @classmethod
    def __get_database(cls):
        if cls.__database:
            return cls.__database
        else:
            raise Exception('no database registered')

    @classmethod
    def connection(cls, func=None, transaction=False):
        if not func:
            return functools.partial(ConnectionManager.connection, transaction=transaction)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            database = cls.__get_database()
            database.connect(reuse_if_open=True)
            if transaction:
                with database.atomic('EXCLUSIVE'):
                    cls.__active_transactions += 1
                    result = func(*args, **kwargs)
                    cls.__active_transactions -= 1
            else:
                result = func(*args, **kwargs)
            if cls.__active_transactions == 0 and not database.is_closed():
                database.close()
            return result
        return wrapper