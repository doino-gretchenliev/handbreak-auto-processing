import os

from filelock import SoftFileLock
from persistqueue import PDict


class PersistentBlockingDictionary(PDict):
    _SQL_SELECT_KEY = 'SELECT \'{key_column}\' FROM {table_name}'
    _SQL_SELECT_PRIM_KEY = 'SELECT {key_column} FROM {table_name}'
    _SQL_COUNT_KEYS = 'DELETE FROM {table_name} WHERE {key_column}=\'{key}\''

    lock = None

    def __init__(self, path):
        self.lock = SoftFileLock(os.path.join(path, "data.lock"))
        super(PersistentBlockingDictionary, self).__init__(path, name='persistent_dictionary', multithreading=True)

    def keys(self):
        with self.lock:
            return self._keys()

    def iterkeys(self):
        with self.lock:
            return self._iterkeys()

    def _insert_into(self, *record):
        with self.lock:
            return super(PersistentBlockingDictionary, self)._insert_into(*record)

    def _update(self, key, *args):
        with self.lock:
            return super(PersistentBlockingDictionary, self)._update(key, *args)

    def __delitem__(self, key):
        with self.lock:
            return super(PersistentBlockingDictionary, self)._delete(key)

    def __contains__(self, item):
        with self.lock:
            select_query = self._SQL_SELECT_KEY.format(key_column=item, table_name=self._table_name)
            result = self._getter.execute(select_query).fetchone()
            return False if result is None else True

    def _keys(self):
        select_query = self._SQL_SELECT_PRIM_KEY.format(key_column=self._key_column, table_name=self._table_name)
        result = self._getter.execute(select_query).fetchall()
        return [i[0] for i in result]

    def _iterkeys(self):
        return iter(self._keys())
