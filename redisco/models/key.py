class Key(unicode):
    def __getitem__(self, key):
        return Key(u"%s:%s" % (self, key))
