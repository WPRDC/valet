"""Many of the below functions were originally imported from park-shark/hm_util.py."""
from dateutil.easter import * # pip install python-dateutil
from datetime import datetime, date, timedelta
#from dateutil.relativedelta import relativedelta

from calendar import monthrange
from pprint import pprint
from .query_util import source_time_range

## A bunch of date calculation functions (not currently in use in the code) ##
def nth_m_day(year,month,n,m):
    # m is the day of the week (where 0 is Monday and 6 is Sunday)
    # This function calculates the date for the nth m-day of a
    # given month/year.
    first = date(year,month,1)
    day_of_the_week = first.weekday()
    delta = (m - day_of_the_week) % 7
    return date(year, month, 1 + (n-1)*7 + delta)

def last_m_day(year,month,m):
    last = date(year,month,monthrange(year,month)[1])
    while last.weekday() != m:
        last -= timedelta(days = 1)
    return last

def is_holiday(date_i):
    year = date_i.year
    holidays = [date(year,1,1), #NEW YEAR'S DAY
    ### HOWEVER, sometimes New Year's Day falls on a weekend and is then observed on Monday. If it falls on a Saturday (a normal non-free parking day), what happens?
    ### Actually 2017-1-1 was a Sunday, and other days around that appeared to have normal non-holiday activity.
    ### So if New Year's Day falls on a Sunday, it is observed (at least as a parking holiday) on Sunday.

    ### Current data shows no evidence of any of these dates shifting when they fall on Saturdays or Sundays.
    ### A few dates still need more verification.

        nth_m_day(year,1,3,0), #MARTIN LUTHER KING JR'S BIRTHDAY (third Monday of January)
        easter(year)-timedelta(days=2), #GOOD FRIDAY
        last_m_day(year,5,0), #MEMORIAL DAY (last Monday in May)
        date(year,7,4), #INDEPENDENCE DAY (4TH OF JULY)
        # [ ] This could be observed on a different day when
        # the 4th falls on a Sunday.

        nth_m_day(year,9,1,0), #LABOR DAY (first Monday in September)
        date(year,11,11), #VETERANS' DAY (seems to be observed on Saturdays when if falls on Saturdays)
        # [ ] This could be observed on a different day (check when this is observed if it falls on a Sunday).

        nth_m_day(year,11,4,3), #THANKSGIVING DAY
        nth_m_day(year,11,4,4), #DAY AFTER THANKSGIVING
        date(year,12,25), #CHRISTMAS DAY # There's no evidence that Christmas or the day after Christmas are
        date(year,12,26)] #DAY AFTER CHRISTMAS # observed on days other than the 25th and 26th.

    return date_i in holidays

def parking_days_in_month(year,month):
    count = 0
    month_length = monthrange(year,month)[1]
    for day in range(1,month_length+1):
        date_i = date(year,month,day)
        if date_i.weekday() < 6 and not is_holiday(date_i):
            count += 1
    return count

def parking_days_in_range(start_date,end_date,ref_time='purchase_time',constrain_to_days_with_data=False):
    """This function accepts date objects and finds the number of non-free parking days
    (i.e., metered parking days) between them (including the start date but not the end date)."""
    _, source_start, source_end = source_time_range(ref_time)
    assert start_date <= end_date
    if constrain_to_days_with_data:
        if end_date < source_start or start_date > source_end:
            return 0 # Window has no overlap with source data.
        start_date = max(start_date, source_start)
        end_date = min(end_date, source_end + timedelta(days=1)) # The end_date is non-inclusive (one day beyond the last date
        # in the range). The source_end is inclusive, so to convert source_end to end_date, we must add one day.
        # |----| |----data-----|  ==> 0
        #    |~~~~~~~|
        #        |~~~| (the intersection of the ranges)

    count = 0
    date_i = start_date
    while date_i < end_date:
        if date_i.weekday() < 6 and not is_holiday(date_i):
            count += 1
        date_i += timedelta(days=1)
    return count
## End of date-calculation functions ##

def format_date(d):
    return datetime.strftime(d,"%Y-%m-%d")

def format_utilization(u):
    return "-" if u is None else "{:.1f}%".format(100*u)

def format_row(hour_range,total_payments,transaction_count,utilization,utilization_w_leases='not passed'):
    revenue = "${:,.2f}".format(total_payments)
    row = {'hour_range': hour_range, 'total_payments': "{}".format(revenue), 'transaction_count': "{:,}".format(transaction_count), 'utilization': format_utilization(utilization)}
    if utilization_w_leases != 'not passed':
        row['utilization_w_leases'] = format_utilization(utilization_w_leases)
    return row

def style_by_offset(rate_offset):
    """This function takes a rate_offset and returns a style string."""
    if -0.01 < rate_offset < 0.01: # Essentially, if it is a default value
        return ''
    return ' style="background-color:#f2f2f2"'

def format_as_table(results,zone,show_utilization,late_night_zones,rate_offsets):
    """To simplify piping new results via AJAX, use Python to generate the
    table and then send that to the appropriate div."""
# The original Jinja template looked like this:
#<table>
#    <tr>
#        <th>Hour range</th>
#        <th>Total payments</th>
#        <th>Transactions</th>
#        <th>Utilization</th>
#    </tr>
#{% for result in results_table %}
#    <tr>
#        <td>{{ result.hour_range }}</td>
#        <td>{{ result.total_payments }}</td>
#        <td>{{ result.transaction_count }}</td>
#        <td>{{ result.utilization }}</td>
#    </tr>
#{% endfor %}
#</table>
#    t = """<table id="results_table" style="margin-bottom:0.2rem"><thead><tr><th>Hour range\t</th><th>Transient<br>revenue\t</th><th>Transactions\t</th><th>Utilization<span class="tooltip">*<span class="tooltiptext">Utilization calculation assumes<br>85% occupancy of any leased spots.</span></span>\t</th></tr></thead>"""

    utilization_header = "<th>Utilization\t</th>" if show_utilization else ""
    table_alignment = "" if show_utilization else 'align=right'
    t = """<table id="results_table" style="margin-bottom:0.2rem" """
    t += table_alignment
    t += """><thead><tr><th>Hour range\t</th><th>Transient<br>revenue\t</th><th>Transactions\t</th>"""
    t += utilization_header + "</tr></thead>"
    t += "<tbody>"

    for r,rate_offset in zip(results,rate_offsets):
        if r['hour_range'] == '8am-10am' and r['utilization_w_leases'] != '-':
            pre_utilization = "<b>"
            post_utilization = "*</b>"
        elif r['hour_range'] == '6pm-midnight' and r['utilization_w_leases'] != '-':
            pre_utilization = ""
            post_utilization = "&dagger;"
        else:
            pre_utilization = ""
            post_utilization = ""
        if r['hour_range'] != '6pm-midnight' or zone in late_night_zones:
            style = style_by_offset(rate_offset)
            glyph = "" if style == "" else "&Dagger;"
            utilization_string = "<td>{}{}{}{}\t</td>".format(pre_utilization,r['utilization_w_leases'],post_utilization,glyph) if show_utilization else ""
            t += "<tr{}><td>{}\t</td><td>{}\t</td><td>{}\t</td>{}</tr>".format(style,r['hour_range'], r['total_payments'], r['transaction_count'], utilization_string)
    t += "</tbody></table>"

    return t

def format_rate_description(rate_description):
    # This function borrows code from convert_description_to_rate, so
    # there's some opportunity for refactoring.
    lowercase_rate_description = rate_description.lower()
    if '/' not in lowercase_rate_description: # Deal with cases like *SPECIAL*
        return rate_description
    numerator, denominator = lowercase_rate_description.split('/')
    assert denominator in ['hr','hour']
    assert numerator[0] == '$'
    try: # Try converting it to a float.
        rate = float(numerator[1:])
        return rate_description
    except ValueError:
        style = style_by_offset(42)
        return "<span {}>{}{}</span>".format(style,rate_description,"&Dagger;")
