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
5. Review notes to lead with: approval gate on by default, full audit log,
   docs/PRIVACY.md, no pip dependencies, no telemetry.
