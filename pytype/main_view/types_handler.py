import json
from collections import defaultdict
from itertools import chain
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
        print(union_str, types)
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


def get_pysonar_calls(module_name, function_name, use_cache=False):
    def _get_data(_module_name, _function_name):
        qualname = _module_name + '.' + _function_name

        if use_cache:
            return DataCache.instance().pysonar_cache[qualname]
        else:
            return PysonarCalls.objects.filter(qualname=qualname)


    data = _get_data(module_name, function_name)
    if len(data) == 0:
        new_module = module_name + '.__init__'
        data = _get_data(new_module, function_name)

    if len(data) == 0:
        if module_name.startswith("test"):
            new_module = "tests." + module_name
            data = _get_data(new_module, function_name)

    return data


def get_monkey_calls(module_name, function_name, use_cache=False):
    if use_cache:
        return DataCache.instance().monkeytype_cache[(module_name, function_name)]
    else:
        return MonkeytypeCallTraces.objects.filter(module=module_name).filter(qualname=function_name)


def _function_view(module_name, function_name, use_cache=False):
    calls = get_monkey_calls(module_name, function_name, use_cache)
    pysonar_calls = get_pysonar_calls(module_name, function_name, use_cache)

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
    param_sim = {}
    for param, types in param_types.items():
        param_sim[param] = [_jaccard_sim(*types), _better_sim(*types), _better_sim(*tuple(reversed(types)))]

    new_param_types = {}
    for param, types in param_types.items():
        if len(types[0]) > len(types[1]):
            types[1] = chain(sorted(types[1]), empty_str_generator())
        else:
            types[0] = chain(sorted(types[0]), empty_str_generator())

        new_param_types[param] = [
            (x, y) for x, y in zip(*types)
        ]

    if len(return_types[0]) > len(return_types[1]):
        return_types[1] = chain(sorted(return_types[1]), empty_str_generator())
    else:
        return_types[0] = chain(sorted(return_types[0]), empty_str_generator())

    return_types = [
        (x, y) for x, y in zip(*return_types)
    ]

    param_types = new_param_types.items()
    return locals()
