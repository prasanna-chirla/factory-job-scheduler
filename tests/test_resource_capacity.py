import unittest
from datetime import datetime
from src.resources import fits_capacity

class SharedResourceTests(unittest.TestCase):
    def test_single_shared_tool_cannot_be_double_booked(self):
        key=("TOOL-JIG","2026-01-05",1)
        start=datetime.fromisoformat("2026-01-05T09:00:00"); end=datetime.fromisoformat("2026-01-05T10:00:00")
        bookings={key:[(start,end,1)]}
        self.assertFalse(fits_capacity(bookings,key,datetime.fromisoformat("2026-01-05T09:30:00"),datetime.fromisoformat("2026-01-05T10:30:00"),1,1))

    def test_labor_pool_capacity_allows_only_configured_concurrency(self):
        key=("operator","2026-01-05",1); start=datetime.fromisoformat("2026-01-05T09:00:00"); end=datetime.fromisoformat("2026-01-05T10:00:00")
        bookings={key:[(start,end,2)]}
        self.assertTrue(fits_capacity(bookings,key,start,end,1,3))
        self.assertFalse(fits_capacity(bookings,key,start,end,2,3))

if __name__=="__main__": unittest.main()
