"""
Mission 136: EventBus.publish() is a synchronous, post-commit
observation mechanism — every real publisher in this repo calls it only
after its own mutation/persistence has already succeeded (see
MISSION_136.md §4.2). A subscriber's exception is therefore caught and
logged individually, never re-raised: every other subscriber for the
same event is still attempted, and the caller's already-successful
operation is never turned into an apparent failure (§4.3 documents the
concrete duplicate-mutation risk this prevents). No Qt/Manager wiring is
needed to prove this contract — an isolated EventBus is sufficient.
"""

import unittest

from src.core.event_bus import EventBus


class EventBusFaultIsolationTest(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus()

    def test_all_subscribers_are_called_once_in_registration_order(self):
        calls = []
        self.bus.subscribe("evt", lambda payload: calls.append(("a", payload)))
        self.bus.subscribe("evt", lambda payload: calls.append(("b", payload)))
        self.bus.subscribe("evt", lambda payload: calls.append(("c", payload)))

        self.bus.publish("evt", {"x": 1})

        self.assertEqual([name for name, _ in calls], ["a", "b", "c"])
        self.assertTrue(all(payload["x"] == 1 for _, payload in calls))

    def test_a_failing_intermediate_subscriber_does_not_block_the_others(self):
        calls = []

        def subscriber_a(payload):
            calls.append("a")

        def subscriber_b_fails(payload):
            calls.append("b")
            raise ValueError("boom")

        def subscriber_c(payload):
            calls.append("c")

        self.bus.subscribe("evt", subscriber_a)
        self.bus.subscribe("evt", subscriber_b_fails)
        self.bus.subscribe("evt", subscriber_c)

        with self.assertLogs("src.core.event_bus", level="ERROR"):
            result = self.bus.publish("evt")

        self.assertEqual(calls, ["a", "b", "c"])
        self.assertIsNone(result)

    def test_failure_is_logged_with_event_name_callback_and_traceback_but_not_the_payload(self):
        def failing_subscriber(payload):
            raise ValueError("boom")

        self.bus.subscribe("workspace.saved", failing_subscriber)

        with self.assertLogs("src.core.event_bus", level="ERROR") as captured:
            self.bus.publish("workspace.saved", {"secret": "should-not-appear"})

        self.assertEqual(len(captured.records), 1)
        record = captured.records[0]
        message = record.getMessage()

        self.assertIn("workspace.saved", message)
        self.assertIn("failing_subscriber", message)
        self.assertIsNotNone(record.exc_info)
        self.assertIs(record.exc_info[0], ValueError)

        full_output = "\n".join(captured.output)
        self.assertNotIn("should-not-appear", full_output)

    def test_multiple_failures_are_all_logged_and_all_subscribers_are_attempted(self):
        calls = []

        def a_fails(payload):
            calls.append("a")
            raise ValueError("a failed")

        def b_ok(payload):
            calls.append("b")

        def c_fails(payload):
            calls.append("c")
            raise RuntimeError("c failed")

        def d_ok(payload):
            calls.append("d")

        for callback in (a_fails, b_ok, c_fails, d_ok):
            self.bus.subscribe("evt", callback)

        with self.assertLogs("src.core.event_bus", level="ERROR") as captured:
            result = self.bus.publish("evt")

        self.assertEqual(calls, ["a", "b", "c", "d"])
        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 2)
        exception_types = {record.exc_info[0] for record in captured.records}
        self.assertEqual(exception_types, {ValueError, RuntimeError})

    def test_subscribing_during_fan_out_does_not_affect_the_current_publish(self):
        calls = []

        def late_subscriber(payload):
            calls.append("late")

        def subscriber_that_subscribes_more(payload):
            calls.append("first")
            self.bus.subscribe("evt", late_subscriber)

        self.bus.subscribe("evt", subscriber_that_subscribes_more)

        self.bus.publish("evt")
        self.assertEqual(calls, ["first"])

        self.bus.publish("evt")
        self.assertEqual(calls, ["first", "first", "late"])

    def test_freeze_still_makes_dict_payloads_read_only_and_isolated(self):
        received = {}

        def subscriber(payload):
            received["payload"] = payload

        self.bus.subscribe("evt", subscriber)

        original = {"nested": [1, 2, 3]}
        self.bus.publish("evt", original)

        frozen = received["payload"]

        with self.assertRaises(TypeError):
            frozen["nested"] = "mutated"

        frozen["nested"].append(4)
        self.assertEqual(original["nested"], [1, 2, 3])

    def test_nested_publish_during_a_subscriber_completes_and_outer_fan_out_continues(self):
        calls = []

        def outer_first(payload):
            calls.append("outer_first")

        def outer_second_publishes_nested_event(payload):
            calls.append("outer_second_start")
            self.bus.publish("nested_evt")
            calls.append("outer_second_end")

        def nested_subscriber_fails(payload):
            calls.append("nested_fail")
            raise ValueError("nested boom")

        def outer_third(payload):
            calls.append("outer_third")

        self.bus.subscribe("nested_evt", nested_subscriber_fails)
        self.bus.subscribe("outer_evt", outer_first)
        self.bus.subscribe("outer_evt", outer_second_publishes_nested_event)
        self.bus.subscribe("outer_evt", outer_third)

        with self.assertLogs("src.core.event_bus", level="ERROR"):
            self.bus.publish("outer_evt")

        self.assertEqual(
            calls,
            ["outer_first", "outer_second_start", "nested_fail", "outer_second_end", "outer_third"],
        )

    def test_a_successful_operation_is_never_reported_as_failed_because_a_subscriber_raised(self):
        """
        Mission 136 §4.3: locks the architectural decision against a
        future reintroduction of aggregate+raise. Minimal harness
        mirroring the real shape of every publisher in the repo (e.g.
        CharacterManager.create()): mutate, persist (simulated), publish()
        as the very last step, then return success — a subscriber's
        failure must never turn that already-real success into an
        apparent one.
        """
        subscriber_calls = []

        def observer_ok(payload):
            subscriber_calls.append("observer_ok")

        def observer_fails(payload):
            subscriber_calls.append("observer_fails")
            raise RuntimeError("refresh crashed")

        self.bus.subscribe("character.created", observer_ok)
        self.bus.subscribe("character.created", observer_fails)

        def create_character_like_operation():
            # Mutation + persistence already succeeded by this point in
            # every real publisher (MISSION_136.md §4.2/§4.3).
            persisted = True
            self.bus.publish("character.created", {"character_id": "abc"})
            return persisted

        with self.assertLogs("src.core.event_bus", level="ERROR"):
            result = create_character_like_operation()

        self.assertTrue(result)
        self.assertEqual(subscriber_calls, ["observer_ok", "observer_fails"])

    def test_describing_a_callback_without_a_qualname_falls_back_to_repr_without_crashing(self):
        class ObserverWithoutQualname:
            def __call__(self, payload):
                raise ValueError("callable object failed")

        observer = ObserverWithoutQualname()
        self.bus.subscribe("evt", observer)

        with self.assertLogs("src.core.event_bus", level="ERROR") as captured:
            result = self.bus.publish("evt")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)


if __name__ == "__main__":
    unittest.main()
