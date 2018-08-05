from django.db import models

class LastCached(models.Model):
    parameter = models.CharField(max_length=100)
    cache_date = models.CharField(max_length=100) # Store date as a string for now.

class SpaceCount(models.Model):
    zone = models.CharField(max_length=100)
    as_of = models.CharField(max_length=100) # Store date as a string for now.
    spaces = models.SmallIntegerField()
    rate = models.FloatField()

    class Meta:
        verbose_name = "space count and rate"
        verbose_name_plural = "space counts and rates"

    def __str__(self):
        return '{} | {}'.format(self.zone,self.as_of)
