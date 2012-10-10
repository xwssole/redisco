"""
Handles the queries.
"""
from attributes import IntegerField, DateTimeField
import redisco
from redisco.containers import SortedSet, Set, List, NonPersistentList
from exceptions import AttributeNotIndexed
from attributes import ZINDEXABLE

# Model Set
class ModelSet(Set):
    def __init__(self, model_class):
        self.model_class = model_class
        self.key = model_class._key['all']
        self._db = redisco.get_client()
        self._filters = {}
        self._exclusions = {}
        self._zfilters = []
        self._ordering = []
        self._limit = None
        self._offset = None

    #################
    # MAGIC METHODS #
    #################

    def __getitem__(self, index):
        """
        Will look in _set to get the id and simply return the instance of the model.
        """
        if isinstance(index, slice):
            return map(lambda id: self._get_item_with_id(id), self._set[index])
        else:
            id = self._set[index]
            if id:
                return self._get_item_with_id(id)
            else:
                raise IndexError

    def __repr__(self):
        if len(self._set) > 30:
            m = self._set[:30]
        else:
            m = self._set
        s = map(lambda id: self._get_item_with_id(id), m)
        return "%s" % s

    def __iter__(self):
        for id in self._set:
            yield self._get_item_with_id(id)

    def __len__(self):
        return len(self._set)

    def __contains__(self, val):
        return val.id in self._set

    ##########################################
    # METHODS THAT RETURN A SET OF INSTANCES #
    ##########################################

    def get_by_id(self, id):
        """
        Returns the object definied by ``id``.

        :param id: the ``id`` of the objects to lookup.
        :returns: The object instance or None if not found.

        >>> from redisco import models
        >>> class Foo(models.Model):
        ...     name = models.Attribute()
        ...
        >>> f = Foo(name="Einstein")
        >>> f.save()
        True
        >>> Foo.objects.get_by_id(f.id) == f
        True
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        if (self._filters or self._exclusions or self._zfilters) and str(id) not in self._set:
            return
        if self.model_class.exists(id):
            return self._get_item_with_id(id)

    def get_by_unique(self, att, value):
        """
        Returns the object by the unique value of att. 

        :param att: the unique attribute of the objects to lookup.
        :param value: the unique value of the objects to lookup.
        :returns: The object instance or None if not found.

        >>> from redis import models
        >>> class Foo(models.Model):
        ...     name = models.Attribute(unique=True)
        ...
        >>> f = Foo(name='Einstein')
        >>> f.save()
        True
        >>> Foo.objects.get_by_unique(name='Einstein') == f
        True
        >>> [f.delete() for f in Foo.objects.all()]
        [...]
        """

        if (self._filters or self._exclusions or self._zfilters):
            return
        
        id = self.model_class.get_id_by_unique(att, value)
        if id is None:
            return None
        assert (self.model_class.exists(id))
        return self._get_item_with_id(id)

    def first(self):
        """
        Return the first object of a collections.

        :return: The object or Non if the lookup gives no result


        >>> from redisco import models
        >>> class Foo(models.Model):
        ...     name = models.Attribute()
        ...
        >>> f = Foo(name="toto")
        >>> f.save()
        True
        >>> Foo.objects.filter(name="toto").first() # doctest: +ELLIPSIS
        <Foo:...>
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        try:
            return self.limit(1).__getitem__(0)
        except IndexError:
            return None


    #####################################
    # METHODS THAT MODIFY THE MODEL SET #
    #####################################

    def filter(self, **kwargs):
        """
        Filter a collection on criteria

        >>> from redisco import models
        >>> class Foo(models.Model):
        ...     name = models.Attribute()
        ...
        >>> Foo(name="toto").save()
        True
        >>> Foo(name="toto").save()
        True
        >>> Foo.objects.filter() # doctest: +ELLIPSIS
        [<Foo:...>, <Foo:...>]
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        clone = self._clone()
        if not clone._filters:
            clone._filters = {}
        clone._filters.update(kwargs)
        return clone

    def exclude(self, **kwargs):
        """
        Exclude a collection within a lookup.


        >>> from redisco import models
        >>> class Foo(models.Model):
        ...    name = models.Attribute()
        ...    exclude_me = models.BooleanField()
        ...
        >>> Foo(name="Einstein").save()
        True
        >>> Foo(name="Edison", exclude_me=True).save()
        True
        >>> Foo.objects.exclude(exclude_me=True).first().name
        u'Einstein'
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        clone = self._clone()
        if not clone._exclusions:
            clone._exclusions = {}
        clone._exclusions.update(kwargs)
        return clone

    def zfilter(self, **kwargs):
        clone = self._clone()
        if not clone._zfilters:
            clone._zfilters = []
        clone._zfilters.append(kwargs)
        return clone

    # this should only be called once
    def order(self, field):
        """
        Enable ordering in collections when doing a lookup.

        .. Warning:: This should only be called once per lookup.

        >>> from redisco import models
        >>> class Foo(models.Model):
        ...    name = models.Attribute()
        ...    exclude_me = models.BooleanField()
        ...
        >>> Foo(name="Abba").save()
        True
        >>> Foo(name="Zztop").save()
        True
        >>> Foo.objects.all().order("-name").first().name
        u'Zztop'
        >>> Foo.objects.all().order("name").first().name
        u'Abba'
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        fname = field.lstrip('-')
        if fname not in self.model_class._indices:
            raise ValueError("Order parameter should be an indexed attribute.")
        alpha = True
        if fname in self.model_class._attributes:
            v = self.model_class._attributes[fname]
            alpha = not isinstance(v, ZINDEXABLE)
        clone = self._clone()
        if not clone._ordering:
            clone._ordering = []
        clone._ordering.append((field, alpha,))
        return clone

    def limit(self, n, offset=0):
        """
        Limit the size of the collection to *n* elements.
        """
        clone = self._clone()
        clone._limit = n
        clone._offset = offset
        return clone

    def create(self, **kwargs):
        """
        Create an object of the class.

        .. Note:: This is the same as creating an instance of the class and saving it.

        >>> from redisco import models
        >>> class Foo(models.Model):
        ...     name = models.Attribute()
        ...
        >>> Foo.objects.create(name="Obama") # doctest: +ELLIPSIS
        <Foo:...>
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        instance = self.model_class(**kwargs)
        if instance.save():
            return instance
        else:
            return None

    def all(self):
        """
        Return all elements of the collection.
        """
        return self._clone()

    def get_or_create(self, **kwargs):
        """
        Return an element of the collection or create it if necessary.

        >>> from redisco import models
        >>> class Foo(models.Model):
        ...     name = models.Attribute()
        ...
        >>> new_obj = Foo.objects.get_or_create(name="Obama")
        >>> get_obj = Foo.objects.get_or_create(name="Obama")
        >>> new_obj == get_obj
        True
        >>> [f.delete() for f in Foo.objects.all()] # doctest: +ELLIPSIS
        [...]
        """
        opts = {}
        for k, v in kwargs.iteritems():
            if k in self.model_class._indices:
                opts[k] = v
        o = self.filter(**opts).first()
        if o:
            return o
        else:
            return self.create(**kwargs)

    #

    @property
    def db(self):
        return self._db

    ###################
    # PRIVATE METHODS #
    ###################

    @property
    def _set(self):
        """
        This contains the list of ids that have been looked-up,
        filtered and ordered. This set is build hen we first access
        it and is cached for has long has the ModelSet exist.
        """
        # For performance reasons, only one zfilter is allowed.
        if hasattr(self, '_cached_set'):
            return self._cached_set
        if self._zfilters:
            self._cached_set = self._add_zfilters()
            return self._cached_set
        s = Set(self.key)
        if self._filters:
            s = self._add_set_filter(s)
        if self._exclusions:
            s = self._add_set_exclusions(s)
        n = self._order(s.key)
        self._cached_set = n
        return self._cached_set

    def _add_set_filter(self, s):
        """
        This function is the internal of the `filter` function.
        It simply creates a new "intersection" of indexed keys (the filter) and
        the previous filtered keys (if any).

        .. Note:: This function uses the ``Set`` container class.

        :return: the new Set
        """
        indices = []
        for k, v in self._filters.iteritems():
            index = self._build_key_from_filter_item(k, v)
            if k not in self.model_class._indices:
                raise AttributeNotIndexed(
                        "Attribute %s is not indexed in %s class." %
                        (k, self.model_class.__name__))
            indices.append(index)
        new_set_key = "~%s.%s" % ("+".join([self.key] + indices), id(self))
        s.intersection(new_set_key, *[Set(n) for n in indices])
        new_set = Set(new_set_key)
        new_set.set_expire()
        return new_set

    def _add_set_exclusions(self, s):
        """
        This function is the internals of the `filter` function.
        It simply creates a new "difference" of indexed keys (the filter) and
        the previous filtered keys (if any).

        .. Note:: This function uses the ``Set`` container class.

        :return: the new Set
        """
        indices = []
        for k, v in self._exclusions.iteritems():
            index = self._build_key_from_filter_item(k, v)
            if k not in self.model_class._indices:
                raise AttributeNotIndexed(
                        "Attribute %s is not indexed in %s class." %
                        (k, self.model_class.__name__))
            indices.append(index)
        new_set_key = "~%s.%s" % ("-".join([self.key] + indices), id(self))
        s.difference(new_set_key, *[Set(n) for n in indices])
        new_set = Set(new_set_key)
        new_set.set_expire()
        return new_set

    def _add_zfilters(self):
        """
        This function is the internals of the zfilter function.
        It will create a SortedSet and will compare the scores to
        the value provided.

        :return: a SortedSet with the ids.

        """

        k, v = self._zfilters[0].items()[0]
        try:
            att, op = k.split('__')
        except ValueError:
            raise ValueError("zfilter should have an operator.")
        index = self.model_class._key[att]
        desc = self.model_class._attributes[att]
        zset = SortedSet(index)
        limit, offset = self._get_limit_and_offset()
        if isinstance(v, (tuple, list,)):
            min, max = v
            min = float(desc.typecast_for_storage(min))
            max = float(desc.typecast_for_storage(max))
        else:
            v = float(desc.typecast_for_storage(v))
        if op == 'lt':
            return zset.lt(v, limit, offset)
        elif op == 'gt':
            return zset.gt(v, limit, offset)
        elif op == 'gte':
            return zset.ge(v, limit, offset)
        elif op == 'lte':
            return zset.le(v, limit, offset)
        elif op == 'in':
            return zset.between(min, max, limit, offset)

    def _order(self, skey):
        """
        This function does not job. It will only call the good
        subfunction in case we want an ordering or not.
        """
        if self._ordering:
            return self._set_with_ordering(skey)
        else:
            return self._set_without_ordering(skey)

    def _set_with_ordering(self, skey):
        """
        Final call for finally ordering the looked-up collection.
        The ordering will be done by Redis itself and stored as a temporary set.

        :return: a Set of `id`
        """
        num, start = self._get_limit_and_offset()
        old_set_key = skey
        for ordering, alpha in self._ordering:
            if ordering.startswith('-'):
                desc = True
                ordering = ordering.lstrip('-')
            else:
                desc = False
            new_set_key = "%s#%s.%s" % (old_set_key, ordering, id(self))
            by = "%s->%s" % (self.model_class._key['*'], ordering)
            self.db.sort(old_set_key,
                         by=by,
                         store=new_set_key,
                         alpha=alpha,
                         start=start,
                         num=num,
                         desc=desc)
            if old_set_key != self.key:
                Set(old_set_key).set_expire()
            new_list = List(new_set_key)
            new_list.set_expire()
            return new_list

    def _set_without_ordering(self, skey):
        """
        Final call for "non-ordered" looked up.
        We order by id anyway and this is done by redis (same as above).

        :returns: A Set of `id`
        """
        # sort by id
        num, start = self._get_limit_and_offset()
        old_set_key = skey
        new_set_key = "%s#.%s" % (old_set_key, id(self))
        self.db.sort(old_set_key,
                     store=new_set_key,
                     start=start,
                     num=num)
        if old_set_key != self.key:
            Set(old_set_key).set_expire()
        new_list = List(new_set_key)
        new_list.set_expire()
        return new_list

    def _get_limit_and_offset(self):
        """
        Return the limit and offset of the looked up ids.
        """
        if (self._limit is not None and self._offset is None) or \
                (self._limit is None and self._offset is not None):
                    raise "Limit and offset must be specified"

        if self._limit is None:
            return (None, None)
        else:
            return (self._limit, self._offset)

    def _get_item_with_id(self, id):
        """
        Fetch an object and return the instance. The real fetching is
        done by assigning the id to the Instance. See ``Model`` class.
        """
        instance = self.model_class()
        instance.id = str(id)
        return instance

    def _build_key_from_filter_item(self, index, value):
        """
        Build the keys from the filter so we can fetch the good keys
        with the indices.
        Example:
            Foo.objects.filter(name='bar')
            => 'Foo:name:bar'
        """
        desc = self.model_class._attributes.get(index)
        if desc:
            value = desc.typecast_for_storage(value)
        return self.model_class._key[index][value]

    def _clone(self):
        """
        This function allows the chaining of lookup calls.
        Example:
            Foo.objects.filter().filter().exclude()...

        :returns: a modelset instance with all the previous filters.
        """
        klass = self.__class__
        c = klass(self.model_class)
        if self._filters:
            c._filters = self._filters
        if self._exclusions:
            c._exclusions = self._exclusions
        if self._zfilters:
            c._zfilters = self._zfilters
        if self._ordering:
            c._ordering = self._ordering
        c._limit = self._limit
        c._offset = self._offset
        return c

