from django.db import models


class MonkeytypeCallTraces(models.Model):
    created_at = models.TextField(blank=True, primary_key=True)
    module = models.TextField(blank=True, null=True)
    qualname = models.TextField(blank=True, null=True)
    arg_types = models.TextField(blank=True, null=True)
    return_type = models.TextField(blank=True, null=True)
    yield_type = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'monkeytype_call_traces'

    def __lt__(self, other):
        return self.created_at < other.created_at

    def __repr__(self):
        return 'MonkeytypeCallTraces' + str(self.__dict__)

    @classmethod
    def type_to_str(cls, type):
        # if type["module"] in ["builtins", "typing"]:
        str_type = type["qualname"]
        # else:
        #     str_type = "{}.{}".format(type["module"],  type["qualname"])


        if "elem_types" in type:
            str_type = '{}[{}]'.format(str_type, ','.join(map(cls.type_to_str, type["elem_types"])))
        return str_type

class PysonarCalls(models.Model):
    rowid = models.IntegerField(primary_key=True)
    qualname = models.TextField(blank=True, null=True)
    arg_types = models.TextField(blank=True, null=True)
    return_type = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pysonar_calls'
