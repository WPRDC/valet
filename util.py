"""Many of the below functions were originally imported from park-shark/hm_util.py."""
from dateutil.easter import * # pip install python-dateutil
from datetime import datetime, date, timedelta
#from dateutil.relativedelta import relativedelta

from calendar import monthrange
from pprint import pprint

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

def parking_days_in_range(start_date,end_date):
    """This function accepts date objects and finds the number of non-free parking days
    between them (including the start date but not the end date)."""
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

def format_as_table(results,zone):
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
    t = """<table id="results_table" style="margin-bottom:0.2rem"><thead><tr><th>Hour range\t</th><th>Transient<br>revenue\t</th><th>Transactions\t</th><th>Utilization\t</th></tr></thead>"""
    t += "<tbody>"

    for r in results:
        if r['hour_range'] == '8am-10am' and r['utilization_w_leases'] != '-':
            pre_utilization = "<b>"
            post_utilization = "*</b>"
        else:
            pre_utilization = ""
            post_utilization = ""
        if r['hour_range'] != '6pm-midnight' or zone in ["328 - Ivy Bellefonte Lot", "Southside Lots", "341 - 18th & Sidney Lot", "342 - East Carson Lot", "343 - 19th & Carson Lot", "344 - 18th & Carson Lot", "345 - 20th & Sidney Lot"]:
            utilization_string = "<td>{}{}{}\t</td>".format(pre_utilization,r['utilization_w_leases'],post_utilization)
            t += "<tr><td>{}\t</td><td>{}\t</td><td>{}\t</td>{}</tr>".format(r['hour_range'], r['total_payments'], r['transaction_count'],utilization_string)
    t += "</tbody></table>"

    return t
