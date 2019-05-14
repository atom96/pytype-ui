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
