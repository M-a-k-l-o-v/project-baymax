"""Test fakes for BAYMAX.

`FakeBackend` implements `InferenceBackend` with canned responses and
injectable failure modes. Registered under the "fake" key in tests that
spin up the full FastAPI app; used directly in unit tests of the agent
loop and retry logic per ADR 0011 §F1 / §F4.
"""
