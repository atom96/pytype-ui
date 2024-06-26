import json
from collections import defaultdict, OrderedDict
from itertools import chain, zip_longest
from typing import List

from main_view.data_cache import DataCache
from main_view.models import MonkeytypeCallTraces, PysonarCalls


def empty_str_generator():
    while True:
        yield ""


def _smart_splitter(string):
    depth = 0
    start = 0
    result = []
    for i, c in enumerate(string + ','):
        if c == ',' and depth == 0:
            result.append(string[start: i].strip())
            start = i + 1
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1

    return result


def _resolve_union(union_str: str) -> List[str]:
    if not union_str.startswith('Union['):
        return [union_str]
    else:
        types = _smart_splitter(union_str[len("Union["): -1])
        return [
            i for t in types for i in _resolve_union(t)
        ]


def _jaccard_sim(set1, set2):
    try:
        return len(set1 & set2) / len(set1 | set2)
    except ZeroDivisionError:
        return 1.0


def _better_sim(set1, set2):
    try:
        return len(set1 - set2) / len(set1 | set2)
    except ZeroDivisionError:
        return 0.0


def get_pysonar_calls(module_name, function_name, ps_name, use_cache=False):
    def _to_qualname(_module_name, _function_name):
        return _module_name + '.' + _function_name

    def _get_data(qualname):
        if use_cache:
            return DataCache.instance().pysonar_cache[qualname]
        else:
            return PysonarCalls.objects.filter(qualname=qualname)

    if ps_name is not None:
        return _get_data(ps_name)

    data = _get_data(_to_qualname(module_name, function_name))
    if len(data) == 0:
        splitted = module_name.split('.')
        for index in range(len(splitted) + 1):
            new_module = '.'.join(splitted[:index] + ['__init__'] + splitted[index:])
            print(_to_qualname(new_module, function_name))
            data = _get_data(_to_qualname(new_module, function_name))
            if len(data) > 0:
                break

    if len(data) == 0:
        if module_name.startswith("test"):
            new_module = "tests." + module_name
            data = _get_data(_to_qualname(new_module, function_name))
        else:
            new_module = 'src.' + module_name
            data = _get_data(_to_qualname(new_module, function_name))
    return data


def get_monkey_calls(module_name, function_name, use_cache=False):
    if use_cache:
        return DataCache.instance().monkeytype_cache[(module_name, function_name)]
    else:
        return MonkeytypeCallTraces.objects.filter(module=module_name).filter(qualname=function_name)


def _function_view(module_name, function_name, ps_name=None, use_cache=False):
    calls = get_monkey_calls(module_name, function_name, use_cache)
    pysonar_calls = get_pysonar_calls(module_name, function_name, ps_name, use_cache)

    param_types = defaultdict(lambda: [set(), set()])
    return_types = [set(), set()]

    for call in calls:
        if call.arg_types:
            call_params = json.loads(call.arg_types)
            for arg_name, arg_type in call_params.items():
                param_types[arg_name][0].add(MonkeytypeCallTraces.type_to_str(arg_type))

        if call.return_type:
            return_type = json.loads(call.return_type)
            return_types[0].add(MonkeytypeCallTraces.type_to_str(return_type))

    for call in pysonar_calls:
        if call.arg_types:
            try:
                call_params = json.loads(call.arg_types.replace("\\\"", "\""))
            except json.JSONDecodeError:
                print("Called with:'", call.arg_types, "")
                raise
            for arg_name, arg_type in call_params.items():
                if arg_type != "?":
                    for flat_type in _resolve_union(arg_type):
                        param_types[arg_name][1].add(flat_type)

        if call.return_type:
            for flat_type in _resolve_union(call.return_type):
                return_types[1].add(flat_type)

    return_sim = [_jaccard_sim(*return_types), _better_sim(*return_types), _better_sim(*tuple(reversed(return_types)))]
    param_sim = OrderedDict()
    for param, types in sorted(param_types.items()):
        param_sim[param] = [_jaccard_sim(*types), _better_sim(*types), _better_sim(*tuple(reversed(types)))]

    new_param_types = OrderedDict()
    for param, types in sorted(param_types.items()):
        new_param_types[param] = [
            (x, y) for x, y in zip_longest(*[sorted(l) for l in types], fillvalue='')
        ]

    return_types = [
        (x, y) for x, y in zip_longest(*[sorted(l) for l in return_types], fillvalue='')
    ]

    param_types = new_param_types.items()
    return locals()
