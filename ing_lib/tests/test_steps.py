from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ing_lib import steps


START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
TIMEOUT = 10
ARITIES = [
    ("RECORD", 0),
    ("NOT_PRESENT", 0),
    ("GREATER_THAN", 1),
    ("GREATER_THAN_OR_EQUAL", 1),
    ("LESS_THAN", 1),
    ("LESS_THAN_OR_EQUAL", 1),
    ("EQUAL", 1),
    ("NOT_EQUAL", 1),
    ("INCLUSIVE_RANGE", 2),
    ("EXCLUSIVE_RANGE", 2),
]


def prediction(uuid="A", condition="EQUAL", values=(1,), **overrides):
    result = {
        "telem_uuid": uuid,
        "verify_wait": "VERIFY",
        "dn_eu": "DN",
        "verification_condition": condition,
        "verification_values": list(values),
    }
    result.update(overrides)
    return result


def sample(raw=1, eng=101):
    return {"raw_value": raw, "eng_value": eng}


def assert_prediction(result, predict, status, value=None, details=None):
    assert result == {
        "telem_uuid": predict["telem_uuid"],
        "predict": predict,
        "actual_value": value,
        "verification_status": status,
        "data_present": details is not None,
        "telem_details": details,
    }


def assert_calls(provider, count, channels, lookback=0):
    assert provider.calls == [
        (channels, TIMEOUT, lookback, START, steps.ReturnOn.ANY)
        for _ in range(count)
    ]


@pytest.fixture
def clock():
    state = SimpleNamespace(current=START)

    def now(tz):
        assert tz is timezone.utc
        return state.current

    with patch.object(steps, "datetime") as patched_datetime:
        patched_datetime.now.side_effect = now
        yield state


@pytest.fixture
def scripted_callback(clock):
    def make(*polls):
        calls = []

        def callback(channels, timeout, lookback, start_time, return_on):
            index = len(calls)
            if index >= len(polls):
                pytest.fail("Telemetry callback called after its script was exhausted")
            calls.append(deepcopy((channels, timeout, lookback, start_time, return_on)))
            elapsed, histories = polls[index]
            clock.current = START + timedelta(seconds=elapsed)
            return histories

        return SimpleNamespace(callback=callback, calls=calls)

    return make


@pytest.mark.parametrize(
    "value, expected",
    [(0, True), (-2, True), (1.5, True), ("0", True), ("-2.5", True),
     ("1e3", True), (" 4 ", True), ("0x10", False), ("", False),
     ("text", False), (None, False), ([], False)],
)
def test_confirm_numeric(value, expected):
    assert steps.confirm_numeric(value) is expected


@pytest.mark.parametrize(
    "mask, and_value, or_value",
    [("0b0011", 2, 11), ("0B0011", 2, 11), ("0x03", 2, 11),
     ("0X03", 2, 11), ("3", 2, 11), (3, 2, 11), ("0", 0, 10), (0, 0, 10)],
)
@pytest.mark.parametrize("operation", ["AND", "OR"])
def test_apply_bit_mask(mask, and_value, or_value, operation):
    result = steps.apply_bit_mask("10", mask, operation)
    assert result == (and_value if operation == "AND" else or_value)
    assert isinstance(result, int)


@pytest.mark.parametrize(
    "value, mask, operation",
    [("text", "3", "AND"), (10, "0b102", "AND"),
     (10, "0xGG", "OR"), (10, "invalid", "AND"),
     (10, "1.5", "OR"), (10, "3", "XOR")],
)
def test_apply_bit_mask_rejects_invalid_input(value, mask, operation):
    with pytest.raises(steps.BitMaskError):
        steps.apply_bit_mask(value, mask, operation)


@pytest.mark.parametrize("condition, arity", ARITIES)
def test_query_validation_accepts_operator_arities(condition, arity):
    query = [prediction(condition=condition, values=range(arity))]
    original = deepcopy(query)
    assert steps.check_telemetry_query(query) is None
    assert query == original


@pytest.mark.parametrize(
    "condition, count",
    [(condition, count) for condition, arity in ARITIES
     for count in (arity - 1, arity + 1) if count >= 0],
)
def test_query_validation_rejects_wrong_operator_arities(condition, count):
    with pytest.raises(steps.InputError):
        steps.check_telemetry_query([prediction(condition=condition, values=range(count))])


@pytest.mark.parametrize(
    "overrides",
    [{"dn_eu": "RAW"}, {"verify_wait": "RETRY"},
     {"verification_condition": "UNKNOWN"},
     {"bit_op": "XOR", "bit_mask": "3"}, {"bit_op": "AND"},
     {"bit_op": "OR", "bit_mask": None}, {"bit_mask": "3"},
     {"bit_mask": 0}, {"bit_mask": "3", "bit_op": None},
     {"bit_mask": "3", "bit_op": "AND", "verification_values": ["text"]},
     {"prior_value": "text"}, {"prior_value": 0, "verification_values": ["text"]}],
)
def test_query_validation_rejects_invalid_configuration(overrides):
    with pytest.raises(steps.InputError):
        steps.check_telemetry_query([prediction(**overrides)])


@pytest.mark.parametrize(
    "overrides",
    [{}, {"bit_mask": None, "bit_op": None}, {"prior_value": 0},
     {"prior_value": "2.5", "verification_values": ["3"]},
     {"bit_mask": 0, "bit_op": "AND"},
     {"dn_eu": "EU", "verify_wait": "WAIT", "bit_mask": "0X03", "bit_op": "OR"}],
)
def test_query_validation_accepts_optional_configuration(overrides):
    steps.check_telemetry_query([prediction(**overrides)])


def test_invalid_later_duplicate_is_validated_before_callback(clock):
    query = [prediction(), prediction("B"), prediction(dn_eu="INVALID")]
    original = deepcopy(query)
    provider = Mock(side_effect=AssertionError("Invalid query must not reach the provider"))
    with pytest.raises(steps.InputError):
        steps.verify_wait_telemetry(query, provider, start_time=START)
    provider.assert_not_called()
    assert query == original


@pytest.mark.parametrize(
    "condition, values, actual, status",
    [("GREATER_THAN", [5], 4, "FAIL"), ("GREATER_THAN", [5], 5, "FAIL"),
     ("GREATER_THAN", [5], 6, "PASS"),
     ("GREATER_THAN_OR_EQUAL", [5], 4, "FAIL"),
     ("GREATER_THAN_OR_EQUAL", [5], 5, "PASS"),
     ("GREATER_THAN_OR_EQUAL", [5], 6, "PASS"),
     ("LESS_THAN", [5], 4, "PASS"), ("LESS_THAN", [5], 5, "FAIL"),
     ("LESS_THAN", [5], 6, "FAIL"),
     ("LESS_THAN_OR_EQUAL", [5], 4, "PASS"),
     ("LESS_THAN_OR_EQUAL", [5], 5, "PASS"),
     ("LESS_THAN_OR_EQUAL", [5], 6, "FAIL"),
     ("INCLUSIVE_RANGE", [3, 7], 2, "FAIL"),
     ("INCLUSIVE_RANGE", [3, 7], 3, "PASS"),
     ("INCLUSIVE_RANGE", [3, 7], 5, "PASS"),
     ("INCLUSIVE_RANGE", [3, 7], 7, "PASS"),
     ("INCLUSIVE_RANGE", [3, 7], 8, "FAIL"),
     ("EXCLUSIVE_RANGE", [3, 7], 2, "FAIL"),
     ("EXCLUSIVE_RANGE", [3, 7], 3, "FAIL"),
     ("EXCLUSIVE_RANGE", [3, 7], 5, "PASS"),
     ("EXCLUSIVE_RANGE", [3, 7], 7, "FAIL"),
     ("EXCLUSIVE_RANGE", [3, 7], 8, "FAIL"),
     ("EQUAL", ["5.0"], 5, "PASS"), ("EQUAL", [5], "6", "FAIL"),
     ("NOT_EQUAL", [5], "5.0", "FAIL"), ("NOT_EQUAL", ["5"], 6, "PASS"),
     ("EQUAL", ["ON"], "ON", "PASS"), ("EQUAL", ["ON"], "OFF", "FAIL"),
     ("NOT_EQUAL", ["ON"], "ON", "FAIL"), ("NOT_EQUAL", ["ON"], "OFF", "PASS")],
)
def test_evaluate_comparison_operators(condition, values, actual, status):
    predict = prediction(condition=condition, values=values)
    telemetry = [sample(actual)]
    result = steps.evaluate_verify_condition(telemetry, predict, False)
    assert_prediction(result, predict, status, actual, telemetry[-1])


@pytest.mark.parametrize("dn_eu, expected", [("DN", 10), ("EU", 110)])
@pytest.mark.parametrize("optional", [{}, {"bit_mask": None, "bit_op": None}])
def test_evaluate_latest_sample_without_optional_mask(dn_eu, expected, optional):
    predict = prediction(values=[expected], dn_eu=dn_eu, **optional)
    telemetry = [sample(0, 100), sample(10, 110)]
    original = deepcopy((predict, telemetry))
    with patch.object(steps, "apply_bit_mask", wraps=steps.apply_bit_mask) as mask:
        result = steps.evaluate_verify_condition(telemetry, predict, False)
    mask.assert_not_called()
    assert_prediction(result, predict, "PASS", expected, telemetry[-1])
    assert (predict, telemetry) == original


@pytest.mark.parametrize(
    "overrides, expected",
    [({}, 29), ({"dn_eu": "EU"}, 129), ({"prior_value": 0}, 29),
     ({"prior_value": "2.5"}, 26.5),
     ({"bit_mask": 0, "bit_op": "AND"}, 0),
     ({"bit_mask": "0x0F", "bit_op": "AND", "prior_value": 0}, 13),
     ({"dn_eu": "EU", "bit_mask": "0x0F", "bit_op": "AND", "prior_value": "3"}, 10),
     ({"dn_eu": "EU", "bit_mask": "0B0010", "bit_op": "OR", "prior_value": "1"}, 30)],
)
def test_evaluate_record_selects_and_transforms_without_mutation(overrides, expected):
    predict = prediction(condition="RECORD", values=[], **overrides)
    raw = "29" if overrides == {"prior_value": 0} else 29
    telemetry = [sample(raw, 129)]
    original = deepcopy((predict, telemetry))
    result = steps.evaluate_verify_condition(telemetry, predict, False)
    assert_prediction(result, predict, "PASS", expected, telemetry[-1])
    assert (predict, telemetry) == original
    sibling = prediction(values=[29])
    assert_prediction(
        steps.evaluate_verify_condition(telemetry, sibling, False),
        sibling, "PASS", raw, telemetry[-1],
    )
    assert (predict, telemetry) == original


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
@pytest.mark.parametrize("telemetry", [None, []])
@pytest.mark.parametrize(
    "condition, values, timed_out, status",
    [("EQUAL", [1], False, "PENDING"), ("EQUAL", [1], True, "FAIL"),
     ("RECORD", [], False, "PENDING"), ("RECORD", [], True, "FAIL"),
     ("NOT_PRESENT", [], False, "PENDING"), ("NOT_PRESENT", [], True, "PASS")],
)
def test_evaluate_no_data_states(verify_wait, telemetry, condition, values, timed_out, status):
    predict = prediction(condition=condition, values=values, verify_wait=verify_wait)
    assert_prediction(
        steps.evaluate_verify_condition(telemetry, predict, timed_out), predict, status,
    )


@pytest.mark.parametrize("timed_out", [False, True])
def test_evaluate_not_present_with_data_fails(timed_out):
    predict = prediction(condition="NOT_PRESENT", values=[])
    telemetry = [sample()]
    assert_prediction(
        steps.evaluate_verify_condition(telemetry, predict, timed_out),
        predict, "FAIL", 1, telemetry[-1],
    )


@pytest.mark.parametrize("raw, mask", [(1, "0xGG"), ("text", "3")])
def test_evaluate_bit_mask_error_becomes_input_error(raw, mask):
    predict = prediction(bit_mask=mask, bit_op="AND")
    with pytest.raises(steps.InputError):
        steps.evaluate_verify_condition([sample(raw)], predict, False)


@pytest.mark.parametrize("variant", ["identical", "transformed"])
def test_interleaved_duplicate_predictions_and_callback_contract(scripted_callback, variant):
    first = prediction(values=[13])
    query = [first, prediction("B", values=[42], dn_eu="EU")]
    if variant == "identical":
        query.extend([deepcopy(first), deepcopy(first)])
        expected = [13, 42, 13, 13]
    else:
        query.extend([
            prediction(values=[4], dn_eu="EU", bit_mask="0b0111", bit_op="AND", prior_value="1"),
            prediction(values=[29], dn_eu="EU", bit_mask="0x10", bit_op="OR", prior_value=0),
        ])
        expected = [13, 42, 4, 29]
    histories = {"A": [sample(0, 0), sample(13, 130)], "B": [sample(4, 0), sample(5, 42)]}
    original = deepcopy((query, histories))
    scripted = scripted_callback((1, histories))
    contexts = []
    context = object()

    def provider(channels, timeout, lookback, start_time, return_on, *, session=None):
        contexts.append(session)
        return scripted.callback(channels, timeout, lookback, start_time, return_on)

    callback = provider if variant == "identical" else partial(provider, session=context)
    result = steps.verify_wait_telemetry(query, callback, START, TIMEOUT, 7)
    assert_calls(scripted, 1, ["A", "B"], lookback=7)
    assert contexts == ([None] if variant == "identical" else [context])
    assert result["query_matches_predict"] is True
    assert result["telemetry"] == histories
    assert len(result["predict_results"]) == len(query)
    assert len({id(item) for item in result["predict_results"]}) == len(query)
    for item, predict, value in zip(result["predict_results"], query, expected):
        assert_prediction(item, predict, "PASS", value, histories[predict["telem_uuid"]][-1])
    assert (query, histories) == original


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
@pytest.mark.parametrize("initial", [{}, {"A": []}])
def test_no_data_keeps_polling_until_available(scripted_callback, verify_wait, initial):
    query = [prediction(verify_wait=verify_wait)]
    histories = {"A": [sample()]}
    provider = scripted_callback((1, initial), (2, histories))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 2, ["A"])
    assert result["query_matches_predict"] is True
    assert result["telemetry"] == histories
    assert_prediction(result["predict_results"][0], query[0], "PASS", 1, histories["A"][-1])


@pytest.mark.parametrize("verify_value, verify_status", [(2, "PASS"), (8, "FAIL")])
def test_terminal_results_are_retained_by_query_index(scripted_callback, verify_value, verify_status):
    query = [
        prediction(condition="LESS_THAN", values=[5], verify_wait="WAIT"),
        prediction("B", verify_wait="WAIT"),
        prediction(condition="GREATER_THAN", values=[5], verify_wait="WAIT"),
        prediction(values=[verify_value]),
    ]
    early, middle, late, b_sample = sample(2), sample(8), sample(6), sample(1)
    polls = [
        {"A": [early], "B": []},
        {"A": [early, middle]},
        {"A": [early, middle, late], "B": [b_sample]},
    ]
    original = deepcopy((query, polls))
    provider = scripted_callback(*enumerate(polls, start=1))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 3, ["A", "B"])
    assert result["query_matches_predict"] is (verify_status == "PASS")
    assert result["telemetry"] == polls[-1]
    assert len(result["predict_results"]) == 4
    expected = [("PASS", 2, early), ("PASS", 1, b_sample), ("PASS", 8, middle),
                (verify_status, 2, early)]
    for item, predict, (status, value, details) in zip(result["predict_results"], query, expected):
        assert_prediction(item, predict, status, value, details)
    assert (query, polls) == original


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
def test_partial_channels_at_deadline_default_missing_histories_to_empty(scripted_callback, verify_wait):
    query = [prediction(), prediction("B", verify_wait=verify_wait),
             prediction("C", condition="NOT_PRESENT", values=[], verify_wait=verify_wait)]
    histories = {"A": [sample()]}
    provider = scripted_callback((1, histories), (15, histories))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 2, ["A", "B", "C"])
    assert result["query_matches_predict"] is False
    assert result["telemetry"] == {"A": histories["A"], "B": [], "C": []}
    assert len(result["predict_results"]) == 3
    assert_prediction(result["predict_results"][0], query[0], "PASS", 1, histories["A"][-1])
    assert_prediction(result["predict_results"][1], query[1], "FAIL")
    assert_prediction(result["predict_results"][2], query[2], "PASS")


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
def test_not_present_with_data_is_immediately_terminal(scripted_callback, verify_wait):
    query = [prediction(condition="NOT_PRESENT", values=[], verify_wait=verify_wait)]
    histories = {"A": [sample()]}
    provider = scripted_callback((1, histories))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 1, ["A"])
    assert result["query_matches_predict"] is False
    assert_prediction(result["predict_results"][0], query[0], "FAIL", 1, histories["A"][-1])


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
def test_not_present_absence_passes_only_at_deadline(scripted_callback, verify_wait):
    query = [prediction(condition="NOT_PRESENT", values=[], verify_wait=verify_wait)]
    provider = scripted_callback((1, {}), (14.999999, {"A": []}), (15, {}))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 3, ["A"])
    assert result["query_matches_predict"] is True
    assert result["telemetry"] == {"A": []}
    assert_prediction(result["predict_results"][0], query[0], "PASS")


def test_not_present_failure_is_retained_while_histories_refresh(scripted_callback):
    query = [prediction(condition="NOT_PRESENT", values=[], verify_wait="WAIT"),
             prediction("B", verify_wait="WAIT")]
    first = sample()
    final = {"B": [sample()]}
    provider = scripted_callback((1, {"A": [first]}), (2, final))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 2, ["A", "B"])
    assert result["query_matches_predict"] is False
    assert result["telemetry"] == {"A": [], "B": final["B"]}
    assert len(result["predict_results"]) == 2
    assert_prediction(result["predict_results"][0], query[0], "FAIL", 1, first)
    assert_prediction(result["predict_results"][1], query[1], "PASS", 1, final["B"][-1])


@pytest.mark.parametrize(
    "verify_wait, stale_status, values, expected_status",
    [("WAIT", "PASS", [0, 1], "PASS"), ("VERIFY", "FAIL", [1], "PASS"),
     ("VERIFY", "PASS", [0], "FAIL")],
)
def test_input_verification_status_does_not_control_completion(
    scripted_callback, verify_wait, stale_status, values, expected_status,
):
    query = [prediction(verify_wait=verify_wait, verification_status=stale_status)]
    original = deepcopy(query)
    polls = [(index, {"A": [sample(value) for value in values[:index]]})
             for index in range(1, len(values) + 1)]
    provider = scripted_callback(*polls)
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, len(polls), ["A"])
    assert result["query_matches_predict"] is (expected_status == "PASS")
    assert_prediction(result["predict_results"][0], query[0], expected_status,
                      values[-1], polls[-1][1]["A"][-1])
    assert query == original


@pytest.mark.parametrize("elapsed, count", [(14.999999, 2), (15, 1), (15.000001, 1)])
def test_timeout_boundary_is_checked_after_callback(scripted_callback, elapsed, count):
    assert steps._TELEMETRY_QUERY_MARGIN == 5
    query = [prediction(verify_wait="WAIT")]
    polls = [(elapsed, {})]
    if count == 2:
        polls.append((15, {}))
    provider = scripted_callback(*polls)
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT, 200)
    assert_calls(provider, count, ["A"], lookback=200)
    assert result["query_matches_predict"] is False
    assert result["telemetry"] == {"A": []}
    assert_prediction(result["predict_results"][0], query[0], "FAIL")


def test_wait_failed_comparisons_retry_until_deadline(scripted_callback):
    query = [prediction(verify_wait="WAIT")]
    polls = [(1, {"A": [sample(0)]}), (14.999999, {"A": [sample(0), sample(2)]}),
             (15, {"A": [sample(0), sample(2), sample(3)]})]
    provider = scripted_callback(*polls)
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 3, ["A"])
    assert result["query_matches_predict"] is False
    assert result["telemetry"] == polls[-1][1]
    assert_prediction(result["predict_results"][0], query[0], "FAIL", 3, polls[-1][1]["A"][-1])


def test_wait_can_pass_on_callback_that_crosses_deadline(scripted_callback, clock):
    query = [prediction(verify_wait="WAIT")]
    clock.current = START + timedelta(seconds=14)
    histories = {"A": [sample()]}
    provider = scripted_callback((16, histories))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 1, ["A"])
    assert result["query_matches_predict"] is True
    assert_prediction(result["predict_results"][0], query[0], "PASS", 1, histories["A"][-1])


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
@pytest.mark.parametrize("raw, status", [(None, "FAIL"), (1, "PASS"), (0, "FAIL")])
def test_historical_nonempty_query_fetches_once(scripted_callback, clock, verify_wait, raw, status):
    clock.current = START + timedelta(seconds=16)
    query = [prediction(verify_wait=verify_wait)]
    history = [] if raw is None else [sample(raw)]
    provider = scripted_callback((16, {"A": history}))
    result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 1, ["A"])
    assert result["query_matches_predict"] is (status == "PASS")
    assert result["telemetry"] == {"A": history}
    assert_prediction(result["predict_results"][0], query[0], status, raw,
                      history[-1] if history else None)


def test_default_start_time_is_one_captured_utc_origin(scripted_callback):
    query = [prediction("B"), prediction("A", verify_wait="WAIT"), prediction("B")]
    provider = scripted_callback((1, {"B": [sample()]}),
                                 (2, {"B": [sample()], "A": [sample()]}))
    result = steps.verify_wait_telemetry(query, provider.callback, timeout=TIMEOUT, lookback=9)
    assert_calls(provider, 2, ["B", "A"], lookback=9)
    assert all(call[3].tzinfo is timezone.utc for call in provider.calls)
    assert result["query_matches_predict"] is True


def test_empty_query_succeeds_without_callback(clock):
    provider = Mock(side_effect=AssertionError("Empty query must not reach the provider"))
    assert steps.verify_wait_telemetry([], provider, START, TIMEOUT) == {
        "query_matches_predict": True, "predict_results": [], "telemetry": {},
    }
    provider.assert_not_called()


@pytest.mark.parametrize("verify_wait", ["VERIFY", "WAIT"])
@pytest.mark.parametrize("condition, values", [("EQUAL", [1]), ("NOT_PRESENT", [])])
def test_evaluator_error_is_terminal_and_unsuccessful(scripted_callback, verify_wait, condition, values):
    query = [prediction(condition=condition, values=values, verify_wait=verify_wait)]
    error_result = {"telem_uuid": "A", "predict": query[0], "actual_value": None,
                    "verification_status": "ERROR", "data_present": False, "telem_details": None}
    provider = scripted_callback((1, {"A": []}))
    with patch.object(steps, "evaluate_verify_condition", return_value=error_result) as evaluate:
        result = steps.verify_wait_telemetry(query, provider.callback, START, TIMEOUT)
    assert_calls(provider, 1, ["A"])
    evaluate.assert_called_once_with([], query[0], False)
    assert result["query_matches_predict"] is False
    assert result["predict_results"] == [error_result]
    assert result["telemetry"] == {"A": []}


def test_callback_exception_propagates_without_retry(clock):
    error = RuntimeError("provider unavailable")
    provider = Mock(side_effect=error)
    with pytest.raises(RuntimeError) as raised:
        steps.verify_wait_telemetry([prediction()], provider, START, TIMEOUT)
    assert raised.value is error
    provider.assert_called_once_with(["A"], TIMEOUT, 0, START, steps.ReturnOn.ANY)


@pytest.mark.parametrize(
    "overrides, raw, error_type",
    [({"verification_condition": "GREATER_THAN"}, "text", ValueError),
     ({"bit_mask": "0xGG", "bit_op": "AND"}, 1, steps.InputError)],
)
def test_real_evaluator_exceptions_propagate_without_retry(scripted_callback, overrides, raw, error_type):
    provider = scripted_callback((1, {"A": [sample(raw)]}))
    with pytest.raises(error_type):
        steps.verify_wait_telemetry([prediction(**overrides)], provider.callback, START, TIMEOUT)
    assert_calls(provider, 1, ["A"])
