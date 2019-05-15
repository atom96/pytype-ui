import json
from collections import defaultdict
from itertools import chain

from django.db.models import Q, F, Value, CharField
from django.db.models.functions import Substr, StrIndex, Cast
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from main_view.models import MonkeytypeCallTraces, PysonarCalls


def modules_view(request, module_prefix=''):
    i = 0 if module_prefix == '' else len(module_prefix.split('.'))
    modules = sorted({
        '.'.join(x['module'].split('.')[:i + 1])
        for x in MonkeytypeCallTraces.objects
            .filter(module__startswith=module_prefix)
            .values('module')
            .distinct()

    })

    if len(modules) == 1:
        return module_view(request, next(iter(modules)))

    return render(request, 'modules.html', locals())


def module_view(request, module_name):
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


def function_view(request, module_name, function_name):
    calls = MonkeytypeCallTraces.objects.filter(module=module_name).filter(qualname=function_name)

    pysonar_module = module_name
    if module_name.startswith("test"):
        pysonar_module = "tests." + pysonar_module
    pysonar_calls = PysonarCalls.objects.filter(qualname=pysonar_module + '.' + function_name)
    print(list(pysonar_calls))

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
            print(call.arg_types)
            call_params = json.loads(call.arg_types.replace("\\\"", "\""))
            for arg_name, arg_type in call_params.items():
                if arg_type != "?":
                    param_types[arg_name][1].add(arg_type)

        if call.return_type:
            return_types[1].add(call.return_type)

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

    print(param_types)

    param_types = new_param_types.items()

    return render(request, 'function.html', locals())
