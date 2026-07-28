"""Entrypoint wrapper (v4.6) — Community Cloud's platform reboots
have been observed re-selecting the conventional entrypoint name,
which bypassed app.py's grouped navigation (28-Jul incident). This
file satisfies the convention and routes straight into the router.
"""
import runpy

runpy.run_path("app.py", run_name="__main__")
