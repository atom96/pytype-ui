import json
import os
from collections import defaultdict
from itertools import chain
from statistics import mean
from typing import List

from django.conf import settings
from django.db.models import Q, F, Value, CharField
from django.db.models.functions import Substr, StrIndex, Cast
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from main_view.models import MonkeytypeCallTraces, PysonarCalls


def modules_view(request, repo_name, module_prefix=''):
    settings.repo_name = repo_name
    i = 0 if module_prefix == '' else len(module_prefix.split('.'))
    modules = sorted({
        '.'.join(x['module'].split('.')[:i + 1])
        for x in MonkeytypeCallTraces.objects
            .filter(module__startswith=module_prefix)
            .values('module')
            .distinct()

    })

    add_flat_module = len(modules) > 1 and any(module == module_prefix for module in modules)

    if len(modules) == 1:
        return module_view(request, repo_name, next(iter(modules)))

    return render(request, 'modules.html', locals())


def module_view(request, repo_name, module_name, add_init='n'):
    settings.repo_name = repo_name
    functions = (x['qualname']
                 for x in MonkeytypeCallTraces.objects
                     .filter(module=module_name)
                     .values('qualname')
                     .distinct()
                 )

    return render(request, 'module.html', locals())


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

def _function_view(module_name, function_name, add_init = 'n'):
    calls = MonkeytypeCallTraces.objects.filter(module=module_name).filter(qualname=function_name)

    pysonar_module = module_name
    if module_name.startswith("test"):
        pysonar_module = "tests." + pysonar_module
    if add_init == 'y':
        pysonar_module += '.__init__'
    print(pysonar_module)
    pysonar_calls = PysonarCalls.objects.filter(qualname=pysonar_module + '.' + function_name)

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
            call_params = json.loads(call.arg_types.replace("\\\"", "\""))
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


def _similarity_view(module_name, add_init='n'):
    functions = (x['qualname']
                 for x in MonkeytypeCallTraces.objects
                     .filter(module=module_name)
                     .values('qualname')
                     .distinct()
                 )


    ret_sim = []
    param_sim = []
    for function in functions:
        function_stats = _function_view(module_name, function, add_init)
        ret_sim.append(function_stats['return_sim'])
        param_sim.append(function_stats['param_sim'])

    sim = mean(
        chain(
            (e[0] for e in ret_sim),
            (e[0] for d in param_sim for e in d.values())
        )
    )

    monkey_share = mean(
        chain(
            (e[1] for e in ret_sim),
            (e[1] for d in param_sim for e in d.values())
        )
    )

    sonar_share = mean(
        chain(
            (e[2] for e in ret_sim),
            (e[2] for d in param_sim for e in d.values())
        )
    )

    return locals()


def similarity_view(request, repo_name, module_name, add_init):
    settings.repo_name = repo_name
    return render(request, 'similarity.html', _similarity_view(module_name, add_init))


def _modules_similarity_view(module_prefix, seen_set):
    if module_prefix in seen_set:
        return []
    else:
        seen_set.add(module_prefix)

    i = 0 if module_prefix == '' else len(module_prefix.split('.'))
    modules = sorted({
        '.'.join(x['module'].split('.')[:i + 1])
        for x in MonkeytypeCallTraces.objects
            .filter(module__startswith=module_prefix)
            .values('module')
            .distinct()

    })
    add_flat_module = len(modules) > 1 and any(module == module_prefix for module in modules)

    if len(modules) == 1:
        sim = _similarity_view(next(iter(modules)))

        return list(
            chain(
                (e for e in sim['ret_sim']),
                (e for d in sim['param_sim'] for e in d.values())
            ))
    else:
        result = []
        if add_flat_module:
            print("====FLAT MODULE DETECTED ====")
            sim = _similarity_view(module_prefix, 'y')

            result = list(
                chain(
                    (e for e in sim['ret_sim']),
                    (e for d in sim['param_sim'] for e in d.values())
                ))
        result += [
            x for module in modules for x in _modules_similarity_view(module, seen_set)
        ]
        return result


def modules_similarity_view(request, repo_name, module_prefix=''):
    settings.repo_name = repo_name
    stats = _modules_similarity_view(module_prefix, set())
    sim = mean(s[0] for s in stats)

    monkey_share = mean(s[1] for s in stats)

    sonar_share = mean(s[2] for s in stats)

    return render(request, 'similarity.html', locals())


def function_view(request, repo_name, module_name, function_name, add_init='n'):
    settings.repo_name = repo_name
    return render(request, 'function.html', _function_view(module_name, function_name))

def all_packages_view(request):
    repos = sorted([x for x in os.listdir('/home/arek/Pulpit/mgr') if not x.startswith('.')], key=lambda x: x.lower())
    return render(request, 'main.html', locals())
