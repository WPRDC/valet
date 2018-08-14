from .util import parking_days_in_range
from datetime import date, timedelta

# First install pytest
#    > pip install pytest
# Then run
#    > py.test 
# to run the tests in any file with a name like test_*.py or *_test.py.

def test_2018():
    assert parking_days_in_range(date(2018,1,1),date(2018,1,7)) == 5
    assert parking_days_in_range(date(2018,10,1),date(2018,10,31)) == 31 - 4 
    assert parking_days_in_range(date(2018,11,11),date(2018,11,11)) == 0
    assert parking_days_in_range(date(2018,11,1),date(2018,11,4)) == 3
    assert parking_days_in_range(date(2018,11,1),date(2018,11,11)) == 9
    assert parking_days_in_range(date(2018,11,1),date(2018,11,30)) == 30 - 6
    assert parking_days_in_range(date(2018,12,1),date(2018,12,31)) == 31 - 5 - 2
    assert parking_days_in_range(date(2018,10,1),date(2018,12,31)) == 31 - 4 + 30 - 6 + 31 - 7
