"""Authored JSON/translation fixtures only; no ROM, network or live model."""
from dataclasses import replace
import io
import json
import unittest

import quality
from review_payload import (InvalidReview, PayloadLimits, load_json_object,
                            read_json_object, parse_review_response)


def fixture():
    # Original test text, not copied from a game or a user's translation.
    snap = quality.Snapshot("unit-project", "test-key", 1,
                            "ここへ来てください。", "กรุณามาที่นี่")
    rubric = quality.Rubric()
    digest = quality.text_hash("authored test configuration")
    identity = quality.ReviewIdentity(snap, rubric.digest, digest, digest,
                                      digest, digest)
    payload = dict(snap.wire_identity(),
                   scores=dict(zip(quality.DIMENSIONS, rubric.weights)),
                   issues=[], suggested_target=None, review_confidence=0.5)
    return identity, payload


class ReviewPayloadTests(unittest.TestCase):
    def test_valid_thai_utf8_preserved(self):
        expected = {"text": "เก่งมาก น้ำ ผู้", "placeholder": "{NAME}"}
        raw = json.dumps(expected, ensure_ascii=False).encode("utf-8")
        self.assertEqual(load_json_object(raw), expected)
        self.assertEqual(load_json_object(raw.decode("utf-8")), expected)

    def test_whitespace_is_allowed(self):
        self.assertEqual(load_json_object(' \r\n {"a": 1} \t'), {"a": 1})

    def test_duplicate_keys_rejected_even_when_values_equal(self):
        with self.assertRaises(InvalidReview):
            load_json_object('{"a":1,"a":1}')

    def test_nested_duplicate_key_rejected(self):
        with self.assertRaises(InvalidReview):
            load_json_object('{"scores":{"semantic":1,"semantic":35}}')

    def test_escaped_duplicate_key_rejected(self):
        with self.assertRaises(InvalidReview):
            load_json_object(r'{"a":1,"\u0061":2}')

    def test_nonstandard_numbers_rejected(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token), self.assertRaises(InvalidReview):
                load_json_object('{"v":' + token + '}')

    def test_finite_syntax_overflow_rejected(self):
        for token in ("1e999", "-1e999"):
            with self.subTest(token=token), self.assertRaises(InvalidReview):
                load_json_object('{"v":' + token + '}')

    def test_number_tokens_bounded_before_conversion(self):
        for token in ("1" * 97, "0." + "1" * 97, "1e" + "9" * 97):
            with self.subTest(token=token[:8]), self.assertRaises(InvalidReview):
                load_json_object('{"v":' + token + '}')

    def test_strings_named_nan_are_not_numbers(self):
        self.assertEqual(load_json_object('{"v":"NaN"}'), {"v": "NaN"})

    def test_partial_json_and_trailing_payload_rejected(self):
        for raw in ('{"a":', '{"a":"unfinished}', '{"a":1', '{}{}',
                    '{} trailing text', '{"a":1,}', '{"a":]}', ''):
            with self.subTest(raw=raw), self.assertRaises(InvalidReview):
                load_json_object(raw)

    def test_markdown_or_reasoning_is_not_silently_stripped(self):
        for raw in ('```json\n{}\n```', '<think>hello</think>{}', 'Answer: {}'):
            with self.subTest(raw=raw), self.assertRaises(InvalidReview):
                load_json_object(raw)

    def test_top_level_must_be_object(self):
        for raw in ('[]', 'null', 'true', '10', '"text"'):
            with self.subTest(raw=raw), self.assertRaises(InvalidReview):
                load_json_object(raw)

    def test_invalid_utf8_and_bom_rejected(self):
        for raw in (b'{"v":"\xff"}', b'\xef\xbb\xbf{}', '\ufeff{}', '\ud800'):
            with self.subTest(raw=repr(raw)), self.assertRaises(InvalidReview):
                load_json_object(raw)

    def test_escaped_unpaired_surrogate_in_value_or_key_rejected(self):
        for raw in (r'{"v":"\ud800"}', r'{"v":"\udfff"}', r'{"\ud800":1}'):
            with self.subTest(raw=raw), self.assertRaises(InvalidReview):
                load_json_object(raw)

    def test_valid_surrogate_pair_accepted(self):
        self.assertEqual(load_json_object(r'{"v":"\ud83d\ude00"}'), {"v": "😀"})

    def test_depth_limit_includes_root(self):
        self.assertEqual(load_json_object('{"a":[{}]}', PayloadLimits(max_depth=3)),
                         {"a": [{}]})
        with self.assertRaises(InvalidReview):
            load_json_object('{"a":[{}]}', PayloadLimits(max_depth=2))

    def test_extreme_depth_rejected_before_decoder(self):
        raw = '{"a":' + '[' * 4000 + '0' + ']' * 4000 + '}'
        with self.assertRaisesRegex(InvalidReview, "nesting limit"):
            load_json_object(raw)

    def test_brackets_and_escaped_quotes_inside_strings_not_depth(self):
        expected = {"a": '[[[[[{{{ "quoted" \\ ]]]]]'}
        self.assertEqual(load_json_object(json.dumps(expected),
                                         PayloadLimits(max_depth=1)), expected)

    def test_byte_limit_is_not_character_limit(self):
        raw = json.dumps({"a": "ก" * 10}, ensure_ascii=False)
        self.assertLess(len(raw), len(raw.encode("utf-8")))
        with self.assertRaises(InvalidReview):
            load_json_object(raw, PayloadLimits(max_bytes=len(raw)))

    def test_exact_size_accepted_and_one_over_rejected(self):
        self.assertEqual(load_json_object(b'{}', PayloadLimits(max_bytes=2)), {})
        with self.assertRaises(InvalidReview):
            load_json_object(b'{} ', PayloadLimits(max_bytes=2))

    def test_keys_and_strings_have_limits(self):
        self.assertEqual(load_json_object('{"abc":"def"}',
                                         PayloadLimits(max_string_chars=3)),
                         {"abc": "def"})
        for raw in ('{"abcd":1}', '{"a":"abcd"}'):
            with self.subTest(raw=raw), self.assertRaises(InvalidReview):
                load_json_object(raw, PayloadLimits(max_string_chars=3))

    def test_node_count_includes_keys_and_containers(self):
        self.assertEqual(load_json_object('{"a":[1,2]}', PayloadLimits(max_nodes=5)),
                         {"a": [1, 2]})
        with self.assertRaises(InvalidReview):
            load_json_object('{"a":[1,2]}', PayloadLimits(max_nodes=4))

    def test_invalid_limits_rejected(self):
        for name, value in (("max_bytes", True), ("max_depth", 0),
                            ("max_depth", 65), ("max_nodes", -1),
                            ("max_string_chars", 2.5), ("max_number_chars", 129),
                            ("max_bytes", 2_097_153)):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                PayloadLimits(**{name: value})
        with self.assertRaises(ValueError):
            load_json_object('{}', None)

    def test_non_text_input_rejected(self):
        for raw in ({}, None, bytearray(b'{}'), 5):
            with self.subTest(raw=raw), self.assertRaises(InvalidReview):
                load_json_object(raw)

    def test_short_reads_and_caller_stream_lifetime(self):
        class Short(io.BytesIO):
            def read(self, count=-1):
                self.last_count = count
                return super().read(min(count, 1))
        stream = Short(b'{"a":1}')
        self.assertEqual(read_json_object(stream), {"a": 1})
        self.assertFalse(stream.closed)
        self.assertGreater(stream.last_count, 0)

    def test_stream_reads_no_more_than_limit_plus_one(self):
        class Endless:
            consumed = 0
            def read(self, count):
                self.consumed += count
                return b' ' * count
        stream = Endless()
        with self.assertRaises(InvalidReview):
            read_json_object(stream, PayloadLimits(max_bytes=32))
        self.assertEqual(stream.consumed, 33)

    def test_exact_length_stream_allowed(self):
        self.assertEqual(read_json_object(io.BytesIO(b'{}'),
                                         PayloadLimits(max_bytes=2)), {})

    def test_invalid_stream_return_rejected(self):
        class Bad:
            def __init__(self, value):
                self.value = value
            def read(self, count):
                return self.value
        for value in (None, '{}', b'x' * 100):
            with self.subTest(value=repr(value)), self.assertRaises(InvalidReview):
                read_json_object(Bad(value), PayloadLimits(max_bytes=2))

    def test_io_error_propagates_without_retry(self):
        class Broken:
            calls = 0
            def read(self, count):
                self.calls += 1
                raise OSError("fixture disconnect")
        stream = Broken()
        with self.assertRaises(OSError):
            read_json_object(stream)
        self.assertEqual(stream.calls, 1)

    def test_valid_payload_uses_existing_core(self):
        expected, payload = fixture()
        raw = json.dumps(payload, ensure_ascii=False)
        result = parse_review_response(raw, expected)
        self.assertEqual(result.total, 100)
        self.assertEqual(result.identity, expected)
        self.assertIsNone(result.suggested_target)
        self.assertEqual(json.loads(raw), payload)

    def test_stale_identity_rejected_after_decoding(self):
        expected, payload = fixture()
        payload['revision'] = 2
        with self.assertRaises(InvalidReview):
            parse_review_response(json.dumps(payload), expected)

    def test_duplicate_identity_rejected_before_last_value_can_win(self):
        expected, payload = fixture()
        raw = json.dumps(payload)
        raw = '{"revision":9,' + raw[1:]
        with self.assertRaisesRegex(InvalidReview, 'duplicate'):
            parse_review_response(raw, expected)

    def test_model_cannot_supply_total_or_human_approval(self):
        expected, payload = fixture()
        for key, value in (("total", 100), ("human_approved", True)):
            with self.subTest(key=key), self.assertRaises(InvalidReview):
                parse_review_response(json.dumps(dict(payload, **{key: value})),
                                      expected)

    def test_bad_score_is_error_not_clipped_or_zero(self):
        expected, payload = fixture()
        for value in (36, True, 31.5):
            payload['scores']['semantic'] = value
            with self.subTest(value=value), self.assertRaises(InvalidReview):
                parse_review_response(json.dumps(payload), expected)

    def test_partial_review_retains_unknown_total(self):
        expected, payload = fixture()
        payload['scores']['context'] = None
        result = parse_review_response(json.dumps(payload), expected)
        self.assertIsNone(result.total)
        self.assertEqual(result.assessed_maximum, 85)

    def test_outer_ollama_envelope_is_not_review_content(self):
        expected, payload = fixture()
        envelope = {'message': {'role': 'assistant', 'content': json.dumps(payload)}}
        with self.assertRaises(InvalidReview):
            parse_review_response(json.dumps(envelope), expected)

    def test_error_messages_do_not_echo_model_content(self):
        secret = 'private-example-never-log'
        with self.assertRaises(InvalidReview) as result:
            load_json_object(json.dumps({secret: 1})[:-1] + ',"' + secret + '":2}')
        self.assertNotIn(secret, str(result.exception))


if __name__ == '__main__':
    unittest.main()
