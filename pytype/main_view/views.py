import os
from itertools import chain
from statistics import mean, StatisticsError

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

# Create your views here.
from main_view.data_cache import DataCache
from main_view.models import MonkeytypeCallTraces, PysonarCalls
from main_view.types_handler import _function_view


def _update_repo_name(repo_name):
    if getattr(settings, 'repo_name', None) != repo_name:
        settings.repo_name = repo_name
        DataCache.invalidate_cache()


def modules_view(request, repo_name, module_prefix=''):
    _update_repo_name(repo_name)
    i = 0 if module_prefix == '' else len(module_prefix.split('.'))

    all_modules = (MonkeytypeCallTraces.objects
                   .filter(module__startswith=module_prefix)
                   .values('module')
                   .distinct())

    if len(all_modules) == 1 and all_modules[0] == module_prefix:
        return module_view(request, repo_name, all_modules[0])

    modules = sorted({
        '.'.join(x['module'].split('.')[:i + 1])
        for x in all_modules
    })

    add_flat_module = any(module == module_prefix for module in modules)
    if add_flat_module:
        modules = filter(lambda x: x != module_prefix, modules)

    return render(request, 'modules.html', locals())


def module_view(request, repo_name, module_name):
    _update_repo_name(repo_name)
    functions = (x['qualname']
                 for x in MonkeytypeCallTraces.objects
                     .filter(module=module_name)
                     .values('qualname')
                     .distinct()
                 )

    return render(request, 'module.html', locals())


def _similarity_view(module_name):
    # functions = (x['qualname']
    #              for x in MonkeytypeCallTraces.objects
    #                  .filter(module=module_name)
    #                  .values('qualname')
    #                  .distinct()
    #              )
    functions = DataCache.instance().function_name_cache[module_name]

    ret_sim = []
    param_sim = []
    for function in functions:
        function_stats = _function_view(module_name, function, True)
        ret_sim.append(function_stats['return_sim'])
        param_sim.append(function_stats['param_sim'])

    try:
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
    except StatisticsError:
        print(locals())
        raise

    return locals()


def similarity_view(request, repo_name, module_name):
    _update_repo_name(repo_name)
    return render(request, 'similarity.html', _similarity_view(module_name))


def _modules_similarity_view(module_prefix, seen_set):
    if module_prefix in seen_set:
        return []
    else:
        seen_set.add(module_prefix)

    i = 0 if module_prefix == '' else len(module_prefix.split('.'))

    all_modules = [x for x in DataCache.instance().module_name_cache if x.startswith(module_prefix)]

    modules = sorted({
        '.'.join(x.split('.')[:i + 1])
        for x in all_modules
    })

    add_flat_module = len(modules) > 1 and any(module == module_prefix for module in modules)

    if len(all_modules) == 1 and module_prefix == all_modules[0]:
        sim = _similarity_view(next(iter(modules)))

        return list(
            chain(
                (e for e in sim['ret_sim']),
                (e for d in sim['param_sim'] for e in d.values())
            ))
    else:
        result = []
        if add_flat_module:
            sim = _similarity_view(module_prefix)

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
    _update_repo_name(repo_name)
    stats = _modules_similarity_view(module_prefix, set())
    sim = mean(s[0] for s in stats)

    monkey_share = mean(s[1] for s in stats)

    sonar_share = mean(s[2] for s in stats)
    module_name = module_prefix

    return render(request, 'similarity.html', locals())


def function_view(request, repo_name, module_name, function_name):
    _update_repo_name(repo_name)
    return render(request, 'function.html', _function_view(module_name, function_name))


def all_packages_view(request):
    repos = sorted([x for x in os.listdir(settings.REPOS_DIR) if not x.startswith('.')], key=lambda x: x.lower())
    return render(request, 'main.html', locals())


def _get_functions(repo_name):
    _update_repo_name(repo_name)

    def _is_normal_function(name):
        splitted = name.split('.')

        if splitted[-1].startswith('test_') or splitted[-1].startswith('tests_'):
            return False
        return True

    functions_mt_dict = {'.'.join(x): x
                         for x in MonkeytypeCallTraces.objects
                             .values_list('module', 'qualname')
                             .distinct()
                         if _is_normal_function('.'.join(x))
                         }
    functions_mt = set(functions_mt_dict.keys())
    function_ps = set()
    functions_ps_dict = {}
    # function_ps = {x['qualname'] for x in PysonarCalls.objects.values('qualname').distinct()}
    for function in PysonarCalls.objects.values('qualname').distinct():
        function = function['qualname']
        splitted = function.split('.')

        if not _is_normal_function(function):
            continue
        ps_function = function

        if not ps_function in functions_mt:
            for index in range(len(splitted) - 1):
                test = '.'.join(splitted[index:])
                if test in functions_mt:
                    ps_function = test
                    break
                elif splitted[index] == '__init__':
                    init_module = '.'.join(splitted[:index] + splitted[index + 1:])
                    if init_module in functions_mt:
                        ps_function = init_module
        functions_ps_dict[ps_function] = function
        function_ps.add(ps_function)
    return functions_mt, function_ps, functions_mt_dict, functions_ps_dict


def num_of_functions_view(request):
    result = {}
    for repo in [x for x in os.listdir(settings.REPOS_DIR) if not x.startswith('.')]:
        print(repo)
        functions_mt, function_ps, _, _ = _get_functions(repo)
        result[repo] = {
            'ps and mt': len(function_ps & functions_mt),
            'only_mt': len(functions_mt - function_ps),
            'only_ps': len(function_ps - functions_mt)
        }

    l = []
    for repo_name in sorted(result):
        l.append(
            '|'.join(map(str, [
                repo_name,
                result[repo_name]['only_mt'],
                result[repo_name]['ps and mt'],
                result[repo_name]['only_ps']
            ])
                     ))

        print(l[-1])

    return JsonResponse(l, safe=False)


def set_of_functions_view(request, repo_name):
    result = {}

    functions_mt, function_ps, _, _ = _get_functions(repo_name)

    result[repo_name] = {
        'ps and mt': sorted(function_ps & functions_mt),
        'only_mt': sorted(functions_mt - function_ps),
        'only_ps': sorted(function_ps - functions_mt)
    }

    return JsonResponse(result, safe=False)


def new_similarity_repo(request, repo_name):
    result = {}

    for repo_name in [x for x in os.listdir(settings.REPOS_DIR) if not x.startswith('.')]:
        functions_mt, function_ps, mt_dict, ps_dict = _get_functions(repo_name)
        sim = []
        mt = []
        ps = []
        l = len(function_ps & functions_mt)
        for i, function in enumerate(function_ps & functions_mt):
            i += 1
            print('function', i, '/', l)

            view = _function_view(
                module_name=mt_dict[function][0],
                function_name=mt_dict[function][1],
                ps_name=ps_dict[function],
                use_cache=True
            )

            for e in chain([view['return_sim']], view['param_sim'].values()):
                sim.append(e[0])
                mt.append(e[1])
                ps.append(e[2])

        result[repo_name] = {
            'sim': sum(sim) / len(sim) if sim else 0,
            'mt': sum(mt) / len(mt) if mt else 0,
            'ps': sum(ps) / len(ps) if ps else 0
        }


    return JsonResponse(
        result
    )
