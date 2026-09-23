# Redis configuration fixture
This is intentionally broken, synthetic evaluation data, not a production outage.
The API and Redis run in separate Compose containers. The service hostname is
`redis`; `localhost` refers to the API's own container. An explicit host override
must still work. Fix the default configuration without changing the tests.

`app.py` is an optional FastAPI demonstration. The tests exercise the configuration
function without a running Redis instance. Do not interpret this as a live Docker
health-check experiment.
