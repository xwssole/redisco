import inspect
import copy

class SharedModel(object):
    '''
    Proxy of redisco.model which support multiple proxies
    have shared access of one model.
    '''

    def __init__(self, model):
        if inspect.isclass(model):
            self.__dict__['_shared_model'] = None
            self.__dict__['_model_cls'] = model
        elif model is not None:
            model._has_pending_save = False
            self.__dict__['_shared_model'] = model
            self.__dict__['_model_cls'] = model.__class__
        self.__dict__['_proxy_modified'] = False
    
    def __call__(self, *args, **kwargs):
        model = self._model_cls(*args, **kwargs) 
        model._has_pending_save = False
        self.__dict__['_shared_model'] = model
        return self

    @property
    def model(self):
        return self._shared_model

    def __setattr__(self, k, v):
        if (self._shared_model._has_pending_save and 
                not self._proxy_modified): 
            model = self._shared_model
            model_cls = self._model_cls

            attr_dict = {}
            self.__dict__['_shared_model'] = copy.copy(self._shared_model)
            self._shared_model._id = model._id
            self._shared_model._modified_attrs = set()
            self.on_copy()
        attr = self._shared_model.attributes[k]
        attr.__set__(self._shared_model, v)
        self._shared_model._has_pending_save = True
        self.__dict__['_proxy_modified'] = True

    def __getattr__(self, k):
        return getattr(self._shared_model, k)

    def get_by_id(self, oid):
        return SharedModel(self._model_cls.objects.get_by_id(oid))

    def on_copy(self):
        pass

    def copy(self):
        proxy = SharedModel(self._shared_model)
        proxy.__dict__['_model_cls'] = self._model_cls
        proxy.__dict__['_proxy_modified'] = False
        return proxy

    def save(self):
        self._shared_model.save()
        self._shared_model._has_pending_save = False
        self.__dict__['_proxy_modified'] = False
