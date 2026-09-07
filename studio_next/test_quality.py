"""Synthetic tests for quality policy; not game, model, or runtime tests."""
import copy
from dataclasses import replace
import unittest

from quality import (DIMENSIONS, TECH_NAMES, HumanDecision, InvalidReview,
                     ReviewIdentity, Rubric, Snapshot, TechnicalReport,
                     check_format_tokens, language_gate, parse_review,
                     review_schema, suggested_revision, text_hash)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.rubric = Rubric()
        # Independently authored test text, not an extraction from a game.
        self.snapshot = Snapshot("test-project", "row-1", 1,
                                 "合計%d、{NAME}", "รวม%d, {NAME}")
        self.identity = ReviewIdentity(self.snapshot, self.rubric.digest,
                                       text_hash("policy"), text_hash("context"),
                                       text_hash("model"), text_hash("prompt"))
        self.tech_config = text_hash("technical-config")

    def payload(self, **updates):
        data = dict(self.snapshot.wire_identity(), scores=dict(zip(DIMENSIONS, self.rubric.weights)),
                    issues=[], suggested_target=None, review_confidence=0.8)
        data.update(updates)
        return data

    def review(self, **updates):
        return parse_review(self.payload(**updates), self.identity)

    def tech(self, **updates):
        # These PASS values are test fixtures, never real game evidence.
        values = {name: "PASS" for name in TECH_NAMES}
        values.update(updates)
        return TechnicalReport.from_host(self.snapshot, self.tech_config, values)

    def human(self, action="APPROVED"):
        return HumanDecision(self.snapshot, self.identity.language_policy_sha256,
                             self.identity.context_sha256, action, "synthetic-tester")

    def gate(self, technical=None, review=None, human=None, **kwargs):
        return language_gate(self.identity, self.tech_config,
                             self.tech() if technical is None else technical,
                             self.review() if review is None else review,
                             self.human() if human is None else human, **kwargs)

    def issue(self, severity="critical"):
        return {"type": "semantic", "severity": severity, "message": "Test issue, not a real assessment",
                "source_quote": "合計", "target_quote": "รวม"}

    def test_host_computes_total(self):
        report = self.review()
        self.assertEqual(report.total, 100)
        self.assertEqual(report.assessed_maximum, 100)

    def test_model_total_is_not_accepted(self):
        with self.assertRaises(InvalidReview): self.review(total=100)

    def test_ai_cannot_set_human_approved(self):
        with self.assertRaises(InvalidReview): self.review(human_approved=True)

    def test_json_requires_all_score_components(self):
        scores = self.payload()["scores"]
        del scores["context"]
        with self.assertRaises(InvalidReview): self.review(scores=scores)

    def test_score_out_of_range_rejected_without_clipping(self):
        scores = self.payload()["scores"]
        scores["semantic"] = 36
        with self.assertRaises(InvalidReview): self.review(scores=scores)

    def test_negative_score_rejected(self):
        scores = self.payload()["scores"]
        scores["fluency"] = -1
        with self.assertRaises(InvalidReview): self.review(scores=scores)

    def test_boolean_score_rejected(self):
        scores = self.payload()["scores"]
        scores["semantic"] = True
        with self.assertRaises(InvalidReview): self.review(scores=scores)

    def test_fractional_score_rejected(self):
        scores = self.payload()["scores"]
        scores["semantic"] = 34.5
        with self.assertRaises(InvalidReview): self.review(scores=scores)

    def test_missing_context_is_partial_not_normalized(self):
        scores = self.payload()["scores"]
        scores["context"] = None
        report = self.review(scores=scores)
        self.assertIsNone(report.total)
        self.assertEqual((report.assessed_points, report.assessed_maximum), (85, 85))
        self.assertIn("QUALITY_PARTIAL", self.gate(review=report).blockers)

    def test_all_unassessed_is_not_zero_quality(self):
        report = self.review(scores={name: None for name in DIMENSIONS})
        self.assertIsNone(report.total)
        self.assertEqual(report.assessed_maximum, 0)

    def test_confidence_is_not_used_for_gate(self):
        self.assertTrue(self.gate(review=self.review(review_confidence=0)).ready_for_binary_checks)
        self.assertTrue(self.gate(review=self.review(review_confidence=None)).ready_for_binary_checks)

    def test_nan_confidence_rejected(self):
        with self.assertRaises(InvalidReview): self.review(review_confidence=float("nan"))

    def test_infinite_confidence_rejected(self):
        with self.assertRaises(InvalidReview): self.review(review_confidence=float("inf"))

    def test_boolean_confidence_rejected(self):
        with self.assertRaises(InvalidReview): self.review(review_confidence=True)

    def test_revision_boolean_rejected(self):
        with self.assertRaises(InvalidReview): self.review(revision=True)

    def test_wrong_project_rejected(self):
        with self.assertRaises(InvalidReview): self.review(project_id="another-project")

    def test_wrong_source_hash_rejected(self):
        with self.assertRaises(InvalidReview): self.review(source_sha256=text_hash("changed"))

    def test_wrong_target_hash_rejected(self):
        with self.assertRaises(InvalidReview): self.review(target_sha256=text_hash("changed"))

    def test_wrong_revision_rejected(self):
        with self.assertRaises(InvalidReview): self.review(revision=2)

    def test_nonexistent_quote_rejected(self):
        issue = self.issue()
        issue["source_quote"] = "not in source"
        with self.assertRaises(InvalidReview): self.review(issues=[issue])

    def test_unknown_issue_severity_rejected(self):
        with self.assertRaises(InvalidReview): self.review(issues=[self.issue("approved")])

    def test_bounded_issue_array(self):
        with self.assertRaises(InvalidReview): self.review(issues=[self.issue()] * 101)

    def test_critical_meaning_blocks_even_at_100(self):
        report = self.review(issues=[self.issue()])
        self.assertEqual(report.total, 100)
        self.assertIn("MEANING_ISSUE_UNRESOLVED", self.gate(review=report).blockers)

    def test_major_meaning_blocks_even_at_100(self):
        self.assertIn("MEANING_ISSUE_UNRESOLVED", self.gate(review=self.review(issues=[self.issue("major")])).blockers)

    def test_warning_preserved_separately(self):
        result = self.gate(review=self.review(issues=[self.issue("warning")]))
        self.assertTrue(result.ready_for_binary_checks)
        self.assertIn("AI_REVIEW_WARNINGS", result.warnings)

    def test_technical_failure_blocks_high_score(self):
        result = self.gate(technical=self.tech(printf="FAIL"))
        self.assertIn("TECHNICAL_FAIL:printf", result.blockers)
        self.assertFalse(result.ready_for_binary_checks)

    def test_missing_check_remains_unknown(self):
        report = TechnicalReport.from_host(self.snapshot, self.tech_config,
                                           check_format_tokens(self.snapshot.source, self.snapshot.target))
        self.assertEqual(dict(report.checks)["encoding"], "NOT_EVALUATED")
        self.assertIn("TECHNICAL_NOT_EVALUATED:encoding", self.gate(technical=report).blockers)

    def test_no_technical_report_is_not_pass(self):
        result = language_gate(self.identity, self.tech_config, None, self.review(), self.human())
        self.assertIn("TECHNICAL_NOT_EVALUATED", result.blockers)

    def test_unknown_check_name_rejected(self):
        with self.assertRaises(ValueError):
            TechnicalReport.from_host(self.snapshot, self.tech_config, {"font_ok": "PASS"})

    def test_wrong_technical_result_rejected(self):
        with self.assertRaises(ValueError): self.tech(encoding="YES")

    def test_required_warning_does_not_pass(self):
        self.assertIn("TECHNICAL_WARNING:pixel_width", self.gate(technical=self.tech(pixel_width="WARNING")).blockers)

    def test_technical_config_change_invalidates_technical_only(self):
        report = replace(self.tech(), configuration_sha256=text_hash("new-font"))
        result = self.gate(technical=report)
        self.assertEqual(result.blockers, ("TECHNICAL_STALE",))

    def test_model_change_invalidates_ai_not_human(self):
        changed = replace(self.identity, model_digest=text_hash("other-model"))
        self.assertTrue(self.human().applies_to(changed))
        result = language_gate(changed, self.tech_config, self.tech(), self.review(), self.human())
        self.assertIn("AI_REVIEW_STALE", result.blockers)
        self.assertNotIn("HUMAN_REVIEW_REQUIRED", result.blockers)

    def test_context_change_invalidates_ai_and_human(self):
        changed = replace(self.identity, context_sha256=text_hash("new-speaker"))
        result = language_gate(changed, self.tech_config, self.tech(), self.review(), self.human())
        self.assertIn("AI_REVIEW_STALE", result.blockers)
        self.assertIn("HUMAN_REVIEW_REQUIRED", result.blockers)

    def test_target_change_invalidates_all_old_evidence(self):
        current = replace(self.identity, snapshot=replace(self.snapshot, target="แก้ใหม่", revision=2))
        result = language_gate(current, self.tech_config, self.tech(), self.review(), self.human())
        self.assertEqual(set(result.blockers), {"TECHNICAL_STALE", "AI_REVIEW_STALE", "HUMAN_REVIEW_REQUIRED"})

    def test_release_requires_human_action(self):
        result = language_gate(self.identity, self.tech_config, self.tech(), self.review(), None)
        self.assertIn("HUMAN_REVIEW_REQUIRED", result.blockers)

    def test_release_policy_can_omit_human_but_never_fakes_approval(self):
        result = language_gate(self.identity, self.tech_config, self.tech(), self.review(), None, require_human=False)
        self.assertTrue(result.ready_for_binary_checks)
        self.assertIn("HUMAN_REVIEW_NOT_CURRENT", result.warnings)

    def test_human_rejection_blocks_even_test_mode(self):
        self.assertIn("HUMAN_REVIEW_NOT_APPROVED", self.gate(human=self.human("REJECTED"), mode="test").blockers)

    def test_test_mode_allows_missing_language_review_with_warning(self):
        result = language_gate(self.identity, self.tech_config, self.tech(), None, None, mode="test")
        self.assertTrue(result.ready_for_binary_checks)
        self.assertIn("TEST_BUILD_WITHOUT_CURRENT_AI_REVIEW", result.warnings)
        self.assertIn("HUMAN_REVIEW_NOT_CURRENT", result.warnings)

    def test_test_mode_does_not_bypass_encoding_failure(self):
        self.assertIn("TECHNICAL_FAIL:encoding", self.gate(technical=self.tech(encoding="FAIL"), mode="test").blockers)

    def test_low_score_blocks_release(self):
        scores = {name: 0 for name in DIMENSIONS}
        self.assertIn("QUALITY_BELOW_THRESHOLD", self.gate(review=self.review(scores=scores)).blockers)

    def test_malformed_gate_policy_rejected(self):
        with self.assertRaises(ValueError): self.gate(minimum_score=True)
        with self.assertRaises(ValueError): self.gate(mode="anything")

    def test_named_placeholder_count(self):
        self.assertEqual(check_format_tokens("{NAME}{NAME}", "{NAME}")["placeholders"], "FAIL")

    def test_named_placeholder_reordering_is_allowed(self):
        self.assertEqual(check_format_tokens("{A}{B}", "{B}{A}")["placeholders"], "PASS")

    def test_printf_loss_detected(self):
        self.assertEqual(check_format_tokens("Value %d", "Value")["printf"], "FAIL")

    def test_printf_order_preserved(self):
        self.assertEqual(check_format_tokens("%s %d", "%d %s")["printf"], "FAIL")

    def test_literal_percent_not_an_argument(self):
        self.assertEqual(check_format_tokens("%%d", "percent d")["printf"], "PASS")

    def test_printf_width_and_stars_preserved(self):
        self.assertEqual(check_format_tokens("%3$*2$.*1$f", "%3$*2$.*1$f")["printf"], "PASS")
        self.assertEqual(check_format_tokens("%03d", "%d")["printf"], "FAIL")

    def test_suggestion_is_a_new_unapproved_revision(self):
        review = self.review(suggested_target="ยอดรวม%d, {NAME}")
        new = suggested_revision(self.snapshot, review)
        self.assertEqual(new.revision, 2)
        self.assertEqual(self.snapshot.revision, 1)
        changed = replace(self.identity, snapshot=new)
        self.assertFalse(self.human().applies_to(changed))
        self.assertIn("AI_REVIEW_STALE", language_gate(changed, self.tech_config, self.tech(), review, self.human()).blockers)

    def test_suggestion_on_stale_revision_rejected(self):
        review = self.review(suggested_target="ยอดรวม%d, {NAME}")
        with self.assertRaises(InvalidReview): suggested_revision(replace(self.snapshot, revision=2), review)

    def test_unchanged_suggestion_does_not_bump_revision(self):
        with self.assertRaises(InvalidReview):
            suggested_revision(self.snapshot, self.review(suggested_target=self.snapshot.target))

    def test_schema_does_not_offer_approval_or_total(self):
        props = review_schema()["properties"]
        self.assertNotIn("total", props)
        self.assertNotIn("human_approved", props)
        self.assertFalse(review_schema()["additionalProperties"])

    def test_rubric_reconfiguration_is_fingerprinted(self):
        custom = Rubric((40, 20, 10, 15, 10, 5), "custom")
        self.assertNotEqual(custom.digest, self.rubric.digest)
        with self.assertRaises(InvalidReview): parse_review(self.payload(), self.identity, custom)

    def test_invalid_weights_rejected(self):
        with self.assertRaises(ValueError): Rubric((35, 20, 15, 15, 10, 6))
        with self.assertRaises(ValueError): Rubric((True, 20, 15, 15, 10, 39))

    def test_bad_identity_hash_rejected(self):
        with self.assertRaises(ValueError): replace(self.identity, model_digest="not-a-digest")

    def test_empty_actor_cannot_approve(self):
        with self.assertRaises(ValueError): replace(self.human(), actor=" ")

    def test_payload_not_mutated(self):
        payload = self.payload()
        previous = copy.deepcopy(payload)
        parse_review(payload, self.identity)
        self.assertEqual(payload, previous)

    def test_result_is_not_a_complete_build_gate(self):
        result = self.gate()
        self.assertTrue(result.ready_for_binary_checks)
        self.assertFalse(hasattr(result, "build_ready"))
        self.assertFalse(hasattr(result, "runtime_verified"))


if __name__ == "__main__":
    unittest.main()
