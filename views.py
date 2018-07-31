import re, ckanapi
from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django import forms

from pprint import pprint

from .util import parking_days_in_range

def get_zones():
    zones = ["301 - Sheridan Harvard Lot",
        "302 - Sheridan Kirkwood Lot",
        "304 - Tamello Beatty Lot",
        "307 - Eva Beatty Lot",
        "308 - Harvard Beatty Lot",
        "311 - Ansley Beatty Lot",
        "314 - Penn Circle NW Lot",
        "321 - Beacon Bartlett Lot",
        "322 - Forbes Shady Lot",
        "323 - Douglas Phillips Lot",
        "324 - Forbes Murray Lot",
        "325 - JCC/Forbes Lot",
        "301 - Sheridan Harvard Lot",
        "328 - Ivy Bellefonte Lot",
        "329 - Centre Craig",
        "331 - Homewood Zenith Lot",
        "334 - Taylor Street Lot",
        "335 - Friendship Cedarville Lot",
        "337 - 52nd & Butler Lot",
        "338 - 42nd & Butler Lot",
        "341 - 18th & Sidney Lot",
        "342 - East Carson Lot",
        "343 - 19th & Carson Lot",
        "344 - 18th & Carson Lot",
        "345 - 20th & Sidney Lot",
        "351 - Brownsville & Sandkey Lot",
        "354 - Walter/Warrington Lot",
        "355 - Asteroid Warrington Lot",
        "357 - Shiloh Street Lot",
        "361 - Brookline Lot",
        "363 - Beechview Lot",
        "369 - Main/Alexander Lot",
        "371 - East Ohio Street Lot",
        "375 - Oberservatory Hill Lot",
        "401 - Downtown 1",
        "402 - Downtown 2",
        "403 - Uptown",
        "404 - Strip Disctrict",
        "405 - Lawrenceville",
        "406 - Bloomfield (On-street)",
        "407 - Oakland 1",
        "408 - Oakland 2",
        "409 - Oakland 3",
        "410 - Oakland 4",
        "411 - Shadyside",
        "412 - East Liberty",
        "413 - Squirrel Hill",
        "414 - Mellon Park",
        "415 - SS & SSW",
        "416 - Carrick",
        "417 - Allentown",
        "418 - Beechview",
        "419 - Brookline",
        "420 - Mt. Washington",
        "421 - NorthSide",
        "422 - Northshore",
        "423 - West End",
        "424 - Technology Drive",
        "425 - Bakery Sq",
        "426 - Hill District",
        "427 - Knoxville"]
    return zones

def convert_to_choices(xs):
    choices = []
    for x in xs:
        zone_code = re.sub(" - .*","",str(x))
        choices.append( (zone_code, x) )
    return choices

def get_revenue(zone,start_date,end_date,start_hour,end_hour):
    """This should look like a SQL query."""
    pass

def get_space_count(zone,start_date,end_date):
    pass

def get_lease_count(zone,start_date,end_date):
    pass

def get_hourly_rate(zone,start_date,end_date):
    pass


def calculate_utilization(zone,start_date,end_date,start_hour,end_hour):
    """Utilization = (Revenue from parking purchases) / { ([# of spots] - 0.85*[# of leases]) * (rate per hour) * (the number of days in the time span where parking is not free) * (duration of slot in hours) }"""
    revenue = get_revenue(zone,start_date,end_date,start_hour,end_hour)
    effective_space_count = get_space_count(zone,start_date,end_date) - 0.85*get_lease_count(zone,start_date,end_date)
    non_free_days = parking_days_in_range(start_date,end_date)
    slot_duration = end_hour - start_hour
    assert end_hour > start_hour
    utilization = revenue/effective_space_count/hourly_rate/non_free_days/slot_duration
    return utilization

def index(request):

    zone_choices = convert_to_choices(get_zones())

    class ZoneForm(forms.Form):
        zone = forms.ChoiceField(choices=zone_choices)
        #resource = forms.ChoiceField(choices=first_resource_choices)
        #input_field = forms.ChoiceField(choices=first_field_choices, help_text="(what you have in your spreadsheet)")
        #input_column_index = forms.CharField(initial='B',
        #    label="Input column",
        #    help_text='(the column in your spreadsheet where the values you want to convert can be found [e.g., "B"])',
        #    widget=forms.TextInput(attrs={'size':2}))
        #output_field = forms.ChoiceField(choices=first_field_choices, help_text="(what you want to convert your spreadsheet column to)")

    #template = loader.get_template('index.html')
    #context = {#'output': output,
    #            'zone_picker': ZoneForm().as_p()}

    #return HttpResponse(template.render(context, request))
    return HttpResponse("This page shows parking reports by zone/lot. <br>Choose a zone: {}<br>".format( ZoneForm().as_p() ))

