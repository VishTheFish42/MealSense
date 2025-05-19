# dump_menu.py  – output every /getmenu JSON to files in ./menus/
from mitmproxy import http, ctx
from pathlib import Path
import datetime

# Get current date and time
now = datetime.datetime.now()

save_dir = f"menus_{now.strftime('%Y-%m-%d_%H-%M-%S')}"
Path(save_dir).mkdir(exist_ok=True)

def response(flow: http.HTTPFlow):
    if "/getmenu" in flow.request.path or "/getcampuslocations" in flow.request.path and flow.response:
        ts   = flow.response.timestamp_end
        host = flow.request.host.replace(":", "_")
        fname = Path(save_dir) / f"{host}_{ts:.0f}.json"
        try:
            fname.write_bytes(flow.response.content)
            ctx.log.info(f"saved {fname}")
        except Exception as e:
            ctx.log.warn(f"could not write {fname}: {e}")
