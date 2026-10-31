# Builder repair of audit A5

Owner: coordinator builder, not auditor. The supplied checkpoint and pre-repair candidate both accept NaN freshness; restoring either preserves the defect. See audit-repair-restore-check.json and the preserved pre-repair source ZIP.

Changed only numeric criteria validation in scoring/sealing.py: card and question freshness must be finite non-boolean numbers greater than zero; both cost bounds must be finite non-boolean numbers at least zero. Valid card serialization/hashes remain unchanged. No past chain was rewritten.

Five added tests cover NaN, both infinities, both booleans, negative and zero boundaries, question overrides, cost units, valid fractional freshness/zero cost, and actual CLI refusal before a chain or score exists. Targeted five-test result passes in numeric-criteria-builder-tests.log. Reviewed the helper’s original reproduction and the three validation branches; the correction prevents comparisons against NaN from suppressing stale-page flags. Full integrated rerun follows the claims builder repair, then the separate auditor owns closure.
