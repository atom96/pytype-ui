from collections import defaultdict

from main_view.models import PysonarCalls, MonkeytypeCallTraces


class DataCache:
    INSTANCE = None

    def __init__(self):
        print("=====CACHE BUILDING====")
        pysonar_cache = defaultdict(list)
        monkeytype_cache = defaultdict(list)
        function_name_cache = defaultdict(set)
        module_name_cache = set()

        for pysonar_call in PysonarCalls.objects.all():
            pysonar_cache[pysonar_call.qualname].append(pysonar_call)

        for monkey_call in MonkeytypeCallTraces.objects.all():
            monkeytype_cache[(monkey_call.module, monkey_call.qualname)].append(monkey_call)
            function_name_cache[monkey_call.module].add(monkey_call.qualname)
            module_name_cache.add(monkey_call.module)

        self.pysonar_cache = pysonar_cache
        self.monkeytype_cache = monkeytype_cache
        self.function_name_cache = function_name_cache
        self.module_name_cache = module_name_cache
        print("=====CACHE FINISHED====")

    @classmethod
    def instance(cls):
        if cls.INSTANCE is None:
            cls.INSTANCE = DataCache()
        return cls.INSTANCE

    @classmethod
    def invalidate_cache(cls):
        print("====Cache invalidated========")
        cls.INSTANCE = None
