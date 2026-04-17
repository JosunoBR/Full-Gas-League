## Plan: Fix PythonAnywhere import and site errors

TL;DR: Fix the undefined `all_seasons` reference in `app/routes/admin.py`, ensure upload folder creation runs under WSGI in `run.py`, and remove/save `app/routes/public.py` without BOM encoding so PythonAnywhere can import it.

**Steps**
1. Update `app/routes/admin.py` in `data_health()` to define `all_seasons = Season.query.order_by(Season.id.desc()).all()` before use. Use the existing fallback logic.
2. Update `run.py` so upload folder initialization runs on import/WSGI startup, not only inside `if __name__ == '__main__'`.
   - Add a directory creation step for `app.config['UPLOAD_FOLDER']` immediately after app config is loaded.
3. Clean `app/routes/public.py` to remove any BOM/hidden leading character and save it as UTF-8 without BOM.
4. Verify the fix by compiling/importing the modified files and reloading the application.

**Verification**
1. Run `python -m py_compile app/routes/admin.py app/routes/public.py run.py`.
2. Confirm `app/routes/public.py` has no BOM by checking its first bytes or re-saving with UTF-8 no BOM.
3. Start the app locally or reload PythonAnywhere and confirm the WSGI imports without error.
4. If available, run targeted tests for page rendering or upload behavior.

**Decisions**
- Keep the fix small and targeted to the bug sources seen in the log.
- Prefer a WSGI-safe startup path for upload folder creation rather than relying on `__main__` execution.

**Further Considerations**
1. If the PythonAnywhere environment still reports `OSError: write error`, check `UPLOAD_FOLDER` permissions and existence after deployment.
2. If there are still missing uploads, add a helper to ensure the directory exists before each `file.save()` call.
