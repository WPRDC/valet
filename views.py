import re, ckanapi, time, datetime
from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django import forms

from datetime import timedelta

from pprint import pprint
from collections import defaultdict

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

def is_beginning_of_the_quarter(dt):
   return dt.day == 1 and dt.month in [1,4,7,10]

def add_quarter_to_date(d):
    if d.month in [1,4,7]:
        d = d.replace(month = d.month+3)
    elif d.month == 10:
        d = d.replace(month = 1, year = d.year+1)
    else:
        raise ValueError("The date {} does not correspond to the beginning of a quarter.".format(d))
    return d

def beginning_of_quarter(d):
    """Takes a date and returns the first date before
    that that corresponds to the beginning of the quarter."""
    if d == None:
        d = datetime.datetime.now().date()
    return d.replace(day=1, month=int((d.month-1)/3)*3+1).date()

def end_of_quarter(d):
    #print("The approach used in end_of_quarter may not work under some circumstances. Subtracting 31+30+31 days from 7/1 gives 3/31.")
    #return beginning_of_quarter(d + timedelta(days=31+30+31)) - timedelta(days=1)
    start_of_quarter = beginning_of_quarter(d)
    start_of_next_quarter = add_quarter_to_date(start_of_quarter)
    return start_of_next_quarter - timedelta(days = 1)

def date_to_quarter(d):
    year = d.year
    quarter_number = int((d.month-1)/3) + 1
    return (year, quarter_number)

def get_quarter_choices():
    earliest_date = datetime.date(2016,1,1)
    earliest_quarter = date_to_quarter(earliest_date)

    now = datetime.datetime.now()
    latest_quarter = date_to_quarter(now)

    # Note that the latest_quarter may be incomplete!
    xs = []
    d = beginning_of_quarter(now)
    while d >= earliest_date:
        xs.append(date_to_quarter(d))
        if d.month in [4,7,10]:
            d = d.replace(month = d.month-3)
        elif d.month == 1:
            d = d.replace(month = 10, year = d.year-1)
        else:
            raise ValueError("The date {} does not correspond to the beginning of a quarter.".format(d))
        print(d)

    choices = []
    for x in xs:
        quarter_code = "{} Q{}".format(x[0],x[1])
        choices.append( (quarter_code, quarter_code) )

    return choices

def convert_to_choices(xs):
    choices = []
    for x in xs:
        zone_code = re.sub(" - .*","",str(x))
        choices.append( (zone_code, x) )
    return choices

def get_number_of_rows(site,resource_id,API_key=None):
# On other/later versions of CKAN it would make sense to use
# the datastore_info API endpoint here, but that endpoint is
# broken on WPRDC.org.
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        results_dict = ckan.action.datastore_search(resource_id=resource_id,limit=1) # The limit
        # must be greater than zero for this query to get the 'total' field to appear in
        # the API response.
        count = results_dict['total']
    except:
        return None

    return count

def get_resource_data(site,resource_id,API_key=None,count=1000,offset=0,fields=None):
    # Use the datastore_search API endpoint to get <count> records from
    # a CKAN resource starting at the given offset and only returning the
    # specified fields in the given order (defaults to all fields in the
    # default datastore order).
    ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
    if fields is None:
        response = ckan.action.datastore_search(id=resource_id, limit=count, offset=offset)
    else:
        response = ckan.action.datastore_search(id=resource_id, limit=count, offset=offset, fields=fields)
    # A typical response is a dictionary like this
    #{u'_links': {u'next': u'/api/action/datastore_search?offset=3',
    #             u'start': u'/api/action/datastore_search'},
    # u'fields': [{u'id': u'_id', u'type': u'int4'},
    #             {u'id': u'pin', u'type': u'text'},
    #             {u'id': u'number', u'type': u'int4'},
    #             {u'id': u'total_amount', u'type': u'float8'}],
    # u'limit': 3,
    # u'records': [{u'_id': 1,
    #               u'number': 11,
    #               u'pin': u'0001B00010000000',
    #               u'total_amount': 13585.47},
    #              {u'_id': 2,
    #               u'number': 2,
    #               u'pin': u'0001C00058000000',
    #               u'total_amount': 7827.64},
    #              {u'_id': 3,
    #               u'number': 1,
    #               u'pin': u'0001C01661006700',
    #               u'total_amount': 3233.59}],
    # u'resource_id': u'd1e80180-5b2e-4dab-8ec3-be621628649e',
    # u'total': 88232}
    data = response['records']
    return data

def get_all_records(site,resource_id,API_key=None,chunk_size=5000):
    all_records = []
    failures = 0
    k = 0
    offset = 0 # offset is almost k*chunk_size (but not quite)
    row_count = get_number_of_rows(site,resource_id,API_key)
    if row_count == 0: # or if the datastore is not active
       print("No data found in the datastore.")
       success = False
    while len(all_records) < row_count and failures < 5:
        time.sleep(0.01)
        try:
            records = get_resource_data(site,resource_id,API_key,chunk_size,offset)
            if records is not None:
                all_records += records
            failures = 0
            offset += chunk_size
        except:
            failures += 1

        # If the number of rows is a moving target, incorporate
        # this step:
        #row_count = get_number_of_rows(site,resource_id,API_key)
        k += 1
        print("{} iterations, {} failures, {} records, {} total records".format(k,failures,len(records),len(all_records)))

        # Another option for iterating through the records of a resource would be to
        # just iterate through using the _links results in the API response:
        #    "_links": {
        #  "start": "/api/action/datastore_search?limit=5&resource_id=5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1",
        #  "next": "/api/action/datastore_search?offset=5&limit=5&resource_id=5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1"
        # Like this:
            #if r.status_code != 200:
            #    failures += 1
            #else:
            #    URL = site + result["_links"]["next"]

        # Information about better ways to handle requests exceptions:
        #http://stackoverflow.com/questions/16511337/correct-way-to-try-except-using-python-requests-module/16511493#16511493

    return all_records

def get_attributes(kind):
    from .credentials import site, ckan_api_key as API_key
    if kind in ['spaces']:
        from .credentials import spaces_resource_id as resource_id
    else:
        raise ValueError("attribute kind = {} not found".format(kind))

    attribute_dicts = get_all_records(site, resource_id, API_key)
    return attribute_dicts

def get_revenue(zone,start_date,end_date,start_hour,end_hour):
    """This should look like a SQL query."""
    pass

def get_space_count(zone,start_date,end_date):
    """Check the cache, and if it's been refreshed today, use the cached value."""
    # Run query on model.
    # If there's more than zero results and the dates are valid, return the space count
    # Otherwise, get it from the CKAN repository and save the new value.
    #       Schema
    #       as_of, zone, space_count, cache_date

    # Actually, in most cases, the desired date will be in the past, so the cache
    # should be fine.

    # It's necessary to define a date range for which some information is valid.
    # For instance, if we have lease counts for 2016-07-04 and 2018-02-02, all
    # intermediate dates should map to the 2016-07-04 value (as a first cut).

    # Data structure:
    # get_space_count(zone,start_date,end_date) needs space count for each
    # intermediate date.
    # Maybe a function like this space_count(zone,date) could be called once
    # for each date.

    # But before going to that extreme, how about getting the value that covers
    # the majority of the range (based on which waypoint date is closest)?

    # spaces = OrderedDict(date(2016,7,4):  {"401 - Downtown 1": 210,...},
    #           date(2018,2,2):  {"401 - Downtown 1": 271,...})


    # For now, just get all the data directly.

    attribute_dicts = get_attributes('spaces')

    def convert_string_to_date(s):
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()

    spaces = defaultdict(dict)
    for a in attribute_dicts:
        as_of = convert_string_to_date(a['as_of'])
        spaces[as_of][a['zone']] = a['spaces']

    updates = spaces.keys()
    closest_date = None
    min_diff = datetime.timedelta(days = 99999)
    for u in updates:
        diff = abs( u - start_date ) + abs( u - end_date )
        if diff < min_diff:
            min_diff = diff
            closest_date = u

    return spaces[closest_date][zone]



    # But maybe it's best to just pull all space counts, lease counts, and hourly rates
    # when the app is first run and keep them in some kind of persistent memcache,...
    # except I don't think that Django has this. One probably has to run redis
    # for this functionality.
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
    all_zones = get_zones()
    zone_choices = convert_to_choices(all_zones)
    zone_features = {'spaces': get_space_count(all_zones[0],datetime.date(2018,1,1),datetime.date(2018,3,31)),
            } #'rate':

    quarter_choices = get_quarter_choices()

    pprint(zone_choices)
    pprint(quarter_choices)

    class SpaceTimeForm(forms.Form):
        zone = forms.ChoiceField(choices=zone_choices)
        quarter = forms.ChoiceField(choices=quarter_choices)
        #input_field = forms.ChoiceField(choices=first_field_choices, help_text="(what you have in your spreadsheet)")
        #input_column_index = forms.CharField(initial='B',
        #    label="Input column",
        #    help_text='(the column in your spreadsheet where the values you want to convert can be found [e.g., "B"])',
        #    widget=forms.TextInput(attrs={'size':2}))
        #output_field = forms.ChoiceField(choices=first_field_choices, help_text="(what you want to convert your spreadsheet column to)")

    #template = loader.get_template('index.html')
    #context = {#'output': output,
    #            'zone_picker': SpaceTimeForm().as_p()}
    context = {'zone_picker': SpaceTimeForm().as_p(),
            'zone_features': zone_features}
    return render(request, 'valet/index.html', context)

    #return HttpResponse(template.render(context, request))
    #return HttpResponse("This page shows parking reports by zone/lot. <br>Choose a zone: {}<br>".format( SpaceTimeForm().as_p() ))

