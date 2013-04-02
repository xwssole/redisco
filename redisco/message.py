# -*- coding: utf-8 -*-
# doctest: +ELLIPSIS
__all__ = ['MessageQueue']

import redisco

class MessageQueue(object):

    def __init__(self):
        self._conn = redisco.connection
        self._pubsub = self._conn.pubsub()

    def publish(self, *args, **kwargs):
        return self._conn.publish(*args, **kwargs)

    def subscribe(self, *args, **kwargs):
        return self._pubsub.subscribe(*args, **kwargs)

    def unsubscribe(self, *args, **kwargs):
        return self._pubsub.unsubscribe(*args, **kwargs)

    def psubscribe(self, *args, **kwargs):
        return self._pubsub.psubscribe(*args, **kwargs)

    def punsubscribe(self, *args, **kwargs):
        return self._pubsub.punsubscribe(*args, **kwargs)

    def listen(self, *args, **kwargs):
        return self._pubsub.listen(*args, **kwargs)
