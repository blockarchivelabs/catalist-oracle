from prometheus_client import Gauge

from src.variables import PROMETHEUS_PREFIX


ALL_VALIDATORS = Gauge(
    "all_validators",
    "All validators",
    namespace=PROMETHEUS_PREFIX,
)

CATALIST_VALIDATORS = Gauge(
    "catalist_validators",
    "Catalist validators",
    namespace=PROMETHEUS_PREFIX,
)

ALL_SLASHED_VALIDATORS = Gauge(
    "all_slashed_validators",
    "All slashed validators",
    namespace=PROMETHEUS_PREFIX,
)

CATALIST_SLASHED_VALIDATORS = Gauge(
    "catalist_slashed_validators",
    "Catalist slashed validators",
    namespace=PROMETHEUS_PREFIX,
)
