# ClinicalTrials.gov regulatory-proxy reporting-gap study

**Scientific and regulatory interpretation correction — 15 October 2026**

The archived 29 March 2026 summary and E156 figures are observational counts of missing posted results among **registry-derived ACT-style proxies**, **not validated numbers of applicable clinical trials (ACTs), missed legal deadlines, or FDAAA violations**. This repo originally presented a broad/strict U.S.-nexus study group as “probable ACT/FDAAA debt”. Such terminology risks overstating what visible registry fields can establish.

In particular:
- US location is neither necessary nor sufficient for ACT status: product regulation, IND/IDE, export jurisdiction, study phase and purpose matter. A trial outside the US may still fall under FDA jurisdiction, and a US-site trial may not.
- FDAAA and the January 2017 Final Rule are not interchangeable for historical trials. Different effective dates, transition rules, scope and exceptions require review.
- 42 CFR 11.44 generally specifies one year from primary completion for applicable trials subject to 11.42, but permits certain certifications, delayed submissions and extensions. A registry **one-calendar-year elapsed** screen cannot establish the actual deadline or a breach. Also distinguish initial submission, public posting, exemptions and quality control.
- Absence of a publication reference or posted results on a given download is not proof that evidence was never published.
- The existing published sample and its numerators have **not been recomputed** in this correction. The original snapshot is not reproduced in this repo at record level, so historical percentages should be interpreted as archived, unverified calculations.

## New machine-readable review queue

The zero-dependency Python module `src/act_proxy_audit.py` reviews individual **ClinicalTrials.gov API v2 JSONL** studies with transparent rules and a fixed reference date. It outputs one JSON line per NCT identifier, a SHA-256 metadata file and the following clearly separated states:

- `registry_posting_clock`: evidence of an ACTUAL, day-precise primary completion and elapsed one-calendar-year interval with/without results posted.
- `review_signals`: explicitly observed interventional, FDA-regulated product flags, study phase, intervention type and US site—not inferred legal conclusions.
- `act_eligibility: UNDETERMINED` and `results_legal_overdue_status: UNDETERMINED` **for every record**, without exceptions.
- `data_caveats`: partial/estimated dates, missing regulatory flags, contradictory or future posting information.
- `review_priority`: prioritisation for qualified human inspection, not a compliance accusation.

Usage with your **own independently verified v2 source export**:

```bash
python src/act_proxy_audit.py --input ctgov_studies.jsonl.gz --as-of 2026-10-15 --output out/registry_review.jsonl
python -m unittest discover -s tests -p 'test_act_proxy_audit.py'
```

This is a screening aid, **not a regulatory ACT classifier**. Prioritised records require source and legal review before claiming that results reporting was required, overdue or noncompliant.

## Primary sources

- [42 CFR 11.22 — criteria for applicable clinical trials](https://www.law.cornell.edu/cfr/text/42/11.22)
- [42 CFR 11.44 — results reporting deadlines and exceptions](https://www.law.cornell.edu/cfr/text/42/11.44)
- [Official ClinicalTrials.gov ACT checklist](https://cdn.clinicaltrials.gov/documents/ACT_Checklist.pdf)
- [NIH — relationship between FDAAA and NIH dissemination policy](https://grants.nih.gov/policy-and-compliance/policy-topics/clinical-trials/reporting/understanding)

The previous E156 protocol, study narrative, and historical dashboard are preserved with visible methodological notices. They should not be cited as independently verified ACT-compliance estimates without a reviewed record-level reanalysis.
