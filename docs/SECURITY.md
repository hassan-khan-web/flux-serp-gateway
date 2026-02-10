# Security Scanning Guide

## Overview

Your CI/CD pipeline now includes two security scanning tools to detect vulnerabilities and security issues:

### 1. **Bandit** - Code Security Scanner
Bandit analyzes your Python code for common security vulnerabilities.

**What it checks:**
- Hardcoded passwords/secrets (B105, B106, B107)
- SQL injection risks (B608, B609)
- Insecure cryptography (B303, B304)
- Unsafe file operations (B603, B605)
- Command injection (B602, B607)
- Debug mode enabled (B601)
- Use of dangerous functions (exec, eval, pickle)
- Weak random number generation (B311, B312)

**Security Issue Codes:**
- B2xx - Flask/Django security issues
- B3xx - Insecure deserialization (pickle, marshal, yaml)
- B4xx - Django/Werkzeug issues
- B5xx - Crypto issues
- B6xx - Hardcoded passwords, command injection
- B7xx - SQL injection, temporary file permissions

### 2. **Safety** - Dependency Vulnerability Scanner
Safety checks all your installed Python packages against a database of known CVEs.

**What it does:**
- Scans requirements.txt and installed packages
- Compares versions against PyUp.io CVE database
- Alerts if packages have known security vulnerabilities
- Helps prevent supply chain attacks
- Shows vulnerability severity and fixes

## Running Locally

### Install Tools
```bash
pip install bandit safety
```

### Run Bandit (Code Security)
```bash
# Scan entire app directory
bandit -r serp-to-context-api/app -v

# Generate JSON report
bandit -r serp-to-context-api/app -f json -o bandit-report.json

# Exclude specific files
bandit -r serp-to-context-api/app --exclude /tests/

# Check specific severity levels
bandit -r serp-to-context-api/app -ll  # Only MEDIUM and HIGH
```

### Run Safety (Dependency Check)
```bash
# Check installed packages
safety check

# Generate JSON report
safety check --json > safety-report.json

# Check specific file
safety check -r requirements.txt

# Full report with all details
safety check --full-report
```

## CI/CD Integration

In your GitHub Actions workflow (`.github/workflows/ci.yml`):

1. **Bandit** runs after flake8 linting
   - Scans `serp-to-context-api/app` directory
   - Outputs JSON report and verbose summary
   - Does NOT block build (continue-on-error: true)

2. **Safety** runs after Bandit
   - Checks all installed dependencies
   - Outputs JSON report and summary
   - Does NOT block build (continue-on-error: true)

3. Both reports are uploaded as artifacts
   - View in GitHub: Actions > [Run] > Artifacts
   - Download for local analysis

## Understanding Reports

### Bandit JSON Report
```json
{
  "results": [
    {
      "test_id": "B105",
      "severity": "HIGH",
      "issue_text": "Possible hardcoded password",
      "filename": "app/services/api.py",
      "line_number": 42
    }
  ]
}
```

### Safety JSON Report
```json
[
  {
    "vulnerability": "...",
    "v": "<1.2.0",
    "specs": ["requests<1.2.0"],
    "advisory": "Security issue in requests library",
    "cve": "CVE-2021-12345"
  }
]
```

## Handling Issues

### If Bandit Finds Issues:

1. **Review the issue** - Does it apply to your code?
2. **Fix it** - Most are legitimate security concerns
3. **Suppress if needed** (last resort):
   ```python
   import requests  # nosec B101 - harmless in this context
   ```

### If Safety Finds Vulnerable Dependencies:

1. **Update the package**:
   ```bash
   pip install --upgrade package-name
   ```

2. **Check for breaking changes** in the package
3. **Update requirements.txt** and test thoroughly
4. **If update not available** - evaluate risk vs benefit

## Configuration

- **Bandit config**: `.bandit` (JSON format)
  - Customize excluded directories
  - Enable/disable specific tests

- **Safety config**: Uses PyUp.io database (checked in CI)

## Next Steps

Monitor the security reports in:
1. GitHub Actions artifacts after each push/PR
2. JSON files provide machine-readable data
3. Fix HIGH/CRITICAL issues before merge
4. Track trends over time

---

**Note**: These scans help prevent security issues but aren't 100% foolproof. Always do code reviews and keep dependencies updated!
