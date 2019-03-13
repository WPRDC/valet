from django.db import models

class LastCached(models.Model):
    parameter = models.CharField(max_length=100)
    cache_date = models.CharField(max_length=100) # Store date as a string for now.

class SpaceCount(models.Model):
    zone = models.CharField(max_length=100)
    as_of = models.CharField(max_length=100) # Store date as a string for now.
    spaces = models.SmallIntegerField(null=True) # This value can be None when it has not been determined yet in the space-counts-and-rates CKAN resource.
    rate = models.FloatField(null=True) # This value can be None when it has not been determined yet in the space-counts-and-rates CKAN resource.
    rate_description = models.CharField(max_length=100,null=True)

    class Meta:
        verbose_name = "space count and rate"
        verbose_name_plural = "space counts and rates"
        unique_together = ('zone', 'as_of') # The combination of zone and as_of serve as a primary key.

    def __str__(self):
        return '{} | {}'.format(self.zone,self.as_of)

class LeaseCount(models.Model):
    zone = models.CharField(max_length=100)
    as_of = models.CharField(max_length=100) # Store date as a string for now.
    leases = models.SmallIntegerField()

    class Meta:
        verbose_name = "lease count"
        unique_together = ('zone', 'as_of') # The combination of zone and as_of serve as a primary key.

    def __str__(self):
        return '{} | {}'.format(self.zone,self.as_of)
