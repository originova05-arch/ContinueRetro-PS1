import unittest
from quality import (DIMENSIONS, InvalidReview, ReviewIdentity, Rubric, Snapshot,
                     parse_review, suggested_revision, text_hash)


class ReviewBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.rubric = Rubric()
        self.snapshot = Snapshot("fixture", "fixture-1", 1, "確認", "ตรวจสอบ")
        digest = text_hash("fixture-policy")
        self.identity = ReviewIdentity(self.snapshot, self.rubric.digest, digest,
                                       digest, digest, digest)
        self.payload = dict(self.snapshot.wire_identity(),
                            scores=dict(zip(DIMENSIONS, self.rubric.weights)),
                            issues=[], suggested_target=None, review_confidence=None)

    def test_huge_positive_integer_confidence_fails_without_float_overflow(self):
        self.payload["review_confidence"] = 10 ** 1000
        with self.assertRaises(InvalidReview):
            parse_review(self.payload, self.identity)

    def test_huge_negative_integer_confidence_fails_without_float_overflow(self):
        self.payload["review_confidence"] = -(10 ** 1000)
        with self.assertRaises(InvalidReview):
            parse_review(self.payload, self.identity)

    def test_missing_top_level_field_is_review_error_not_score_zero(self):
        del self.payload["scores"]
        with self.assertRaises(InvalidReview):
            parse_review(self.payload, self.identity)

    def test_absent_suggestion_cannot_create_revision(self):
        review = parse_review(self.payload, self.identity)
        with self.assertRaises(InvalidReview):
            suggested_revision(self.snapshot, review)


if __name__ == "__main__":
    unittest.main()
