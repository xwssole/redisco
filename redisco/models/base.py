from datetime import datetime, date
from redisco.connection import _get_client
from redisco.containers import Set, List, SortedSet, NonPersistentList
from attributes import *
from key import Key
from managers import ManagerDescriptor, Manager
from utils import _encode_key
from exceptions import FieldValidationError, MissingID

__all__ = ['Model']

ZINDEXABLE = (IntegerField, DateTimeField, DateField, FloatField)


##############################
# Model Class Initialization #
##############################

def _initialize_attributes(model_class, name, bases, attrs):
    """Initialize the attributes of the model."""
    model_class._attributes = {}
    for k, v in attrs.iteritems():
        if isinstance(v, Attribute):
            model_class._attributes[k] = v
            v.name = v.name or k

def _initialize_referenced(model_class, attribute):
    # this should be a descriptor
    def _related_objects(self):
        return (model_class.objects
                .filter(**{attribute.attname: self.id}))

    related_name = (attribute.related_name or
            model_class.__name__.lower() + '_set')
    setattr(attribute._target_type, related_name,
            property(_related_objects))

def _initialize_lists(model_class, name, bases, attrs):
    model_class._lists = {}
    for k, v in attrs.iteritems():
        if isinstance(v, ListField):
            model_class._lists[k] = v
            v.name = v.name or k

def _initialize_references(model_class, name, bases, attrs):
    model_class._references = {}
    h = {}
    for k, v in attrs.iteritems():
        if isinstance(v, ReferenceField):
            model_class._references[k] = v
            v.name = v.name or k
            att = Attribute(name=v.attname)
            h[v.attname] = att
            setattr(model_class, v.attname, att)
            _initialize_referenced(model_class, v)
    attrs.update(h)

def _initialize_indices(model_class, name, bases, attrs):
    model_class._indices = []
    for k, v in attrs.iteritems():
        if isinstance(v, Attribute) and v.indexed:
            model_class._indices.append(k)
        elif isinstance(v, ListField) and v.indexed:
            model_class._indices.append(k)

    if model_class._meta['indices']:
        model_class._indices.extend(model_class._meta['indices'])

def _initialize_key(model_class, name):
    model_class._key = Key(name)

def _initialize_db(model_class):
    model_class._db = model_class._meta['db'] or _get_client()

def _initialize_manager(model_class):
    model_class.objects = ManagerDescriptor(Manager(model_class))


class ModelOptions(object):
    def __init__(self, meta):
        self.meta = meta

    def get_field(self, field_name):
        if self.meta is None:
            return None
        try:
            return self.meta.__dict__[field_name]
        except KeyError:
            return None
    __getitem__ = get_field


class ModelBase(type):
    def __init__(cls, name, bases, attrs):
        super(ModelBase, cls).__init__(name, bases, attrs)
        cls._meta = ModelOptions(attrs.pop('Meta', None))
        _initialize_references(cls, name, bases, attrs)
        _initialize_attributes(cls, name, bases, attrs)
        _initialize_lists(cls, name, bases, attrs)
        _initialize_indices(cls, name, bases, attrs)
        _initialize_key(cls, name)
        _initialize_db(cls)
        _initialize_manager(cls)


class Model(object):
    __metaclass__ = ModelBase

    def __init__(self, **kwargs):
        self.update_attributes(**kwargs)

    def is_valid(self):
        self._errors = []
        for field in self.fields:
            try:
                field.validate(self)
            except FieldValidationError, e:
                self._errors.extend(e.errors)
        self.validate()
        return not bool(self._errors)

    def validate(self):
        """Overriden in the model class.
        
        Do custom validation here. Add tuples to self._errors.

        Example:

            class Person(Model):
                name = Attribute(required=True)

                def validate(self):
                    if name == 'Nemo':
                        self._errors.append(('name', 'cannot be Nemo'))

        """
        pass

    def update_attributes(self, **kwargs):
        """Updates the attributes of the model."""
        attrs = self.attributes.values() + self.lists.values() \
                + self.references.values()
        for att in attrs:
            if att.name in kwargs:
                att.__set__(self, kwargs[att.name])

    def save(self):
        """Saves the instance to the datastore."""
        if not self.is_valid():
            return None
        self._write()
        return True

    def key(self):
        """Returns the Redis key where the values are stored."""
        return self._key[self.id]

    def delete(self):
        """Deletes the object from the datastore."""
        self._delete_from_indices()
        self._delete_membership()
        del self.db[self.key()]

    def is_new(self):
        """Returns True if the instance is new.

        Newness is based on the presence of the _id attribute.
        """
        return not hasattr(self, '_id')

    @property
    def id(self):
        """Returns the id of the instance.

        Raises MissingID if the instance is new.
        """
        if not hasattr(self, '_id'):
            raise MissingID
        return self._id

    @id.setter
    def id(self, val):
        """Returns the id of the instance as a string."""
        self._id = str(val)

    @property
    def attributes(cls):
        """Return the attributes of the model.

        Returns a dict with models attribute name as keys
        and attribute descriptors as values.
        """
        return dict(cls._attributes)

    @property
    def lists(cls):
        """Return the lists of the model.

        Returns a dict with models attribute name as keys
        and ListField descriptors as values.
        """
        return dict(cls._lists)

    @property
    def indices(cls):
        """Return a list of the indices of the model."""
        return cls._indices

    @property
    def references(cls):
        return cls._references

    @property
    def db(cls):
        return cls._db

    @property
    def errors(self):
        return self._errors

    @property
    def fields(self):
        return (self.attributes.values() + self.lists.values()
                + self.references.values())

    ###################
    # Private methods #
    ###################

    def _initialize_id(self):
        """Initializes the id of the instance."""
        self.id = str(self.db.incr(self._key['id']))

    def _write(self):
        """Writes the values of the attributes to the datastore.

        This method also creates the indices and saves the lists
        associated to the object.
        """
        _new = self.is_new()
        if _new:
            self._initialize_id()
        self._create_membership()
        self._update_indices()
        h = {}
        # attributes
        for k, v in self.attributes.iteritems():
            if isinstance(v, DateTimeField):
                if v.auto_now:
                    setattr(self, k, datetime.now())
                if v.auto_now_add and _new:
                    setattr(self, k, datetime.now())
            elif isinstance(v, DateField):
                if v.auto_now:
                    setattr(self, k, date.today())
                if v.auto_now_add and _new:
                    setattr(self, k, date.today())
            h[k] = v.typecast_for_storage(getattr(self, k))
        # indices
        for index in self.indices:
            if index not in self.lists and index not in self.attributes:
                v = getattr(self, index)
                if callable(v):
                    v = v()
                h[index] = str(v)
        if h:
            self.db.hmset(self.key(), h)

        # lists
        for k, v in self.lists.iteritems():
            l = List(self.key()[k])
            l.clear()
            values = getattr(self, k)
            if values:
                l.extend(values)

    ##############
    # Membership #
    ##############

    def _create_membership(self):
        Set(self._key['all']).add(self.id)

    def _delete_membership(self):
        Set(self._key['all']).remove(self.id)


    ############
    # INDICES! #
    ############

    def _update_indices(self):
        self._delete_from_indices()
        self._add_to_indices()

    def _add_to_indices(self):
        """Adds the base64 encoded values of the indices."""
        pipe = self.db.pipeline()
        for att in self.indices:
            self._add_to_index(att, pipe=pipe)
        pipe.execute()

    def _add_to_index(self, att, val=None, pipe=None):
        """
        Adds the id to the index.

        This also adds to the _indices set of the object.
        """
        index = self._index_key_for(att)
        if index is None:
            return
        t, index = index
        if t == 'attribute':
            pipe.sadd(index, self.id)
            pipe.sadd(self.key()['_indices'], index)
        elif t == 'list':
            for i in index:
                pipe.sadd(i, self.id)
                pipe.sadd(self.key()['_indices'], i)
        elif t == 'sortedset':
            zindex, index = index
            pipe.sadd(index, self.id)
            pipe.sadd(self.key()['_indices'], index)
            descriptor = self.attributes[att]
            score = descriptor.typecast_for_storage(getattr(self, att))
            pipe.zadd(zindex, self.id, score)
            pipe.sadd(self.key()['_zindices'], zindex)


    def _delete_from_indices(self):
        s = Set(self.key()['_indices'])
        z = Set(self.key()['_zindices'])
        pipe = s.db.pipeline()
        for index in s.members:
            pipe.srem(index, self.id)
        for index in z.members:
            pipe.srem(index, self.id)
        pipe.delete(s.key)
        pipe.delete(z.key)
        pipe.execute()

    def _index_key_for(self, att, value=None):
        if value is None:
            value = getattr(self, att)
            if callable(value):
                value = value()
        if value is None:
            return None
        if att not in self.lists:
            try:
                descriptor = self.attributes[att]
                if isinstance(descriptor, ZINDEXABLE):
                    sval = descriptor.typecast_for_storage(value)
                    return self._tuple_for_index_key_attr_zset(att, value, sval)
                else:
                    return self._tuple_for_index_key_attr_val(att, value)
            except KeyError:
                return self._tuple_for_index_key_attr_val(att, value)
        else:
            return self._tuple_for_index_key_attr_list(att, value)

    def _tuple_for_index_key_attr_val(self, att, val):
        return ('attribute', self._index_key_for_attr_val(att, val))

    def _tuple_for_index_key_attr_list(self, att, val):
        return ('list', [self._index_key_for_attr_val(att, e) for e in val])

    def _tuple_for_index_key_attr_zset(self, att, val, sval):
        return ('sortedset',
                (self._key[att], self._index_key_for_attr_val(att, sval)))

    def _index_key_for_attr_val(self, att, val):
        return self._key[att][_encode_key(str(val))]


    ##################
    # Python methods #
    ##################

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.key() == other.key()

    def __ne__(self, other):
        return not self.__eq__(other)

