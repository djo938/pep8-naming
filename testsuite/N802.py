#: Okay
def ok():
    pass
#: N802
def __bad():
    pass
#: N802
def bad__():
    pass
#: Okay
def __bad__():
    pass
#: Okay
def _ok():
    pass
#: N802
def ok_ok_ok_ok():
    pass
#: N802
def _somehow_good():
    pass
#: N802
def go_od_():
    pass
#: N802
def _go_od_():
    pass
#: N802
def NotOK():
    pass
#: N802
def _():
    pass
#: N802
class Foo(object):
    def __method(self):
        pass
#: Okay
class Foo(object):
    def __method__(self):
        pass
#: Okay
class ClassName(object):
    def __method__(self):
        pass
#: Okay
class ClassName(object):
    def notOk(self):
        pass
#: N802
class ClassName(object):
    def method(self):
        def __bad():
            pass
#: Okay
def setUp():
    pass

#: Okay
def tearDown():
    pass

#: Okay
class TestCase:
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def setUpClass(self):
        pass
    def tearDownClass(self):
        pass
