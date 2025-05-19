# dump_menu.py  – output every /getmenu JSON to files in ./menus/
from mitmproxy import http, ctx
from pathlib import Path; Path("menus").mkdir(exist_ok=True)

def response(flow: http.HTTPFlow):
    if "/getmenu" in flow.request.path and flow.response:
        ts   = flow.response.timestamp_end
        host = flow.request.host.replace(":", "_")
        fname = Path("menus") / f"{host}_{ts:.0f}.json"
        try:
            fname.write_bytes(flow.response.content)
            ctx.log.info(f"saved {fname}")
        except Exception as e:
            ctx.log.warn(f"could not write {fname}: {e}")
