# -*- coding: utf-8 -*-
"""
Defines the fields that can be added to redisco models.
"""
import time
from datetime import datetime, date
from dateutil.tz import tzutc, tzlocal
from calendar import timegm
from redisco.containers import List
from exceptions import FieldValidationError, MissingID

__all__ = ['Attribute', 'CharField', 'ListField', 'DateTimeField',
        'DateField', 'ReferenceField', 'IntegerField',
        'FloatField', 'BooleanField', 'Counter', 'ZINDEXABLE']


class Attribute(object):
    """Defines an attribute of the model.

    The attribute accepts strings and are stored in Redis as
    they are - strings.

    Options
        name      -- alternate name of the attribute. This will be used
                     as the key to use when interacting with Redis.
        indexed   -- Index this attribute. Unindexed attributes cannot
                     be used in queries. Default: True.
        unique    -- validates the uniqueness of the value of the
                     attribute.
        validator -- a callable that can validate the value of the
                     attribute.
        default   -- Initial value of the attribute.

    """
    def __init__(self,
                 name=None,
                 indexed=True,
                 required=False,
                 validator=None,
                 unique=False,
                 default=None):
        self.name = name
        self.indexed = indexed
        self.required = required
        self.validator = validator
        self.default = default
        self.unique = unique

        if self.unique:
            self.indexed = False

    def __get__(self, instance, owner):
        try:
            return getattr(instance, '_' + self.name)
        except AttributeError:
            self.__set__(instance, self.default)
            return self.default

    def __set__(self, instance, value):
        attribute_name = '_' + self.name
        setattr(instance, attribute_name, value)

    def typecast_for_read(self, value):
        """Typecasts the value for reading from Redis."""
        # The redis client encodes all unicode data to utf-8 by default.
        return value.decode('utf-8')

    def typecast_for_storage(self, value):
        """Typecasts the value for storing to Redis."""
        try:
            return unicode(value)
        except UnicodeError:
            return value.decode('utf-8')

    def value_type(self):
        return unicode

    def acceptable_types(self):
        return basestring

    def validate(self, instance):
        val = getattr(instance, self.name)
        errors = []
        # type_validation
        if val is not None and not isinstance(val, self.acceptable_types()):
            errors.append((self.name, 'bad type',))
        # validate first standard stuff
        if self.required:
            if val is None or not unicode(val).strip():
                errors.append((self.name, 'required'))
        # validate uniquness
        if val and self.unique:
            error = self.validate_uniqueness(instance, val)
            if error:
                errors.append(error)
        # validate using validator
        if self.validator:
            r = self.validator(self.name, val)
            if r:
                errors.extend(r)
        if errors:
            raise FieldValidationError(errors)

    def validate_uniqueness(self, instance, val):
        if self.indexed and self.unique:
            return (self.name, 'unique could not be indexed')

        encoded = self.typecast_for_storage(val)
        match = instance.__class__.objects.get_by_unique(**{self.name: encoded})
        match_count = 0 if match is None else 1
        if match_count > (0 if instance.is_new() else 1):
            return (self.name, 'not unique',)


class CharField(Attribute):

    def __init__(self, max_length=255, **kwargs):
        super(CharField, self).__init__(**kwargs)
        self.max_length = max_length

    def validate(self, instance):
        errors = []
        try:
            super(CharField, self).validate(instance)
        except FieldValidationError as err:
            errors.extend(err.errors)

        val = getattr(instance, self.name)

        if val and len(val) > self.max_length:
            errors.append((self.name, 'exceeds max length'))

        if errors:
            raise FieldValidationError(errors)


class BooleanField(Attribute):
    def typecast_for_read(self, value):
        return bool(int(value))

    def typecast_for_storage(self, value):
        if value is None:
            return "0"
        return "1" if value else "0"

    def value_type(self):
        return bool

    def acceptable_types(self):
        return self.value_type()


class IntegerField(Attribute):
    def typecast_for_read(self, value):
        return int(value)

    def typecast_for_storage(self, value):
        if value is None:
            return "0"
        return unicode(value)

    def value_type(self):
        return int

    def acceptable_types(self):
        return (int, long)


class FloatField(Attribute):
    def typecast_for_read(self, value):
        return float(value)

    def typecast_for_storage(self, value):
        if value is None:
            return "0"
        return "%f" % value

    def value_type(self):
        return float

    def acceptable_types(self):
        return self.value_type()


class DateTimeField(Attribute):

    def __init__(self, auto_now=False, auto_now_add=False, **kwargs):
        super(DateTimeField, self).__init__(**kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add

    def typecast_for_read(self, value):
        try:
            # We load as if the timestampe was naive
            dt = datetime.fromtimestamp(float(value), tzutc())
            # And gently override (ie: not convert) to the TZ to UTC
            return dt
        except (TypeError, ValueError):
            return None

    def typecast_for_storage(self, value):
        if not isinstance(value, datetime):
            raise TypeError("%s should be datetime object, and not a %s" %
                    (self.name, type(value)))
        if value is None:
            return None
        # Are we timezone aware ? If no, make it TimeZone Local
        if value.tzinfo is None:
           value = value.replace(tzinfo=tzlocal())
        return "%d.%06d" % (float(timegm(value.utctimetuple())),  value.microsecond)

    def value_type(self):
        return datetime

    def acceptable_types(self):
        return self.value_type()


class DateField(Attribute):

    def __init__(self, auto_now=False, auto_now_add=False, **kwargs):
        super(DateField, self).__init__(**kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add

    def typecast_for_read(self, value):
        try:
            # We load as if it is UTC time
            dt = date.fromtimestamp(float(value))
            # And assign (ie: not convert) the UTC TimeZone
            return dt
        except TypeError, ValueError:
            return None

    def typecast_for_storage(self, value):
        if not isinstance(value, date):
            raise TypeError("%s should be date object, and not a %s" %
                    (self.name, type(value)))
        if value is None:
            return None
        return "%d" % float(timegm(value.timetuple()))

    def value_type(self):
        return date

    def acceptable_types(self):
        return self.value_type()

class ListField(object):
    """Stores a list of objects.

    target_type -- can be a Python object or a redisco model class.

    If target_type is not a redisco model class, the target_type should
    also a callable that casts the (string) value of a list element into
    target_type. E.g. str, unicode, int, float.

    ListField also accepts a string that refers to a redisco model.

    """
    def __init__(self, target_type,
                 name=None,
                 indexed=True,
                 required=False,
                 validator=None,
                 default=None):
        self._target_type = target_type
        self.name = name
        self.indexed = indexed
        self.required = required
        self.validator = validator
        self.default = default or []
        from base import Model
        self._redisco_model = (isinstance(target_type, basestring) or
            issubclass(target_type, Model))

    def __get__(self, instance, owner):
        try:
            return getattr(instance, '_' + self.name)
        except AttributeError:
            if instance.is_new():
                val = self.default
            else:
                key = instance.key()[self.name]
                val = List(key).members
            if val is not None:
                klass = self.value_type()
                if self._redisco_model:
                    val = filter(lambda o: o is not None, [klass.objects.get_by_id(v) for v in val])
                else:
                    val = [klass(v) for v in val]
            self.__set__(instance, val)
            return val

    def __set__(self, instance, value):
        setattr(instance, '_' + self.name, value)

    def value_type(self):
        if isinstance(self._target_type, basestring):
            t = self._target_type
            from base import get_model_from_key
            self._target_type = get_model_from_key(self._target_type)
            if self._target_type is None:
                raise ValueError("Unknown Redisco class %s" % t)
        return self._target_type

    def validate(self, instance):
        val = getattr(instance, self.name)
        errors = []

        if val:
            if not isinstance(val, list):
                errors.append((self.name, 'bad type'))
            else:
                for item in val:
                    if not isinstance(item, self.value_type()):
                        errors.append((self.name, 'bad type in list'))

        # validate first standard stuff
        if self.required:
            if not val:
                errors.append((self.name, 'required'))
        # validate using validator
        if self.validator:
            r = self.validator(val)
            if r:
                errors.extend(r)
        if errors:
            raise FieldValidationError(errors)


class ReferenceField(object):
    def __init__(self,
                 target_type,
                 name=None,
                 attname=None,
                 indexed=True,
                 required=False,
                 related_name=None,
                 default=None,
                 validator=None):
        self._target_type = target_type
        self.name = name
        self.indexed = indexed
        self.required = required
        self._attname = attname
        self._related_name = related_name
        self.validator = validator
        self.default = default

    def __set__(self, instance, value):
        """
        Will set the referenced object unless None is provided
        which will simply remove the reference
        """
        if not isinstance(value, self.value_type()) and \
                value is not None:
            raise TypeError
        # remove the cached value from the instance
        if hasattr(instance, '_' + self.name):
            delattr(instance, '_' + self.name)
        # Remove the attribute_id reference
        setattr(instance, self.attname, None)
        # Set it to the new value if any.
        if value is not None:
            setattr(instance, self.attname, value.id)

    def __get__(self, instance, owner):
        try:
            if not hasattr(instance, '_' + self.name):
                o = self.value_type().objects.get_by_id(
                                    getattr(instance, self.attname))
                setattr(instance, '_' + self.name, o)
            return getattr(instance, '_' + self.name)
        except AttributeError:
            setattr(instance, '_' + self.name, self.default)
            return self.default

    def value_type(self):
        return self._target_type

    @property
    def attname(self):
        if self._attname is None:
            self._attname = self.name + '_id'
        return self._attname

    @property
    def related_name(self):
        return self._related_name

    def validate(self, instance):
        val = getattr(instance, self.name)
        errors = []

        if val:
            if not isinstance(val, self.value_type()):
                errors.append((self.name, 'bad type for reference'))

        # validate first standard stuff
        if self.required:
            if not val:
                errors.append((self.name, 'required'))
        # validate using validator
        if self.validator:
            r = self.validator(val)
            if r:
                errors.extend(r)
        if errors:
            raise FieldValidationError(errors)


class Counter(IntegerField):
    def __init__(self, **kwargs):
        super(Counter, self).__init__(**kwargs)
        if not kwargs.has_key('default') or self.default is None:
            self.default = 0

    def __set__(self, instance, value):
        raise AttributeError("can't set a counter.")

    def __get__(self, instance, owner):
        if not instance.is_new():
            v = instance.db.hget(instance.key(), self.name)
            if v is None:
                return 0
            return int(v)
        else:
            return 0


ZINDEXABLE = (IntegerField, DateTimeField, DateField, FloatField, Counter)
