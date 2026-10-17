"""Loopback-only preview under a project subpath, just like GitHub Pages."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
from urllib.request import urlopen
from pathlib import Path
import argparse
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8766/economic-note/'


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'site'),**kwargs)
    def do_GET(self):
        path=urlsplit(self.path).path
        if not path.startswith('/economic-note/') or '..' in unquote(path).split('/'):
            self.send_error(404);return
        self.path=self.path[len('/economic-note'):]
        super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def log_message(self,*args):pass


def available():
    try:
        with urlopen(URL+'release.json',timeout=2) as response:r=json.load(response)
        return r.get('format')==1 and bool(r.get('revision'))
    except Exception:return False


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--open',action='store_true');args=p.parse_args()
    if args.open:
        if not available():
            private=ROOT/'.private';private.mkdir(exist_ok=True)
            with (private/'preview.log').open('a') as log:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve())],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            (private/'preview.pid').write_text(str(proc.pid))
            for _ in range(40):
                if available():break
                if proc.poll() is not None:raise RuntimeError('プレビュー起動失敗。別のプログラムが8766番を使用していないか確認してください。')
                time.sleep(.25)
            else:raise RuntimeError('プレビューの起動を確認できません。')
        subprocess.run(['open',URL],check=True)
    else:
        server=ThreadingHTTPServer(('127.0.0.1',8766),Handler)
        print(URL,flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
