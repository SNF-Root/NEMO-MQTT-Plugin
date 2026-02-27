# Packaging Compliance: Python Packaging User Guide

Comparison of `nemo-mqtt-plugin` against the [Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/).

---

## Implementation Status (Completed)

All suggested changes have been implemented:

- ✅ Added `license-files = ["LICEN[CS]E*"]` to `pyproject.toml`
- ✅ License: using `license` + `license-files` (PEP 639); License classifier omitted (superseded by license expression)
- ✅ Updated README build instructions to use `python -m build`
- ✅ Bumped `setuptools>=77.0.3` in `[build-system]`
- ✅ Removed `setup.py` (pyproject.toml is sole source of truth)
- ✅ Removed `requirements.txt` (pyproject.toml is source of truth; use `pip install -e .[dev]` for development)
- ✅ Added `Issues` to `[project.urls]`
- ✅ Updated MANIFEST.in (removed requirements.txt)
- ✅ Updated CI workflow cache key to use `pyproject.toml`
- ✅ **Src layout:** Package moved to `src/nemo_mqtt/`; `pyproject.toml` uses `[tool.setuptools.packages.find]` with `where = ["src"]`; MANIFEST.in, CI, README, and run_tests.py updated for src paths.

---

## Summary

| Area | Status | Notes |
|------|--------|-------|
| Project structure | ✅ Done | Uses src layout: `src/nemo_mqtt/` |
| pyproject.toml | ✅ Done | Present, comprehensive, compliant |
| Build system | ✅ Done | setuptools>=77.0.3 |
| Metadata | ✅ Done | license-files, license expression (PEP 639), Issues URL |
| LICENSE | ✅ Good | MIT license present |
| README.md | ✅ Done | Build instructions updated |
| tests/ | ✅ Good | Present with tests |
| setup.py | ✅ Done | Removed |
| requirements.txt | ✅ Done | Removed; pyproject.toml is source of truth |
| Build command | ✅ Done | README uses `python -m build` |

---

## 1. Project Layout

**Tutorial recommendation:** Use the `src/` layout:

```
packaging_tutorial/
└── src/
    └── example_package_YOUR_USERNAME_HERE/
        ├── __init__.py
        └── example.py
```

**Current layout:** src layout (package under `src/`):

```
nemo-mqtt-plugin/
└── src/
    └── nemo_mqtt/
        ├── __init__.py
        └── ...
```

**Suggested change:** The src layout reduces accidental imports of development code and is recommended by the guide.

**Status:** ✅ Implemented. Package moved to `src/nemo_mqtt/`; `pyproject.toml` uses `[tool.setuptools.packages.find]` with `where = ["src"]`.

---

## 2. Build System (pyproject.toml)

**Status:** ✅ Implemented.

**Current:** `setuptools>=77.0.3` with wheel. Ensures PEP 639 license-files support.

---

## 3. Metadata: license-files

**Status:** ✅ Implemented.

**Current:** `license = "MIT"` and `license-files = ["LICEN[CS]E*"]` in `pyproject.toml`. LICENSE is explicitly included per [PEP 639](https://peps.python.org/pep-0639/).

---

## 4. Metadata: License Classifier

**Status:** N/A (PEP 639).

With PEP 639, the `license` and `license-files` fields in `pyproject.toml` supersede the License classifier. Setuptools 77+ raises an error if both are used. The project correctly uses `license = "MIT"` and `license-files` only.

---

## 5. Project URLs

**Status:** ✅ Implemented.

**Current:** `Issues = "https://github.com/SNF-Root/NEMO-MQTT-Plugin/issues"` in `[project.urls]`.

---

## 6. setup.py Redundancy

**Status:** ✅ Implemented.

**Current:** `setup.py` removed. `pyproject.toml` is the sole source of truth for build configuration.

---

## 7. Build Command

**Status:** ✅ Implemented.

**Current:** README uses `pip install build` and `python -m build` for building.

---

## 8. requirements.txt vs pyproject.toml

**Status:** ✅ Implemented.

**Current:** `requirements.txt` removed. `pyproject.toml` is the source of truth. Use `pip install -e .[dev]` for development. CI cache key updated to use `pyproject.toml`.

---

## 9. MANIFEST.in

**Tutorial:** With `pyproject.toml` and setuptools, many files are included automatically. `license-files` in `pyproject.toml` handles LICENSE.

**Current:** `MANIFEST.in` explicitly includes LICENSE, README, etc. This is fine and can help with sdist contents.

**Suggested change:** No change needed. Keep `MANIFEST.in` for explicit control. Ensure it doesn't conflict with `license-files` once added.

**Priority:** N/A.

---

## 10. Checklist: What Matches the Tutorial

- ✅ `pyproject.toml` present with `[build-system]` and `[project]`
- ✅ `name`, `version`, `description`, `readme`, `authors`
- ✅ `requires-python`
- ✅ `classifiers` (Python versions, OS, etc.)
- ✅ `license` (MIT)
- ✅ `dependencies`
- ✅ `[project.urls]`
- ✅ `LICENSE` file (MIT)
- ✅ `README.md`
- ✅ `tests/` directory
- ✅ `__init__.py` in package
- ✅ Entry points (`[project.scripts]`)

---

## Quick Action List

| Priority | Action | Status |
|----------|--------|--------|
| High | Add `license-files = ["LICEN[CS]E*"]` to `pyproject.toml` | ✅ Done |
| High | License metadata | ✅ Done (PEP 639: license + license-files; classifier omitted) |
| High | Update README build instructions to use `python -m build` | ✅ Done |
| Medium | Bump `setuptools>=77.0.3` in `[build-system]` | ✅ Done |
| Medium | Remove or minimize `setup.py` | ✅ Done |
| Medium | Align `requirements.txt` with `pyproject.toml` or remove | ✅ Done |
| Low | Consider migrating to src layout | ✅ Done |
| Low | Add `Issues` to `[project.urls]` | ✅ Done |

---

## References

- [Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [How to modernize a setup.py based project?](https://packaging.python.org/en/latest/guides/how-to-modernize-setup-py/)
