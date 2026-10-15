"""No CT.gov proxy feature is a legal ACT or overdue-results determination."""
import gzip
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.act_proxy_audit import exact_date, one_calendar_year_after, review_record


def trial(nct_id="NCT00000001", *,
          pcd="2024-03-01", pcd_type="ACTUAL",
          results=False, drug=True, device=None,
          locations=None, study_type="INTERVENTIONAL", phases=None,
          posted=None):
    status = {"primaryCompletionDateStruct": {"date": pcd, "type": pcd_type}}
    if posted is not None:
        status["resultsFirstPostDateStruct"] = {"date": posted}
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id},
            "statusModule": status,
            "designModule": {"studyType": study_type, "phases": phases if phases is not None else ["PHASE3"]},
            "oversightModule": {"isFdaRegulatedDrug": drug, "isFdaRegulatedDevice": device},
            "contactsLocationsModule": {"locations": locations if locations is not None else [
                {"country": "United States"}]},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Example"}]},
        },
        "hasResults": results,
    }


class ProxyAuditTests(unittest.TestCase):
    def test_nonposted_after_anniversary_is_review_not_noncompliance(self):
        result = review_record(trial(), as_of=date(2026, 10, 15))
        self.assertEqual(result["registry_posting_clock"], "ONE_YEAR_ELAPSED_NO_POSTED_RESULTS")
        self.assertEqual(result["review_priority"], "REVIEW_CANDIDATE")
        self.assertEqual(result["act_eligibility"], "UNDETERMINED")
        self.assertEqual(result["results_legal_overdue_status"], "UNDETERMINED")

    def test_exact_anniversary_not_365_days_for_leap_year(self):
        study = trial(pcd="2023-03-01")
        before = review_record(study, as_of=date(2024, 2, 29))
        after = review_record(study, as_of=date(2024, 3, 1))
        self.assertIs(before["one_year_elapsed_without_posted_results"], False)
        self.assertIs(after["one_year_elapsed_without_posted_results"], True)
        self.assertEqual(one_calendar_year_after(date(2024, 2, 29)), date(2025, 3, 1))

    def test_no_actual_day_precise_primary_completion_returns_unknown(self):
        for pcd, kind in [("2020-01", "ACTUAL"), ("2020", "ACTUAL"),
                          ("2024-01-01", "ESTIMATED"), ("invalid", "ACTUAL")]:
            with self.subTest(pcd=pcd, kind=kind):
                record = review_record(trial(pcd=pcd, pcd_type=kind), as_of=date(2026, 10, 15))
                self.assertIsNone(record["one_year_elapsed_without_posted_results"])
                self.assertEqual(record["registry_posting_clock"], "UNASSESSABLE_ACTUAL_PCD_REQUIRED")

    def test_no_posted_results_missing_or_future_status_cannot_be_asserted(self):
        study = trial()
        study.pop("hasResults")
        uncertain = review_record(study, as_of=date(2026, 10, 15))
        self.assertEqual(uncertain["registry_posting_clock"], "UNASSESSABLE_RESULTS_STATUS_UNKNOWN")
        future = review_record(trial(results=True, posted="2027-01-01"), as_of=date(2026, 10, 15))
        self.assertIsNone(future["one_year_elapsed_without_posted_results"])
        self.assertIn("reported_results_first_post_date_after_as_of", future["data_caveats"])

    def test_us_location_alone_never_establishes_fda_act(self):
        for intervention in (True, False, None):
            with self.subTest(drug=intervention):
                out = review_record(trial(drug=intervention), as_of=date(2026, 10, 15))
                self.assertEqual(out["act_eligibility"], "UNDETERMINED")
                self.assertEqual(out["results_legal_overdue_status"], "UNDETERMINED")
                self.assertTrue(out["us_site_observed"])

    def test_non_us_sites_never_exclude_other_fda_nexus(self):
        outside = trial(locations=[{"country": "Canada"}], drug=None, device=None)
        out = review_record(outside, as_of=date(2026, 10, 15))
        self.assertFalse(out["us_site_observed"])
        self.assertEqual(out["act_eligibility"], "UNDETERMINED")

    def test_completed_with_posted_results_not_missing(self):
        out = review_record(trial(results=True, posted="2024-09-01"), as_of=date(2026, 10, 15))
        self.assertIs(out["one_year_elapsed_without_posted_results"], False)
        self.assertEqual(out["registry_posting_clock"], "RESULTS_POSTED_IN_REGISTRY")
        self.assertEqual(out["review_priority"], "DESCRIPTIVE_ONLY")

    def test_invalid_id_and_partial_date_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "NCT"):
            review_record(trial(nct_id="NCT-123"), as_of=date(2026, 10, 15))
        self.assertIsNone(exact_date("2025-03"))
        self.assertIsNone(exact_date("2025-02-30"))

    def test_not_interventional_never_automatically_legal_compliance(self):
        out = review_record(trial(study_type="OBSERVATIONAL"), as_of=date(2026, 10, 15))
        self.assertEqual(out["review_priority"], "DESCRIPTIVE_ONLY")
        self.assertEqual(out["act_eligibility"], "UNDETERMINED")

    def test_input_not_modified(self):
        study = trial()
        previous = json.dumps(study, sort_keys=True)
        review_record(study, as_of=date(2026, 10, 15))
        self.assertEqual(json.dumps(study, sort_keys=True), previous)


if __name__ == "__main__":
    unittest.main()
