import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import sample_data  # noqa: E402


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = core.Store(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_parse_date(self):
        self.assertEqual(core.parse_date("2026.9.3"), "2026-09-03")
        self.assertEqual(core.parse_date("20260930"), "2026-09-30")
        self.assertEqual(core.parse_date(""), "")
        with self.assertRaises(ValueError):
            core.parse_date("2026-13-01")

    def test_report_no_auto(self):
        self.store.import_ncr(sample_data.ncr_rows())
        self.assertEqual(self.store.next_report_no("2026-09-30"), "I30F-HSE-NCR-202609-11")
        self.assertEqual(self.store.next_report_no("2026-10-01"), "I30F-HSE-NCR-202610-1")
        rid = self.store.save_ncr({"title": "안전난간 설치 요망", "issue_date": "2026-10-12"})
        r = self.store.get("ncr", rid)
        self.assertEqual(r["report_no"], "I30F-HSE-NCR-202610-1")
        self.assertEqual(r["receiver"], core.COMPANY)

    def test_status_and_rate(self):
        ref = "2026-10-12"
        rows = [
            {"due_date": "2026-10-01", "done_date": "2026-10-01"},  # 기한 내
            {"due_date": "2026-10-01", "done_date": "2026-10-03"},  # 지연 완료
            {"due_date": "2026-10-05", "done_date": ""},            # 기한초과
            {"due_date": "2026-10-20", "done_date": ""},            # 진행중(대상 아님)
        ]
        self.assertEqual([core.ncr_status(r, ref) for r in rows], ["완료", "완료", "기한초과", "진행중"])
        self.assertAlmostEqual(core.on_time_rate(rows, ref), 33.33)
        self.assertIsNone(core.on_time_rate(rows[3:], ref))

    def test_sample_import_and_rate(self):
        a, b, err = self.store.import_ncr(sample_data.ncr_rows())
        self.assertEqual((a, b, err), (19, 0, []))
        a, b, err = self.store.import_ncr(sample_data.ncr_rows())
        self.assertEqual((a, b), (0, 19))
        rows = self.store.list_ncr("2026-07-13", "2026-10-13")
        self.assertEqual(core.on_time_rate(rows), 100.0)  # HPMS 화면의 100.00% 와 일치
        self.assertEqual(len(self.store.list_ncr(receiver="한국전기")), 1)
        a, b, _ = self.store.import_tbm(sample_data.tbm_rows())
        self.assertEqual((a, b), (18, 0))
        self.assertEqual(self.store.import_tbm(sample_data.tbm_rows())[:2], (0, 18))
        self.assertEqual(self.store.ptw_numbers()[0], "I30F-2026-00067")

    def test_missing_tbm_days(self):
        self.store.import_tbm(sample_data.tbm_rows())
        # 10/4 = 일요일(제외), 10/9 한글날(금), 10/10(토) 기록 없음, 10/11 일요일
        self.assertEqual(self.store.missing_tbm_days("2026-10-01", "2026-10-12"), ["2026-10-09", "2026-10-10"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.store.save_ncr({"title": ""})
        with self.assertRaises(ValueError):
            self.store.save_ncr({"title": "x", "issue_date": "2026-10-10", "due_date": "2026-10-01"})
        with self.assertRaises(ValueError):
            self.store.save_tbm({"exec_date": "2026-10-10", "attendees": "열명"})

    def test_excel_roundtrip(self):
        self.store.import_ncr(sample_data.ncr_rows())
        self.store.import_tbm(sample_data.tbm_rows())
        p1 = os.path.join(self.tmp.name, "ncr.xlsx")
        p2 = os.path.join(self.tmp.name, "tbm.xlsx")
        core.export_xlsx(p1, "부적합보고서", core.NCR_FIELDS, self.store.list_ncr(), [("status", "상태")])
        core.export_xlsx(p2, "TBM보고서", core.TBM_FIELDS, self.store.list_tbm())
        other = core.Store(os.path.join(self.tmp.name, "o.db"))
        self.assertEqual(other.import_ncr(core.import_xlsx(p1, core.NCR_ALIASES)), (19, 0, []))
        self.assertEqual(other.import_tbm(core.import_xlsx(p2, core.TBM_ALIASES)), (18, 0, []))
        other.db.close()


if __name__ == "__main__":
    unittest.main()
