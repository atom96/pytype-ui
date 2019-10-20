from django.conf import settings

from main_view.models import MonkeytypeCallTraces, PysonarCalls


class DBRouter:
    def db_for_read(self, model, **hints):
        print(model, hints, settings)
        if model == MonkeytypeCallTraces:
            return settings.repo_name + '_types'
        if model == PysonarCalls:
            return settings.repo_name + '_pysonar'
        return 'default'
    #
    # def db_for_write(self, model, **hints):
    #     if isinstance(model, MonkeytypeCallTraces):
    #         return 'types'
    #     return 'default'
    #
    # def allow_relation(self, obj1, obj2, **hints):
    #     if obj1._meta.app_label == 'myapp2' or obj2._meta.app_label == 'myapp2':
    #         return True
    #     return None
    #
    # def allow_syncdb(self, db, model):
    #     if db == 'types':
    #         return False
    #     return True