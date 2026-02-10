# Quick Reference

## 🚀 Most Common Commands

### Coverage Testing
```bash
# Run tests with coverage
cd serp-to-context-api
pytest tests/ --cov=app --cov-report=term-missing

# HTML report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Specific test
pytest tests/test_routes.py -v
```

### Security Scanning
```bash
# Code security
bandit -r app -v

# Dependencies
safety check

# Both with reports
bandit -r app -f json -o bandit.json
safety check --json > safety.json
```

### Quick Status
```bash
# Run everything (no coverage threshold)
pytest tests/ -v

# Fast smoke test
pytest tests/test_routes.py tests/test_schemas.py -v
```

---

## 📊 Current Status

| Metric | Value | Target |
|--------|-------|--------|
| Coverage | 78% | 72% ✅ |
| Tests | 107 | 75+ ✅ |
| Security | ✅ Pass | - |

---

## 📁 Documentation Map

- **COVERAGE.md** - Detailed coverage report (all modules, timeline, recommendations)
- **SECURITY.md** - Security scanning guide (Bandit, Safety, local testing)
- **INDEX.md** - Full documentation index (all resources)
- **QUICK_REF.md** - This file (most common tasks)

---

## 🔗 Key Files

```
.github/workflows/ci.yml      ← GitHub Actions workflow
.bandit                        ← Bandit config
serp-to-context-api/
  ├── app/                     ← Application code (790 LOC)
  ├── tests/                   ← Test suite (107 tests)
  └── requirements.txt         ← Dependencies
```

---

## ✅ Quality Gates

- ✅ **Coverage**: 78% (target 72%)
- ✅ **Tests**: 107 passing
- ✅ **Security**: Bandit + Safety passing
- ✅ **Linting**: Flake8 passing

---

## 🆘 Troubleshooting

### Tests failing?
```bash
# Install dependencies
pip install -r requirements.txt

# Run with verbose output
pytest tests/ -vv --tb=short

# Check specific module
pytest tests/test_routes.py -v
```

### Coverage report not generating?
```bash
# Make sure pytest-cov is installed
pip install pytest-cov

# Try with explicit paths
pytest serp-to-context-api/tests/ --cov=serp-to-context-api/app
```

### Security tools not found?
```bash
pip install bandit safety
```

---

## 📈 Metrics at a Glance

```
Total Statements:        583
Covered:                 457 (78%)
Missed:                  126 (22%)

Modules at 100%:         5 (routes, schemas, cache, embeddings, repository)
Modules at 90%+:         2 (formatter, worker)
Modules at 70%+:         2 (database, parser)
Modules < 70%:          1 (scraper)

Tests:                   107
  - Passing:             107 ✅
  - Skipped:             3
  - Failing:             0

Execution Time:          ~24.5 seconds
```

---

## 🔐 Security Summary

**Bandit** (Code Scanning)
- Lines scanned: 790
- Issues found: 1 (false positive)
- No hardcoded secrets ✅
- No SQL injection ✅

**Safety** (Dependencies)
- Packages scanned: 450
- Your CVEs: 0 ✅
- System CVEs: 20 (not your code)

---

## 🎯 Next Steps

1. **Before Committing**
   ```bash
   pytest tests/ --cov=app --cov-report=term-missing
   bandit -r app -v
   safety check
   ```

2. **After Pushing**
   - Check GitHub Actions for CI results
   - Download security reports if needed
   - Merge when all checks pass ✅

3. **For Issues**
   - Review COVERAGE.md or SECURITY.md
   - Check GitHub Actions logs
   - Run local commands to debug

---

## 📞 Getting Help

| Topic | Location |
|-------|----------|
| Coverage details | COVERAGE.md |
| Security info | SECURITY.md |
| All docs | INDEX.md |
| Commands | This file |

---

**Last Updated**: February 10, 2026  
**Coverage**: 78% | **Tests**: 107 ✅ | **Security**: ✅ Passed
