import pickle
import sqlite3

from persistqueue import sqlbase


class PersistentAtomicDictionary(sqlbase.SQLiteBase, dict):
    _TABLE_NAME = 'dict'
    _KEY_COLUMN = 'key'
    _SQL_CREATE = ('CREATE TABLE IF NOT EXISTS {table_name} ('
                   '{key_column} TEXT PRIMARY KEY, data BLOB)')
    _SQL_INSERT = 'INSERT INTO {table_name} (key, data) VALUES (?, ?)'
    _SQL_SELECT = ('SELECT {key_column}, data FROM {table_name} '
                   'WHERE {key_column} = ?')

    _SQL_SELECT_WHERE = ('SELECT {key_column}, data FROM {table_name} '
                         'WHERE {key_column}{op}\'{column}\'')

    _SQL_UPDATE = 'UPDATE {table_name} SET data = ? WHERE {key_column} = ?'

    _SQL_SELECT_KEY = 'SELECT \'{key_column}\' FROM {table_name}'
    _SQL_SELECT_PRIM_KEY = 'SELECT {key_column} FROM {table_name}'
    _SQL_COUNT_KEYS = 'DELETE FROM {table_name} WHERE {key_column}=\'{key}\''

    def __init__(self, path):
        super(PersistentAtomicDictionary, self).__init__(path, name='persistent_dictionary', multithreading=True)

    def check_and_add(self, key, new_value, update=True):
        with self.tran_lock:
            with self._putter as tran:
                exists = self._contains(tran, key)
                if exists:
                    if update:
                        obj = pickle.dumps(new_value)
                        self._update(tran, obj, key)
                else:
                    obj = pickle.dumps(new_value)
                    self._insert_into(tran, key, obj)
                return exists

    def check_and_delete(self, key, values):
        with self.tran_lock:
            with self._putter as tran:
                result = False
                exists = self._contains(tran, key)
                if exists:
                    for value in values:
                        if self._get_value(tran, key) == value:
                            self._delete(key)
                            result = True
                return result

    def get_by_value_and_update(self, search_value, new_value, first_match=False):
        with self.tran_lock:
            with self._putter as tran:
                select_query = self._SQL_SELECT_PRIM_KEY.format(key_column=self._key_column,
                                                                table_name=self._table_name)
                keys = tran.execute(select_query).fetchall()
                result = None
                for key in [i[0] for i in keys]:
                    if self._get_value(tran, key) == search_value:
                        result = key
                        obj = pickle.dumps(new_value)
                        self._update(tran, obj, key)
                        if first_match:
                            break
                return result

    def keys(self):
        return self._keys()

    def iterkeys(self):
        return self._iterkeys()

    def _insert_into(self, transaction, *record):
        return transaction.execute(self._sql_insert, record)

    def _update(self, transaction, *args):
        return transaction.execute(self._sql_update, args)

    def __getitem__(self, item):
        row = self._select(item)
        if row:
            return pickle.loads(row[1])
        else:
            raise KeyError('Key: {} not exists.'.format(item))

    def __contains__(self, item):
        row = self._select(item)
        return row is not None

    def __setitem__(self, key, value):
        obj = pickle.dumps(value)
        with self.tran_lock:
            with self._putter as tran:
                try:
                    self._insert_into(tran, key, obj)
                except sqlite3.IntegrityError:
                    self._update(tran, obj, key)

    def __getitem__(self, item):
        row = self._select(item)
        if row:
            return pickle.loads(row[1])
        else:
            raise KeyError('Key: {} not exists.'.format(item))

    def __delitem__(self, key):
        self._delete(key)

    def __len__(self):
        return self._count()

    def _contains(self, transaction, item):
        result = self._select_with_transaction(transaction, op='=', column=item)
        return False if result is None else True

    def _keys(self):
        select_query = self._SQL_SELECT_PRIM_KEY.format(key_column=self._key_column, table_name=self._table_name)
        result = self._getter.execute(select_query).fetchall()
        return [i[0] for i in result]

    def _iterkeys(self):
        return iter(self._keys())

    def _get_value(self, transaction, key):
        row = self._select_with_transaction(transaction, key)
        if row:
            return pickle.loads(row[1])
        else:
            raise KeyError('Key: {} not exists.'.format(key))

    def _select_with_transaction(self, transaction, *args, **kwargs):
        op = kwargs.get('op', None)
        column = kwargs.get('column', None)
        if op and column:
            return transaction.execute(self._sql_select_where(op, column), args).fetchone()
        return transaction.execute(self._sql_select, args).fetchone()
