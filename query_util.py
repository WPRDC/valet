import ckanapi
from datetime import datetime
from pprint import pprint

from .credentials import site, ckan_api_key as API_key

def query_resource(site,query,API_key=None):
    # Use the datastore_search_sql API endpoint to query a CKAN resource.

    # Note that this doesn't work for private datasets.
    # The relevant CKAN GitHub issue has been closed.
    # https://github.com/ckan/ckan/issues/1954

    # In fact, if the dataset is private (the table is inaccessible),
    # the datastore_search_sql function throws a gibberishy, non-helpful error:
    # TypeError: __str__ returned non-string (type dict)

    ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
    response = ckan.action.datastore_search_sql(sql=query)
    # A typical response is a dictionary like this
    #{u'fields': [{u'id': u'_id', u'type': u'int4'},
    #             {u'id': u'_full_text', u'type': u'tsvector'},
    #             {u'id': u'pin', u'type': u'text'},
    #             {u'id': u'number', u'type': u'int4'},
    #             {u'id': u'total_amount', u'type': u'float8'}],
    # u'records': [{u'_full_text': u"'0001b00010000000':1 '11':2 '13585.47':3",
    #               u'_id': 1,
    #               u'number': 11,
    #               u'pin': u'0001B00010000000',
    #               u'total_amount': 13585.47},
    #              {u'_full_text': u"'0001c00058000000':3 '2':2 '7827.64':1",
    #               u'_id': 2,
    #               u'number': 2,
    #               u'pin': u'0001C00058000000',
    #               u'total_amount': 7827.64},
    #              {u'_full_text': u"'0001c01661006700':3 '1':1 '3233.59':2",
    #               u'_id': 3,
    #               u'number': 1,
    #               u'pin': u'0001C01661006700',
    #               u'total_amount': 3233.59}]
    # u'sql': u'SELECT * FROM "d1e80180-5b2e-4dab-8ec3-be621628649e" LIMIT 3'}
    data = response['records']
    return data

def get_package_parameter(site,package_id,parameter=None,API_key=None):
    """Gets a CKAN package parameter. If no parameter is specified, all metadata
    for that package is returned."""
    # Some package parameters you can fetch from the WPRDC with
    # this function are:
    # 'geographic_unit', 'owner_org', 'maintainer', 'data_steward_email',
    # 'relationships_as_object', 'access_level_comment',
    # 'frequency_publishing', 'maintainer_email', 'num_tags', 'id',
    # 'metadata_created', 'group', 'metadata_modified', 'author',
    # 'author_email', 'state', 'version', 'department', 'license_id',
    # 'type', 'resources', 'num_resources', 'data_steward_name', 'tags',
    # 'title', 'frequency_data_change', 'private', 'groups',
    # 'creator_user_id', 'relationships_as_subject', 'data_notes',
    # 'name', 'isopen', 'url', 'notes', 'license_title',
    # 'temporal_coverage', 'related_documents', 'license_url',
    # 'organization', 'revision_id'
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        metadata = ckan.action.package_show(id=package_id)
        if parameter is None:
            return metadata
        else:
            return metadata[parameter]
    except:
        raise RuntimeError("Unable to obtain package parameter '{}' for package with ID {}".format(parameter,package_id))

def find_resource_id(site,package_id,resource_name,API_key=None):
#def get_resource_id_by_resource_name():
    # Get the resource ID given the package ID and resource name.
    resources = get_package_parameter(site,package_id,'resources',API_key)
    for r in resources:
        if r['name'] == resource_name:
            return r['id']
    return None


def get_resource_id(ref_time):
    by_name = True
    if ref_time == 'hybrid':
        from .credentials import transactions_resource_id as resource_id
    elif ref_time == 'purchase_time':
        if by_name:
            from .credentials import site, ckan_api_key as API_key, transactions_package_id as package_id, resource_name
            resource_id = find_resource_id(site,package_id,resource_name,API_key)
            if resource_id is None:
                raise ValueError("No resource found for package ID = {}, resource name = {}.".format(package_id,resource_name))
        else:
            #from credentials import split_pdl_transactions_resource_id as resource_id
            #from credentials import office_debug_resource_id as resource_id
            #from credentials import split_resource_id as resource_id
            from credentials import transactions_production_resource_id as resource_id
    else:
        raise ValueError("ref_time must specify the reference time to determine the correct resource ID.")
    return resource_id

def get_revenue_and_count(ref_time,zone,start_date,end_date,start_hour,end_hour,start_dt=None,end_dt=None):
    # Two models for getting data:
    # 1) Do a SQL query for all records in the start_date to end_date
    # range, then pare down to the hour range, then sum the results
    # (getting transaction count and total payments). 
    # 2) Do a selective SQL query that plucks out data based both on hour range
    # and date range, and then sum the results.

    # Note that end_date is the last date (NON-INCLUSIVE) of a date range
    # That is, dates = [start_date, end_date)
    # The end_date for October 2018 is 2018-11-01.

    # Caching strategies:
    #   Aggregate by zone and quarter and time range:
    #     A key could be of the form "401 - Downtown | 2018 Q1 | 8am-10am"
    #     With ~60 zones, there would then be 
    #       about 60*5*4*3 = 3600 of these quarterly sums, where transaction
    #                   count and total revenue could each be cached separately.
    #   There would be a few more ultimately to account for the extra time slot
    #   for the Southside, once parking became non-free late there on weekends.

    #   Also caching for extra zones would probably be necessary. 
    from .credentials import site, ckan_api_key as API_key
    resource_id = get_resource_id(ref_time)
    #make_datastore_public(site,resource_id,API_key)

    # query = 'SELECT * FROM "{}" WHERE zone = \'{}\' AND start >= \'2018-01-01\' AND start < \'2018-04-01\' ORDER BY start DESC LIMIT 3'.format(resource_id,zone)# a working query, 
    # which exactly bins the quarter

    start_string = start_date.strftime("%Y-%m-%d") # This should be the first date in the range.
    end_string = end_date.strftime("%Y-%m-%d")     # This should be the last date in the range.
    #query = 'SELECT SUM(payments) as total_payments, COUNT(_id) as transactions FROM "{}" WHERE zone = \'{}\' AND start >= \'{}\' AND start <= \'{}\''.format(resource_id,zone,start_string,end_string)
    new_approach = True
    split_by_mode = True # The dataset is split into mobile transactions and meter transactions.
    assert split_by_mode == True
    if zone is None: # This part deviates from the original proto_get_revenue.py, though it's an improvement.
        if new_approach and end_dt is not None:
            start_dt_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_dt_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            query = 'SELECT SUM(meter_payments) + SUM(mobile_payments) as total_payments, SUM(meter_transactions) + SUM(mobile_transactions) as transaction_count FROM "{}" WHERE start >= \'{}\' AND start < \'{}\''.format(resource_id,start_dt_str,end_dt_str)
        else:
            query = 'SELECT SUM(meter_payments) + SUM(mobile_payments) as total_payments, SUM(meter_transactions) + SUM(mobile_transactions) as transaction_count FROM "{}" WHERE start >= \'{}\' AND start < \'{}\' AND extract(hour from start) >= {} and extract(hour from start) < {}'.format(resource_id,start_string,end_string,start_hour,end_hour)
            # This will definitely fail for extract(hour from start) >= 1 and extract(hour from start) <= 1
            #     though it might work for the designed cases (valet),
            #          but it seems like it doesn't and is somehow giving twice the expected results.
    else:
        query = 'SELECT SUM(meter_payments) + SUM(mobile_payments) as total_payments, SUM(meter_transactions) + SUM(mobile_transactions) as transaction_count FROM "{}" WHERE zone = \'{}\' AND start >= \'{}\' AND start < \'{}\' AND extract(hour from start) >= {} and extract(hour from start) < {}'.format(resource_id,zone,start_string,end_string,start_hour,end_hour)

    # [ ] Verify that hour extraction extracts to a 24-hour clock.
    # 'SELECT *, extract(hour from start) as hour FROM "<resource ID>" WHERE zone = \'S. Craig\' AND start >= \'2018-01-01\' AND start <= \'2018-03-31\' AND extract(hour from start) > 8 LIMIT 5'
    # gives results like this:
    # {'_full_text': "[...]",
    #  '_id': 594455,
    #  'end': '2018-01-02T11:20:00',
    #  'hour': 11.0, <<<<<<<<<<<
    #  'parent_zone': '409 - Oakland 3',
    #  'payments': 2.25,
    #  'start': '2018-01-02T11:10:00',
    #  'transactions': 2,
    #  'utc_start': '2018-01-02T16:10:00',
    #  'zone': 'S. Craig'}

#  '_id': 2950,
#  'end': '2012-09-06T14:10:00',
#  'parent_zone': '409 - Oakland 3',
#  'payments': 2.5,
#  'start': '2012-09-06T14:00:00',
#  'transactions': 2,
#  'utc_start': '2012-09-06T18:00:00',
#  'zone': 'S. Craig'

    print("query = {}".format(query))
    data = query_resource(site,query,API_key)

    if end_date > datetime.now().date():
        print("The end_date {} is in the future.".format(end_date))
        print("... though maybe flagging things as too far in the future or past or in an incomplete quarter or month should be handled in a separate function.") 

    if data[0]['total_payments'] is not None:
        return data[0]['total_payments'], int(data[0]['transaction_count'])
    else:
        return 0.0, 0