import unittest
import redisco
from redisco import models
from redisco import proxy

@proxy.SharedModel
class Person(models.Model):
    first_name = models.CharField()
    last_name = models.CharField()

class ProxyTestCase(unittest.TestCase):

    def setUp(self):
        self.client = redisco.get_client()
        self.client.flushdb()

    def test_save(self):
        p = Person()
        p.first_name = 'xi'
        p.last_name = 'he'
        p.save()

    def test_save_and_get(self):
        p = Person()
        p.first_name = 'xi'
        p.last_name = 'he'
        p.save()

        pp = Person.get_by_id(p.id)
        self.assertEqual(p.first_name, pp.first_name)
        self.assertEqual(p.last_name, pp.last_name)

    def test_copy_save(self):
        p = Person()
        p.first_name = 'xi'
        p.last_name = 'he'
        pp = p.copy()

        p.save()
        pp.save()
        self.assertEqual(p.id, pp.id)

    def test_concurrent_save(self):
        p = Person()
        p.first_name = 'xi'
        p.last_name = 'he'
        p.save()

        pp = Person.get_by_id(p.id)
        ppp = pp.copy()

        pp.first_name = 'xwssole'
        ppp.last_name = 'gua'

        pp.save()
        ppp.save()

        p = Person.get_by_id(p.id)
        self.assertEqual(pp.id, ppp.id)
        self.assertEqual('xwssole', p.first_name)
        self.assertEqual('gua', p.last_name)

    def test_serialize_save(self):
        p = Person()
        p.first_name = 'xi'
        p.last_name = 'he'
        p.save()

        pp = Person.get_by_id(p.id)
        ppp = pp.copy()
        pp.first_name = 'xwssole'
        pp.save()

        ppp.last_name = 'gua'
        ppp.save()
    
        p = Person.get_by_id(p.id)
        self.assertEqual(pp.id, ppp.id)
        self.assertEqual('xwssole', p.first_name)
        self.assertEqual('gua', p.last_name)

    def test_modify_copy_save(self):
        p = Person()
        p.first_name = 'xi'
        p.last_name = 'he'
        p.save()

        pp = Person.get_by_id(p.id)
        pp.first_name = 'xwssole'

        ppp = pp.copy()
        self.assertEqual('xwssole', ppp.first_name)
        self.assertEqual('he', ppp.last_name)
        ppp.last_name = 'gua'

        pp.save()
        ppp.save()

        p = Person.get_by_id(p.id)
        self.assertEqual(pp.id, ppp.id)
        self.assertEqual('xwssole', p.first_name)
        self.assertEqual('gua', p.last_name)

    def tearDown(self):
        self.client.flushdb()
