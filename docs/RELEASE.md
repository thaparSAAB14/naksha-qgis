# Releasing to plugins.qgis.org

1. Bump `version=` in `naksha/metadata.txt` (+ changelog entry).
2. Run the gauntlet: `& "C:\Program Files\QGIS 3.40.13\bin\python-qgis-ltr.bat" tests\test_smoke.py`
3. Build the zip (from the repo root):

   ```powershell
   .\scripts\build_zip.ps1
   ```

4. Upload `dist\naksha-<version>.zip` at https://plugins.qgis.org/plugins/add/
   (needs an OSGeo ID; first upload creates the plugin page, later ones update it).
   Keep `experimental=True` until the trust loop has real-world mileage.
5. Review notes to lead with: **no `exec`/`eval` and no code-execution tool**, approval gate
   on by default, full audit log, docs/PRIVACY.md, no pip dependencies, no telemetry.

## Security scan (run before every upload)

plugins.qgis.org scans with bandit + detect-secrets; several rules are **not waivable**,
so a finding means rejection, not a warning. Reproduce the scan locally:

```bash
uvx bandit -r naksha/ && uvx detect-secrets scan naksha/ && uvx ruff check naksha/ --select F821,F823,F403
```

Last run: **0 bandit findings across 1729 lines, 0 secrets, ruff clean.** Keep it there —
in particular never reintroduce `exec`/`eval` (B102/B307), `subprocess` with a shell
(B602/B605), `try/except: pass` (B110/B112), or `verify=False` (B501). Check the built ZIP
carries no `.bat`/`.exe`/`.so` and no `__pycache__`.
