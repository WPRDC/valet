from django.contrib import admin

from .models import LastCached, SpaceCount, LeaseCount

class LastCachedAdmin(admin.ModelAdmin):
    list_display = ['parameter', 'cache_date']

    search_fields = list_display
    ordering = ['parameter']

admin.site.register(LastCached, LastCachedAdmin)


class SpaceCountAdmin(admin.ModelAdmin):
    list_display = ['zone', 'as_of', 'spaces', 'rate']

    search_fields = list_display
    ordering = ['as_of', 'zone']

admin.site.register(SpaceCount, SpaceCountAdmin)


class LeaseCountAdmin(admin.ModelAdmin):
    list_display = ['zone', 'as_of', 'leases']

    search_fields = list_display
    ordering = ['as_of', 'zone']

admin.site.register(LeaseCount, LeaseCountAdmin)
