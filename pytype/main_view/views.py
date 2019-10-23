import os
from itertools import chain
from statistics import mean, StatisticsError

from django.conf import settings
from django.shortcuts import render

# Create your views here.
from main_view.data_cache import DataCache
from main_view.models import MonkeytypeCallTraces
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

    if len(all_modules) == 1  and module_prefix == all_modules[0]:
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

    return render(request, 'similarity.html', locals())


def function_view(request, repo_name, module_name, function_name):
    _update_repo_name(repo_name)
    return render(request, 'function.html', _function_view(module_name, function_name))


def all_packages_view(request):
    repos = sorted([x for x in os.listdir('/home/arek/Pulpit/mgr') if not x.startswith('.')], key=lambda x: x.lower())
    return render(request, 'main.html', locals())
