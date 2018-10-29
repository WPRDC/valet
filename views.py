import re, ckanapi, time
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader
from django import forms

from datetime import datetime, timedelta, date

from pprint import pprint
from collections import defaultdict, OrderedDict

from .models import SpaceCount, LeaseCount, LastCached
from .util import parking_days_in_range, format_as_table, format_row, format_date
from .proto_get_revenue import get_revenue_and_count, set_table, clear_table

ref_time = 'purchase_time'

hour_ranges = OrderedDict([('8am-10am', {'start_hour': 8, 'end_hour': 10}),
               ('10am-2pm', {'start_hour': 10, 'end_hour': 14}),
               ('2pm-6pm', {'start_hour': 14, 'end_hour': 18})])
# [ ] Add final hour range/ranges for the Southside (maybe picking only particular days, so a different query might be needed).

def get_zones():
    zones = ["301 - Sheridan Harvard Lot",
        "302 - Sheridan Kirkwood Lot",
        "304 - Tamello Beatty Lot",
        "307 - Eva Beatty Lot",
        #"308 - Harvard Beatty Lot", # There's no space counts for this one.
        "311 - Ansley Beatty Lot",
        "314 - Penn Circle NW Lot",
        "321 - Beacon Bartlett Lot",
        "322 - Forbes Shady Lot",
        "323 - Douglas Phillips Lot",
        "324 - Forbes Murray Lot",
        "325 - JCC/Forbes Lot",
        "328 - Ivy Bellefonte Lot",
        #"329 - Centre Craig", # There's no space counts for this one.
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
        "427 - Knoxville" # [ ] There's no data for this one yet.
        ]
    return zones

def convert_string_to_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

def convert_date_to_datetime(d):
    """Takes a date and returns the corresponding datetime,
    with midnight as the time. The result is time-zone-naive."""
    return datetime(year=d.year, month=d.month, day=d.day)

def beginning_of_month(d):
    """Takes a date (or datetime) and returns the first date before
    that that corresponds to the beginning of the month."""
    now = datetime.now()
    if d == None:
        d = now
    if type(d) == type(now):
        d = d.date()
    return d.replace(day=1)

def end_of_month(d):
    if d.month == 12:
        d = d.replace(year = d.year + 1, month = 1)
    else:
        d = d.replace(month = d.month + 1)
    start_of_next_month = beginning_of_month(d)
    return start_of_next_month - timedelta(days = 1)

def add_month_to_date(d):
    if d.month == 12:
        d = d.replace(year = d.year + 1, month = 1)
    else:
        d = d.replace(month = d.month + 1)
    return d

def dates_for_month(year,month):
    start_date = beginning_of_month(date(year,month,1))
    end_date = beginning_of_month(add_month_to_date(start_date))
    return start_date, end_date

def datetimes_for_month(year,month):
    start_date, end_date = dates_for_month(year,month)
    start_dt = convert_date_to_datetime(start_date)
    end_dt = convert_date_to_datetime(end_date)
    return start_dt, end_dt, start_date, end_date

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
    """Takes a date (or datetime) and returns the first date before
    that that corresponds to the beginning of the quarter."""
    now = datetime.now()
    if d == None:
        d = now
    if type(d) == type(now):
        d = d.date()
    return d.replace(day=1, month=int((d.month-1)/3)*3+1)

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

def quarter_to_datetimes(q):
    if re.match(' Q',q) is not None:
        raise RuntimeError("{} is not a properly formed quarter (which should be of the form '2016 Q2').".format(q))
    yr, q_digit = q.split(' Q')
    year = int(yr)
    quarter_number = int(q_digit)
    month = (quarter_number-1)*3 + 1
    start_date = date(year,month,1)
    end_date = end_of_quarter(start_date) + timedelta(days=1)
    start_dt = convert_date_to_datetime(start_date)
    end_dt = convert_date_to_datetime(end_date)
    return start_dt, end_dt, start_date, end_date

def verify_quarter(d):
    year, quarter = date_to_quarter(d)
    too_soon= False
    too_far_back = False
    if end_of_quarter(d) >= datetime.now().date():
        print("Records for this date have not yet been collected.")
        too_soon = True
    elif beginning_of_quarter(d) < date(2012,7,23):
        print("This date is definitely before any available parking meter data.")
        too_far_back = True
    return too_far_back, too_soon


def get_quarter_choices():
    earliest_date = date(2016,1,1)
    earliest_quarter = date_to_quarter(earliest_date)

    now = datetime.now()
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

    choices = []
    for x in xs:
        quarter_code = "{} Q{}".format(x[0],x[1])
        quarter_code_label = str(quarter_code)
        if len(choices) == 0:
            addendum = ' (incomplete)'
            quarter_code_label += addendum
        choices.append( (quarter_code, quarter_code_label) )

    return choices

def convert_to_choices(xs):
    choices = []
    for x in xs:
        #zone_code = re.sub(" - .*","",str(x))
        zone_code = x
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
    if row_count is None:
        print("Some error was encountered when trying to obtain the row count for resource {} from {}".format(resource_id,site))
        success = False
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
    if kind in ['spaces', 'rates']:
        try:
            last_cached = LastCached.objects.get(parameter = kind)
            last_cached_d_str = last_cached.cache_date
            last_cached_date = datetime.strptime(last_cached_d_str, "%Y-%m-%d").date()
        except LastCached.DoesNotExist as e:
            last_cached = None
        table_data = SpaceCount.objects.all()
        from .credentials import spaces_resource_id as resource_id
    elif kind in ['leases']:
        try:
            last_cached = LastCached.objects.get(parameter = kind)
            last_cached_d_str = last_cached.cache_date
            last_cached_date = datetime.strptime(last_cached_d_str, "%Y-%m-%d").date()
        except LastCached.DoesNotExist as e:
            last_cached = None
        table_data = LeaseCount.objects.all()
        from .credentials import leases_resource_id as resource_id
    else:
        raise ValueError("attribute kind = {} not found".format(kind))

    today = datetime.now().date()
    if len(table_data) == 0 or (last_cached is not None and (today - last_cached_date > timedelta(days=3))):
        # Build/refresh cache
        print("Pulling and caching data.")
        attribute_dicts = get_all_records(site, resource_id, API_key)
        # Cache data in the corresponding table.
        if kind in ['spaces', 'rates']:
            for a in attribute_dicts:
                if a['zone'] == '424 - Technology Drive':
                    a['rate'] = 2
                    print("For now, just coerce this rate to $2 per hour, but eventually something smarter should be done.")
                fetched = SpaceCount.objects.filter(zone = a['zone'], as_of = a['as_of']).first()
                if fetched is None:
                    sc = SpaceCount(zone = a['zone'],
                            as_of = a['as_of'],
                            spaces = a['spaces'],
                            rate = a['rate'])
                    sc.save()
                elif fetched.spaces != a['spaces'] or fetched.rate != a['rate']:
                    fetched.spaces = a['spaces']
                    fetched.rate = a['rate']
                    fetched.save()
                # Otherwise, it doesn't need to be updated.

            if len(attribute_dicts) > 0:
                if last_cached is None: # This logic should be replacable with update_or_create.
                    LastCached(parameter = kind, cache_date = datetime.strftime(today, "%Y-%m-%d")).save()
                else:
                    last_cached.cache_date = datetime.strftime(today, "%Y-%m-%d")
                    last_cached.save()
        elif kind in ['leases']:
            for a in attribute_dicts:
                if 'active_leases' not in a or a['active_leases'] is None:
                    a['active_leases'] = 0
                a['leases'] = a['active_leases'] # Standardize the field name within this function and the LeaseCount model.
                fetched = LeaseCount.objects.filter(zone = a['zone'], as_of = a['as_of']).first()
                if fetched is None:
                    lc = LeaseCount(zone = a['zone'],
                            as_of = a['as_of'],
                            leases = a['leases'])
                    lc.save()
                elif fetched.leases != a['leases']:
                    fetched.leases = a['leases']
                    fetched.save()
                # Otherwise, it doesn't need to be updated.

            if len(attribute_dicts) > 0:
                if last_cached is None: # This logic should be replacable with update_or_create.
                    LastCached(parameter = kind, cache_date = datetime.strftime(today, "%Y-%m-%d")).save()
                else:
                    last_cached.cache_date = datetime.strftime(today, "%Y-%m-%d")
                    last_cached.save()
    else:
        print("Using data pulled from local database.")
        attribute_dicts = []
        for row in table_data:
            if kind in ['spaces', 'rates']:
                attribute_d = {'zone': row.zone,
                        'as_of': row.as_of,
                        'spaces': row.spaces,
                        'rate': row.rate}
            elif kind in ['leases']:
                attribute_d = {'zone': row.zone,
                        'as_of': row.as_of,
                        'leases': row.leases}
            else:
                raise ValueError("Unknown parameter = {}".format(kind))
            attribute_dicts.append(attribute_d)

    return attribute_dicts

def get_space_count_and_rate(zone,start_date,end_date):
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

    spaces = defaultdict(dict)
    rates = defaultdict(dict)
    for a in attribute_dicts:
        as_of = convert_string_to_date(a['as_of'])
        if 'spaces' in a:
            spaces[as_of][a['zone']] = a['spaces']
        if 'rate' in a:
            rates[as_of][a['zone']] = a['rate']

    updates = spaces.keys()
    closest_date = None
    min_diff = timedelta(days = 99999)
    for u in updates:
        diff = abs( u - start_date ) + abs( u - end_date )
        if diff < min_diff:
            min_diff = diff
            closest_date = u

    return spaces[closest_date][zone], rates[closest_date][zone]



    # But maybe it's best to just pull all space counts, lease counts, and hourly rates
    # when the app is first run and keep them in some kind of persistent memcache,...
    # [ ] Look into installing Memcached.

def get_x_count(parameter,zone,start_date,end_date):
    attribute_dicts = get_attributes(parameter)

    params = defaultdict(dict)
    for a in attribute_dicts:
        as_of = convert_string_to_date(a['as_of'])
        if parameter in a:
            params[as_of][a['zone']] = a[parameter]
        #else:
        #    params[as_of][a['zone']] = None

    updates = params.keys()
    closest_date = None
    min_diff = timedelta(days = 99999)
    for u in updates:
        diff = abs( u - start_date ) + abs( u - end_date )
        if diff < min_diff:
            min_diff = diff
            closest_date = u

    if closest_date in params and zone in params[closest_date]:
        return params[closest_date][zone]
    return None

def get_lease_count(zone,start_date,end_date):
    return get_x_count('leases',zone,start_date,end_date)

def get_hourly_rate(zone,start_date,end_date,start_hour,end_hour):
    # Some corrections will be needed, e.g., for zones that come up as "MULTIRATE".

    # start_hour and end_hour are being passed since there are a few oddball
    # cases where the rate has been dependent on the time of day.
    space_count, hourly_rate = get_space_count_and_rate(zone,start_date,end_date)
    return hourly_rate

def calculate_utilization(zone,start_date,end_date,start_hour,end_hour):
    """Utilization = (Revenue from parking purchases) / { ([# of spots] - 0.85*[# of leases]) * (rate per hour) * (the number of days in the time span where parking is not free) * (duration of slot in hours) }"""

    revenue, transaction_count = get_revenue_and_count(ref_time,zone,start_date,end_date,start_hour,end_hour)
    lease_count = get_lease_count(zone,start_date,end_date)
    if lease_count is None:
        lease_count = 0
    effective_space_count = get_space_count_and_rate(zone,start_date,end_date)[0] - 0.85*lease_count

    hourly_rate = get_hourly_rate(zone,start_date,end_date,start_hour,end_hour)
    non_free_days = parking_days_in_range(start_date,end_date)
    slot_duration = end_hour - start_hour
    assert end_hour > start_hour
    utilization = revenue/effective_space_count/hourly_rate/non_free_days/slot_duration
    return utilization, revenue, transaction_count

def load_and_cache_utilization(zone,start_date,end_date,start_hour,end_hour):
    # Should this instead combine all the hour ranges?
    ut, rev, transaction_count = calculate_utilization(zone,start_date,end_date,start_hour,end_hour)
    return {'total_payments': rev, 'transaction_count': transaction_count, 'utilization': ut}

def get_features(request):
    """
    Look up the space count, lease count, and rate for this combination
    of zone and quarter (eventually extend this to date range) and return them.
    """
    zone = request.GET.get('zone', None)
    search_by = request.GET.get('search_by', 'month')
    if search_by == 'quarter':
        quarter = request.GET.get('quarter', None)
        # Convert quarter to start_date and end_date
        print("Retrieved zone = '{}' and quarter = '{}'".format(zone,quarter))

        start_dt, end_dt, start_date, end_date = quarter_to_datetimes(quarter)

    elif search_by == 'month':
        month = int(request.GET.get('month', None))
        year = int(request.GET.get('year', None))
        # Convert month/year to start_date and end_date
        print("Retrieved zone = '{}' and month/year = '{}/{}'".format(zone,month,year))

        start_dt, end_dt, start_date, end_date = datetimes_for_month(year,month)

    space_count, hourly_rate = get_space_count_and_rate(zone,start_date,end_date)
    leases = get_lease_count(zone,start_date,end_date)

    data = {
        'spaces': space_count,
        'leases': leases,
        'rate': hourly_rate
    }

    pprint(data)
    return JsonResponse(data)

def get_dates(request):
    """
    Look up the start_date and end_date for this combination
    of zone and quarter/month (eventually extend this to date range) and return them.
    """
    # Note that end_date is the last date (NON-INCLUSIVE) of a date range
    # That is, dates = [start_date, end_date)
    # The end_date for October 2018 is 2018-11-01.

    zone = request.GET.get('zone', None)
    search_by = request.GET.get('search_by', 'month')
    if search_by == 'quarter':
        quarter = request.GET.get('quarter', None)
        # Convert quarter to start_date and end_date
        print("Retrieved zone = '{}' and quarter = '{}'".format(zone,quarter))

        start_dt, end_dt, start_date, end_date = quarter_to_datetimes(quarter)

        data = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'quarter': quarter
        }
    elif search_by == 'month':
        month = int(request.GET.get('month', None))
        year = int(request.GET.get('year', None))
        # Convert month/year to start_date and end_date
        print("Retrieved zone = '{}' and month/year = '{}/{}'".format(zone,month,year))

        start_dt, end_dt, start_date, end_date = datetimes_for_month(year,month)

        data = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'month': month,
            'year': year
        }

    pprint(data)
    return JsonResponse(data)

def get_results(request):
    """
    Look up the utilization, total payments, and transaction count for this combination
    of zone and quarter/month (eventually extend this to arbitrary date range) and return them.
    """
    zone = request.GET.get('zone', None)
    search_by = request.GET.get('search_by', 'month')
    if search_by == 'quarter':
        quarter = request.GET.get('quarter', None)

        # Convert quarter to start_date and end_date
        print("Retrieved zone = '{}' and quarter = '{}'".format(zone,quarter))

        start_dt, end_dt, start_date, end_date = quarter_to_datetimes(quarter)
    elif search_by == 'month':
        month = int(request.GET.get('month', None))
        year = int(request.GET.get('year', None))
        start_date, end_date = dates_for_month(year,month)

    r_list = []
    set_table(ref_time)
    for key in hour_ranges:
        start_hour = hour_ranges[key]['start_hour']
        end_hour = hour_ranges[key]['end_hour']
        r_dict = load_and_cache_utilization(zone,start_date,end_date,start_hour,end_hour)
        #results_dict['hour_range'] = key
        #r_list.append(results_dict)
        row = format_row(key, r_dict['total_payments'], r_dict['transaction_count'], r_dict['utilization'])
        r_list.append( row )
    clear_table(ref_time)

    #result = any(p['id'] == dataset_id for p in rlist)
    #match = None
    #for p in rlist:
    #    if p['id'] == dataset_id:
    #        match = p
    #        break

    #resource_choices = []
    #for pair in csv_resource_choices(p):
    #   resource_choices.append(pair[::-1])
    data = {
        'display_zone': zone,
        'output_table': format_as_table(r_list)
    }
    if search_by == 'quarter':
        data['display_quarter'] = quarter
    elif search_by == 'month':
        data['display_month'] = month
        data['display_year'] = year

    return JsonResponse(data)

def index(request):
    if not request.user.is_authenticated():
        return redirect('%s?next=%s' % ('/admin/login/', request.path))

    all_zones = get_zones()
    zone_choices = convert_to_choices(all_zones)
    initial_zone = all_zones[0]
    search_choices = convert_to_choices(['month','quarter'])

    d = datetime.now().date() - timedelta(days = 365)
    search_by = 'month'
    if search_by == 'quarter':
        initial_quarter_choices = get_quarter_choices() # These should eventually be dependent on the initially chosen zone.
        initial_quarter = initial_quarter_choices[0][0]
        start_dt, end_dt, start_date, end_date = quarter_to_datetimes(initial_quarter)

        class QuarterSpaceTimeForm(forms.Form):
            zone = forms.ChoiceField(choices=zone_choices)
            quarter = forms.ChoiceField(choices=initial_quarter_choices)
            search_by = forms.ChoiceField(choices=search_choices)
            #input_field = forms.ChoiceField(choices=first_field_choices, help_text="(what you have in your spreadsheet)")
            #input_column_index = forms.CharField(initial='B',
            #    label="Input column",
            #    help_text='(the column in your spreadsheet where the values you want to convert can be found [e.g., "B"])',
            #    widget=forms.TextInput(attrs={'size':2}))
            #output_field = forms.ChoiceField(choices=first_field_choices, help_text="(what you want to convert your spreadsheet column to)")
    elif search_by == 'month':
        now = datetime.now()
        first_year = 2016
        years = range(first_year,now.year+1)
        initial_year_choices = convert_to_choices(years)
        initial_month_choices = convert_to_choices(range(1,13))

        initial_month = d.month
        initial_year = d.year
        start_dt, end_dt, start_date, end_date = datetimes_for_month(initial_year,initial_month)

        print("Start of month for date = {} is {} and end of month is {}".format(d,start_date,end_date))

        class MonthSpaceTimeForm(forms.Form):
            zone = forms.ChoiceField(choices=zone_choices) #, initial = "401 - Downtown 1")
            year = forms.ChoiceField(choices=initial_year_choices)
            month = forms.ChoiceField(choices=initial_month_choices)
            search_by = forms.ChoiceField(choices=search_choices)
    else:
        raise ValueError("This view is not provisioned to handle a search_by value of {}.".format(search_by))


    spaces, rate = get_space_count_and_rate(initial_zone,start_date,end_date)
    leases = get_lease_count(initial_zone,start_date,end_date)

    zone_features = {'spaces': spaces,
            'rate': rate,
            'leases': leases}

    results = []
    set_table(ref_time)
    for key in hour_ranges:
        start_hour = hour_ranges[key]['start_hour']
        end_hour = hour_ranges[key]['end_hour']
        ut, revenue, transaction_count = calculate_utilization(initial_zone,start_date,end_date,start_hour,end_hour)
        #results.append( {'hour_range': key, 'total_payments': "{:>12,.2f}".format(revenue), 'transaction_count': transaction_count, 'utilization': "{:.3f}".format(ut)} )
        #results.append( {'hour_range': key, 'total_payments': revenue, 'transaction_count': transaction_count, 'utilization': ut} )
        row = format_row(key, revenue, transaction_count, ut)
        results.append( row )
    clear_table(ref_time)
    pprint(results)

    #template = loader.get_template('index.html')
    #context = {#'output': output,
    #            'zone_picker': SpaceTimeForm().as_p()}
    if search_by == 'quarter':
        st_form = QuarterSpaceTimeForm()
    elif search_by == 'month':
        st_form = MonthSpaceTimeForm()
    #st_form.fields['zone'].initial = ["401 - Downtown 1"]

    output_table = format_as_table(results)

    context = {'zone_picker': st_form.as_p(),
            'form': st_form,
            'start_date': format_date(start_date),
            'end_date': format_date(end_date),
            'start_dt': start_dt,
            'end_dt': end_dt,
            'display_zone': initial_zone,
            'zone_features': zone_features,
            'results': results,
            'output_table': output_table,
            'search_by': search_by}

    if search_by == 'quarter':
        context['display_quarter'] = initial_quarter
    elif search_by == 'month':
        context['display_month'] = initial_month
        context['display_year'] = initial_year

    return render(request, 'valet/index.html', context)

    #return HttpResponse(template.render(context, request))
    #return HttpResponse("This page shows parking reports by zone/lot. <br>Choose a zone: {}<br>".format( SpaceTimeForm().as_p() ))

