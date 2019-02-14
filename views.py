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
from .query_util import get_revenue_and_count_vectorized
from .proto_get_revenue import set_table, clear_table

ref_time = 'purchase_time'

hour_ranges = OrderedDict([('midnight-8am', {'start_hour': 0, 'end_hour': 8}),
               ('8am-10am', {'start_hour': 8, 'end_hour': 10}),
               ('10am-2pm', {'start_hour': 10, 'end_hour': 14}),
               ('2pm-6pm', {'start_hour': 14, 'end_hour': 18}),
               ('6pm-midnight', {'start_hour': 18, 'end_hour': 24}),
               ('total', {'start_hour': 0, 'end_hour': 24}),
               ])
# [ ] Add final hour range/ranges for the Southside (maybe picking only particular days, so a different query might be needed).

def get_zones():
    regular_zones = ["301 - Sheridan Harvard Lot",
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
    minizones = get_minizones()
    zones = regular_zones + minizones
    return zones

def get_minizones():
    # Hard-coding these minizones is only a temporary solution.
    minizones = [
        "Hill District",
        "HILL-DIST-2",
        "S. Craig",
        "SHADYSIDE1",
        "SHADYSIDE2",
        "Southside Lots",
        "SQ.HILL1",
        "SQ.HILL2",
        "UPTOWN1",
        "UPTOWN2",
        "W CIRC DR",
        ]
    return minizones

def is_minizone(zone):
    return zone in get_minizones()

def valid_month_year(month,year):
    try:
        month = int(month)
        year = int(year)
        return True, month, year
    except ValueError:
        #if month in ['', ' ', None] or year in ['', ' ', None]:
        print("{}/{} is not a complete date.".format(month,year))
        return False, None, None

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

def alias(x):
    aliases = {'HILL-DIST-2': 'HILL-DIST-2 [Robinson St Ext]',
            'SHADYSIDE1': 'SHADYSIDE1 [Walnut St]'}
    if x in aliases:
        return aliases[x]
    return x

def convert_to_choices(xs):
    choices = []
    for x in xs:
        #zone_code = re.sub(" - .*","",str(x))
        zone_code = alias(x)
        choices.append( (x, zone_code) )
    return choices

def get_package_metadata(site,package_id,API_key=None):
    ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
    metadata = ckan.action.package_show(id=package_id)
    return metadata

def source_time_range(ref_time):
    from .credentials import site, ckan_api_key as API_key, transactions_package_id as package_id
    metadata = get_package_metadata(site,package_id,API_key)
    pprint(metadata)
    if 'temporal_coverage' in metadata:
        begin_date, end_date = metadata['temporal_coverage'].split('/')
        return "from {} to {}".format(begin_date, end_date)
    return None

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
    if len(table_data) == 0 or (last_cached is not None and (today - last_cached_date > timedelta(days=1))):
        # Build/refresh cache
        attribute_dicts = get_all_records(site, resource_id, API_key)
        print("Pulling and caching data. {} records found.".format(len(attribute_dicts)))
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
    else: # Use data pulled from local database.
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

    # Crude first attempt to handle zones which do not appear
    # in the existing data (like 427 - Knoxville):
    space_count = None
    if zone in spaces[closest_date]:
        space_count = spaces[closest_date][zone]
    rate = None
    if zone in rates[closest_date]:
        rate = rates[closest_date][zone]
    return space_count, rate



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

def calculate_utilization_vectorized(zone,start_date,end_date,start_hours,end_hours,is_a_minizone):
    """Utilization = (Revenue from parking purchases) / { ([# of spots] - 0.85*[# of leases]) * (rate per hour) * (the number of days in the time span where parking is not free) * (duration of slot in hours) }"""

    revenues, transaction_counts = get_revenue_and_count_vectorized(ref_time,zone,start_date,end_date,start_hours,end_hours,is_a_minizone)
    lease_count = get_lease_count(zone,start_date,end_date)
    if lease_count is None:
        lease_count = 0
    space_count = get_space_count_and_rate(zone,start_date,end_date)[0]
    if space_count is not None:
        effective_space_count = space_count - 0.85*lease_count
    non_free_days = parking_days_in_range(start_date,end_date)

    utilizations, utilizations_w_leases = [], []
    for start_hour,end_hour,revenue in zip(start_hours,end_hours,revenues):
        hourly_rate = get_hourly_rate(zone,start_date,end_date,start_hour,end_hour)
        slot_duration = end_hour - start_hour
        assert end_hour > start_hour

        #print("hourly_rate = {}, space_count = {}".format(hourly_rate,space_count))
        if hourly_rate is None or space_count is None or non_free_days == 0:
            utilizations.append(None)
            utilizations_w_leases.append(None)
        else:
            ut = revenue/effective_space_count/hourly_rate/non_free_days/slot_duration
            utilizations.append(ut)
            if start_hour < 8 or start_hour >= 18: # This excludes the "total" slot (from hour 0 to hour 24).
                total_ut = None
            else:
                total_ut = (ut*effective_space_count + 0.85*lease_count)/space_count
            utilizations_w_leases.append(total_ut)

    return utilizations, utilizations_w_leases, revenues, transaction_counts

def vectorized_query(zone,search_by,start_date,end_date,start_hours,end_hours,is_a_minizone):
    """A.K.A. load_and_cache_utilization_vectorized; A.K.A. query_all_ranges."""
    uts, uts_w_leases, revs, transaction_counts = calculate_utilization_vectorized(zone,start_date,end_date,start_hours,end_hours,is_a_minizone)
    rows = []
    for ut, ut_w_leases, rev, transaction_count in zip(uts,uts_w_leases,revs,transaction_counts):
        rows.append({'total_payments': rev, 'transaction_count': transaction_count, 'utilization': ut, 'utilization_w_leases': ut_w_leases})
    return rows

def obtain_table_vectorized(ref_time,search_by,zone,start_date,end_date,hour_ranges):
    r_list = []
    chart_ranges = ['8am-10am', '10am-2pm', '2pm-6pm', '6pm-midnight']
    transactions_chart_data = []
    payments_chart_data = []

    start_hours = []
    end_hours = []
    for key in hour_ranges:
        start_hour = hour_ranges[key]['start_hour']
        end_hour = hour_ranges[key]['end_hour']
        start_hours.append(start_hour)
        end_hours.append(end_hour)


    is_a_minizone = is_minizone(zone)
    set_table(ref_time,is_a_minizone)
    rows = vectorized_query(zone,search_by,start_date,end_date,start_hours,end_hours,is_a_minizone)
    clear_table(ref_time,is_a_minizone)
    for key,r_dict in zip(hour_ranges,rows):

        #if zone[0] == '3': # This signifies a lot rather than on-street parking:
        #    # And lots may have leases.
        #    row = format_row(key, r_dict['total_payments'], r_dict['transaction_count'], r_dict['utilization'], r_dict['utilization_w_leases'])
        #else:
        #    row = format_row(key, r_dict['total_payments'], r_dict['transaction_count'], r_dict['utilization'])
        row = format_row(key, r_dict['total_payments'], r_dict['transaction_count'], None, r_dict['utilization_w_leases'])
        r_list.append( row )
        if key in chart_ranges:
            transactions_chart_data.append(r_dict['transaction_count'])
            payments_chart_data.append(r_dict['total_payments'])

    return r_list, transactions_chart_data, payments_chart_data, chart_ranges

def get_features(request):
    """
    Look up the space count, lease count, and rate for this combination
    of zone and quarter (eventually extend this to date range) and return them.
    """
    zone = request.GET.get('zone', None)
    search_by = request.GET.get('search_by', 'month')
    if search_by == 'date':
        start_dt, end_dt = get_dts_from_date_range(request)
        start_date = start_dt.date()
        end_date = end_dt.date()

    elif search_by == 'quarter':
        quarter = request.GET.get('quarter', None)
        # Convert quarter to start_date and end_date
        print("Retrieved zone = '{}' and quarter = '{}'".format(zone,quarter))

        start_dt, end_dt, start_date, end_date = quarter_to_datetimes(quarter)

    elif search_by == 'month':
        month = request.GET.get('month', None)
        year = request.GET.get('year', None)

        valid, month, year = valid_month_year(month,year)
        if not valid:
            data = {}
            return JsonResponse(data)
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

def get_dts_from_date_range(request):
    """Take a request, extract the from_date and to_date parameters and convert them to
    start_dt and end_dt datetimes, handling cases where both values are unchosen by
    picking the most recent full day (yesterday) and handling cases where only one
    value has been chosen by selecting a one-day interval."""

    from_date = request.GET.get('from_date', None)
    to_date = request.GET.get('to_date', None)
    # Convert quarter to start_date and end_date
    print("Retrieved from_date = '{}' and to_date = '{}'".format(from_date,to_date))

    if from_date not in [None, '']:
        start_dt = datetime.strptime(from_date, "%Y-%m-%d")
        if to_date in [None, '']:
            end_dt = start_dt + timedelta(days = 1)
        else:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days = 1)
    else:
        if to_date not in [None, '']:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days = 1)
            start_dt = end_dt - timedelta(days = 1)
        else: # They're both None.
            end_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = end_dt - timedelta(days = 1)

    return start_dt, end_dt

def get_dates(request):
    """
    Look up the start_date and end_date for this date range/quarter/month
    and return them.
    """
    # Note that end_date is the last date (NON-INCLUSIVE) of a date range
    # That is, dates = [start_date, end_date)
    # The end_date for October 2018 is 2018-11-01.

    search_by = request.GET.get('search_by', 'month')
    if search_by == 'date':
        start_dt, end_dt = get_dts_from_date_range(request)
        data = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'display_time_range': "{} through {}".format(start_dt.date(), end_dt.date() - timedelta(days=1))
        }
    elif search_by == 'quarter':
        quarter = request.GET.get('quarter', None)
        # Convert quarter to start_date and end_date
        start_dt, end_dt, start_date, end_date = quarter_to_datetimes(quarter)
        data = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'quarter': quarter,
            'display_time_range': quarter
        }
    elif search_by == 'month':
        month = request.GET.get('month', None)
        year = request.GET.get('year', None)

        valid, month, year = valid_month_year(month,year)
        if not valid:
            data = {}
            return JsonResponse(data)
        # Convert month/year to start_date and end_date
        start_dt, end_dt, start_date, end_date = datetimes_for_month(year,month)
        data = {
            'start_dt': start_dt,
            'end_dt': end_dt,
            'month': month,
            'year': year,
            'display_time_range': "{}/{}".format(month,year)
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
    elif search_by == 'date':
        start_dt, end_dt = get_dts_from_date_range(request)
        start_date = start_dt.date()
        end_date = end_dt.date()
    elif search_by == 'month':
        month = request.GET.get('month', None)
        year = request.GET.get('year', None)

        valid, month, year = valid_month_year(month,year)
        if not valid:
            data = {
                'display_zone': zone,
                'valid_date_range': False
            }
            return JsonResponse(data)
        start_date, end_date = dates_for_month(year,month)
        # end_date is the first day that is not included in the date range.
        # [start_date, end_date)

    r_list, transactions_chart_data, payments_chart_data, chart_ranges = obtain_table_vectorized(ref_time,search_by,zone,start_date,end_date,hour_ranges)
    data = {
        'display_zone': zone,
        'output_table': format_as_table(r_list),
        'chart_ranges': chart_ranges,
        'transactions_chart_data': transactions_chart_data,
        'payments_chart_data': payments_chart_data,
        'valid_date_range': True
    }
    return JsonResponse(data)


def index(request):
    if not request.user.is_authenticated():
        return redirect('%s?next=%s' % ('/admin/login/', request.path))

    all_zones = get_zones()
    zone_choices = convert_to_choices(all_zones)
    initial_zone = all_zones[0]
    search_choices = convert_to_choices(['month','quarter'])

    initial_d = datetime.now().date() - timedelta(days = 365)
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
        years = list(range(first_year,now.year+1))
        years.append(" ")
        initial_year_choices = convert_to_choices(years)
        months = list(range(1,13))
        months.append(" ")
        initial_month_choices = convert_to_choices(months)

        initial_month = initial_d.month
        initial_year = initial_d.year
        start_dt, end_dt, start_date, end_date = datetimes_for_month(initial_year,initial_month)

        print("Start of month for date = {} is {} and end of month is {}".format(initial_d,start_date,end_date))

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

    if search_by == 'quarter':
        st_form = QuarterSpaceTimeForm()
    elif search_by == 'month':
        st_form = MonthSpaceTimeForm(initial = {'year': initial_year, 'month': initial_month, 'zone': initial_zone})
    #st_form.fields['zone'].initial = ["401 - Downtown 1"]

    results, transactions_chart_data, payments_chart_data, chart_ranges = obtain_table_vectorized(ref_time,search_by,initial_zone,start_date,end_date,hour_ranges)
    output_table = format_as_table(results)

    transactions_time_range = source_time_range(ref_time)
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
            'chart_ranges': chart_ranges,
            'transactions_chart_data': transactions_chart_data,
            'payments_chart_data': payments_chart_data,
            'search_by': search_by,
            'transactions_time_range': transactions_time_range }

    if search_by == 'date':
        context['display_time_range'] = "{} through {}".format(start_date, end_date - timedelta(days=1))
    elif search_by == 'quarter':
        context['display_time_range'] = initial_quarter
    elif search_by == 'month':
        context['display_time_range'] = "{}/{}".format(initial_month,initial_year)

    return render(request, 'valet/index.html', context)

    #return HttpResponse(template.render(context, request))
    #return HttpResponse("This page shows parking reports by zone/lot. <br>Choose a zone: {}<br>".format( SpaceTimeForm().as_p() ))

