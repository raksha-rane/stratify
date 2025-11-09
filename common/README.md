# Common Utilities Module

Shared utilities and components used across all AQTS services.

## Modules

### `logger.py` - Structured Logging

Production-grade logging system with JSON/pretty formatting, log rotation, and correlation ID tracking.

**Quick Start:**
```python
from common.logger import get_logger, set_correlation_id

logger = get_logger(__name__, service_name='my-service')
logger.info("Operation started", extra={'user_id': 123})
```

**Features:**
- JSON and pretty-print formatters
- Automatic log rotation (10MB, 5 backups)
- Correlation ID for request tracing
- Performance timing decorators
- Sensitive data masking
- Environment-based configuration

**See:** [TASK1_SUMMARY.md](../TASK1_SUMMARY.md) for full documentation

---

## Installation

The common module is included in each service's Docker image. To use locally:

```python
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.logger import get_logger
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FORMAT` | pretty | Output format (json, pretty) |
| `LOG_SERVICE_NAME` | Module name | Service identifier |
| `LOG_FILE` | None | Optional log file path |

---

## Testing

```bash
python -m pytest tests/test_logger.py -v
```

---

## Future Modules

- `error_handlers.py` - TASK 2 (Error handling middleware)
- `health.py` - TASK 3 (Health check utilities)
- `rate_limiter.py` - TASK 5 (Rate limiting)
- `metrics.py` - TASK 6 (Prometheus metrics)
