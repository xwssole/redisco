# -*- coding: utf-8 -*-
# doctest: +ELLIPSIS

__all__ = ['publish',
           'subscribe',
           'unsubscribe',
           'psubscribe',
           'punsubscribe',
           'listen']

import redisco

_conn = redisco.connection
_pubsub = _conn.pubsub()

publish = _conn.publish
subscribe = _pubsub.subscribe
unsubscribe = _pubsub.unsubscribe
psubscribe = _pubsub.psubscribe
punsubscribe = _pubsub.punsubscribe
listen = _pubsub.listen
