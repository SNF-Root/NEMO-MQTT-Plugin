# Final Polish Checklist Before Shipping

Recommendations for preparing the NEMO MQTT Plugin as a production-ready Python package.

---

## 1. Documentation & References to Non-Existent Files

### CHANGELOG.md
- **MANIFEST.in** includes `CHANGELOG.md` but the file does not exist.
- **Action**: Create a minimal `CHANGELOG.md` or remove it from MANIFEST.in.
- **Recommendation**: Create it—PyPI and users expect a changelog. Start with:
  ```markdown
  # Changelog
  ## [1.0.0] - YYYY-MM-DD
  - Initial release
  ```

### install_standalone.py
- **README.md** (line 13) mentions "One-command installation with `install_standalone.py`".
- **.gitignore** excludes `install_standalone.py`.
- **Action**: Remove the reference from README or add the script. The README already documents `setup_nemo_integration` and `install_mqtt_plugin`—remove the `install_standalone.py` mention.

### dev_reinstall.sh
- **README.md** (lines 1039–1040) references `scripts/dev_reinstall.sh`.
- **.gitignore** excludes it.
- **Action**: Remove this reference from README; the script does not exist in the repo.

---

## 2. Development-Only Scripts: Exclude from Package

The `scripts/` directory contains tools that require a NEMO project context (Django settings, manage.py). They should **not** be shipped in the PyPI package.

| Script | Purpose | Recommendation |
|--------|---------|----------------|
| `scripts/debug_hmac.py` | HMAC config verification | Keep in repo, **exclude from package** |
| `scripts/check_bridge_status.py` | Bridge diagnostics | Keep in repo, **exclude from package** |
| `scripts/monitor_services.sh` | Service monitoring/restart | Dev/ops only—keep in repo, exclude |
| `scripts/cleanup_mqtt.sh` | Kill bridge, remove lock | Dev/ops only—keep in repo, exclude |
| `scripts/lint.sh` | Run flake8/mypy | Dev only—exclude |
| `scripts/format.sh` | Run black/isort | Dev only—exclude |
| `scripts/test.sh` | Run pytest | Dev only—exclude |
| `scripts/clean.sh` | Clean build artifacts | Dev only—exclude |

**Action**: Ensure `MANIFEST.in` and `pyproject.toml` do **not** include `scripts/`. The package should only contain `nemo_mqtt/`, `tests/` (if desired), and top-level config files. The egg-info SOURCES.txt currently lists `scripts/check_bridge_status.py` and `scripts/debug_hmac.py`—verify your build config so these are not packaged.

---

## 3. TLS/SSL References (Historical Only)

TLS was removed in migration `0007_replace_tls_with_hmac`. Remaining references are:

- **Migrations** (0001–0007): Historical; leave as-is for migration chain.
- **`nemo_mqtt/bridge/auto_services.py`** (line 63): Comment "plain TCP, no TLS"—accurate, keep.
- **`nemo_mqtt/bridge/mqtt_connection.py`** (line 21): Comment "plain TCP, no TLS"—accurate, keep.

**Action**: No code changes. The migration history correctly documents the TLS→HMAC transition.

---

## 4. Security: Sensitive Data in Terminal Output

**`nemo_mqtt/customization.py`** (lines 9–37):

`_print_config_to_terminal()` prints the full config to stdout on every save, including:
- `config.password` (broker password)
- `config.hmac_secret_key`

The `broker_password` and `hmac_key_set` parameters are passed but never used to mask values.

**Action**: Mask sensitive fields before printing:

```python
def _print_config_to_terminal(config, broker_password=False, hmac_key_set=False):
    """Print current MQTT configuration to stdout (sensitive values masked)."""
    pwd_display = "***" if config.password else "(not set)"
    hmac_display = "***" if config.hmac_secret_key else "(not set)"
    lines = [
        "",
        "--- MQTT configuration saved ---",
        # ...
        f"  password: {pwd_display}",
        # ...
        f"  hmac_secret_key: {hmac_display}",
        # ...
    ]
```

---

## 5. Settings Module for Standalone Scripts

Several scripts use `settings_dev`:

- `scripts/debug_hmac.py`: `settings_dev`
- `scripts/check_bridge_status.py`: `settings`
- `nemo_mqtt/monitoring/redis_checker.py`: `settings_dev`
- `nemo_mqtt/monitoring/mqtt_monitor.py`: `settings_dev`
- `nemo_mqtt/redis_mqtt_bridge.py`: `settings_dev` (when run as `__main__`)

NEMO projects may use `settings.py`, `settings_dev.py`, or custom names.

**Action**: Document in README and script docstrings that these must be run from the NEMO project root and that `DJANGO_SETTINGS_MODULE` must point to the project’s settings (e.g. `export DJANGO_SETTINGS_MODULE=settings` or `settings_dev`). Consider trying `settings` first, then `settings_dev`, as a fallback in the bridge when run standalone.

---

## 6. .gitignore vs. Tests

`.gitignore` includes:

```
test_*.py
*_test.py
simple_test.py
test_flow.py
test_message_flow.py
test_monitor_*.py
test_direct_mqtt.py
test_api.py
```

These patterns match files under `tests/` (e.g. `tests/test_signals.py`). If those files are already tracked, they stay tracked, but new test files could be ignored.

**Action**: Narrow the patterns so they do not affect `tests/`:

```
# Root-level or stray test files only
/test_*.py
/*_test.py
/simple_test.py
```

Or explicitly allow tests:

```
!tests/
```

---

## 7. Outdated Paths in monitoring/README.md

`nemo_mqtt/monitoring/README.md` uses old paths:

- Line 42: `python3 NEMO/plugins/mqtt/monitoring/mqtt_monitor.py` (plugin layout)
- Line 51: `python3 NEMO/plugins/mqtt/monitoring/redis_checker.py`
- Line 60: `python3 NEMO/plugins/mqtt/monitoring/../test_mqtt.py`
- Line 111: `./monitor_mqtt.sh mqtt` (script does not exist)

**Action**: Update to the current layout, e.g.:

```bash
# From NEMO project root (with nemo_mqtt installed)
python -m nemo_mqtt.monitoring.mqtt_monitor
python -m nemo_mqtt.monitoring.redis_checker
python manage.py test_mqtt_api
```

Remove or correct the `monitor_mqtt.sh` reference.

---

## 8. Duplicate Build Configuration

**Done**: `setup.py` has been removed. `pyproject.toml` is the single source of truth for build configuration.

---

## 9. run_tests.py

`run_tests.py` at the project root is a thin wrapper around pytest. It is useful for development.

**Action**: Keep it; it does not need to be in the package. Ensure MANIFEST.in does not include it if you want to avoid shipping it.

---

## 10. monitoring/run_monitor.py

`run_monitor.py` expects `manage.py` in the current directory (line 85). It is a dev/debug helper.

**Action**: Keep in the package (it’s under `nemo_mqtt/`) but document that it must be run from the NEMO project root. The `package_data` in pyproject.toml already includes `nemo_mqtt/**`, so it will be installed.

---

## 11. admin.py: Bare except

**`nemo_mqtt/admin.py`** (line 62):

```python
except:
    return "Unknown"
```

**Action**: Use `except Exception:` to avoid catching `KeyboardInterrupt` and `SystemExit`.

---

## 12. Optional: Classifier Update

**Done**: `pyproject.toml` uses `Development Status :: 5 - Production/Stable`.

---

## Summary: Priority Order

| Priority | Item | Effort |
|----------|------|--------|
| High | Mask password/HMAC in `_print_config_to_terminal` | Small |
| High | Fix admin.py bare `except` | Trivial |
| High | Create CHANGELOG.md or remove from MANIFEST.in | Small |
| Medium | Remove `install_standalone.py` and `dev_reinstall.sh` refs from README | Trivial |
| Medium | Exclude `scripts/` from the built package | Small |
| Medium | Update monitoring/README.md paths | Small |
| Low | Refine .gitignore for tests | Trivial |
| Low | Document DJANGO_SETTINGS_MODULE for scripts | Small |
| Low | Update classifier to Production/Stable | Trivial |
