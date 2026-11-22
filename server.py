# -*- coding: utf-8 -*-
"""
CONQUISTA MUNDIAL - overlay de TikTok LIVE (independiente del juego que estés jugando).

  Interactive/TikFinity (regalo/chat) --POST--> /webhook --SSE--> overlay + panel

- Overlay (fuente de navegador):   /            (1080x400, franja superior)
- Panel de control (solo para ti): /panel
- WebHook de Interactive:          /webhook     (POST JSON)

Reglas:
- Cada ronda hay un TOP 3 de donadores. Al pulsar "Fin de ronda":
    TOP 1 -> gana el derecho a conquistar un país (lo pide en el chat: "conquisto tailandia")
    TOP 2 -> su nombre queda destacado en el overlay durante la ronda siguiente
- País libre -> conquistado; su VALOR es lo que donó el conquistador en esa ronda.
- País con dueño -> BATALLA con cuenta atrás: el atacante empieza con lo que donó, el dueño
  con el valor del país. Los regalos de cada uno suman a su lado. Gana el que más tenga
  (empate = defiende el dueño). La cifra del ganador pasa a ser el nuevo valor del país.

Sin dependencias: solo librería estándar.   python server.py
"""
import copy
import json
import os
import queue
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from urllib.request import Request, urlopen

from countries import COUNTRIES, BY_CODE, CONTS, find_country, slug

PORT = int(os.environ.get('PORT', 3210))
HOOK_TOKEN = os.environ.get('HOOK_TOKEN')      # opcional: protege /webhook y /api con ?token=
BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, 'state.json')

GRACE_MS = 3000          # margen oculto al acabar la batalla (regalos con retraso)
SNIPE_MS = 10000         # un regalo en los últimos 10 s vuelve a poner el reloj en 10 s
MAX_EXT = 6              # ...como máximo 6 veces por batalla
EMPEROR_MIN = 3          # países mínimos en un continente para ser su emperador

lock = threading.RLock()
clients = []
clients_lock = threading.Lock()
undo_snap = None
undo_at = 0
UNDO_MS = 120000         # solo se puede deshacer durante 2 minutos (después se perderían regalos)
fresh = True             # True = arrancó sin state.json y aún no ha pasado nada


def ms():
    return int(time.time() * 1000)


def log(*a):
    print(*a, flush=True)


def default_state():
    return {
        'v': 0, 'seq': 0, 'colorSeq': 0, 'rightSeq': 0,
        'round': {'n': 1, 'totals': {}},
        'users': {},            # uid -> {name, img, c}
        'featured': None,       # {uid, coins}  (top 2 de la ronda anterior)
        'rights': [],           # [{id, uid, amount, round}]  conquistas pendientes de elegir país
        'countries': {},        # code -> {owner, value, t}
        'battle': None,         # {code, att, def, attScore, defScore, startAt, endsAt, ext}
        'queue': [],            # batallas en espera [{code, uid, amount}]
        'events': [],           # últimos eventos (animaciones del overlay + registro del panel)
        'config': {'battleSeconds': 90},
    }


state = default_state()


def load_state():
    global state, fresh
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        merged = default_state()
        merged.update(data)
        state = merged
        fresh = False
        log(' Estado cargado:', len(state['countries']), 'países conquistados')
    except FileNotFoundError:
        pass
    except Exception as exc:
        log(' No se pudo leer state.json:', exc)


def save_state():
    try:
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception as exc:
        log(' No se pudo guardar state.json:', exc)


# ---------------------------------------------------------------- difusión
def derived():
    emp = {}
    for code, c in state['countries'].items():
        e = emp.setdefault(c['owner'], {'uid': c['owner'], 'count': 0, 'value': 0, 'conts': {}})
        e['count'] += 1
        e['value'] += c['value']
        cont = BY_CODE.get(code, {}).get('cont', '?')
        e['conts'][cont] = e['conts'].get(cont, 0) + 1
    ranking = sorted(emp.values(), key=lambda e: (-e['count'], -e['value']))
    emperors = {}
    for cont in CONTS:
        best = None
        for e in ranking:
            n = e['conts'].get(cont, 0)
            if n >= EMPEROR_MIN and (best is None or n > best['count']):
                best = {'uid': e['uid'], 'count': n}
        if best:
            emperors[cont] = best
    return {
        'empires': [{'uid': e['uid'], 'count': e['count'], 'value': e['value']} for e in ranking],
        'emperors': emperors,
    }


def payload():
    return json.dumps({'now': ms(), 'fresh': fresh, 'state': state, 'derived': derived()}, ensure_ascii=False)


def broadcast():
    data = payload()
    with clients_lock:
        for q in list(clients):
            q.put(data)


def changed():
    """Llamar (con el lock cogido) tras cualquier cambio de estado."""
    global fresh
    fresh = False
    state['v'] += 1
    save_state()
    broadcast()


def ev(kind, **kw):
    state['seq'] += 1
    e = {'id': state['seq'], 't': ms(), 'kind': kind}
    e.update(kw)
    state['events'].append(e)
    del state['events'][:-40]
    return e


# ---------------------------------------------------------------- usuarios
def norm_uid(username, nickname=''):
    u = re.sub(r'\s+', '', str(username or '').strip().lstrip('@').lower())
    if not u or '{' in u:
        u = slug(nickname)
    return u or 'anon'


def touch_user(uid, name=None, img=None):
    u = state['users'].setdefault(uid, {'name': uid})
    name = str(name or '').strip()
    if name and '{' not in name:
        u['name'] = name[:40]
    img = str(img or '').strip()
    if img.lower().startswith(('http%3a', 'https%3a')):
        img = unquote(img)
    if img.startswith('http') and '{' not in img:
        u['img'] = img
    return u


def uid_from_name(name):
    """Para el panel: reutiliza un usuario existente si el nombre coincide."""
    name = str(name or '').strip()
    low = name.lstrip('@').lower()
    for uid, u in state['users'].items():
        if uid == low or u.get('name', '').lower() == name.lower():
            return uid
    return norm_uid(name, name)


def give_color(uid):
    u = touch_user(uid)
    if 'c' not in u:
        u['c'] = state['colorSeq']
        state['colorSeq'] += 1


def uname(uid):
    return state['users'].get(uid, {}).get('name', uid)


# ---------------------------------------------------------------- lógica de juego
def add_gift(uid, name, img, coins):
    coins = max(0, int(coins))
    if coins <= 0:
        return
    touch_user(uid, name, img)
    totals = state['round']['totals']
    totals[uid] = totals.get(uid, 0) + coins
    b = state['battle']
    if b:
        side = 'att' if uid == b['att'] else 'def' if uid == b['def'] else None
        if side:
            b[side + 'Score'] += coins
            now = ms()
            if b['endsAt'] - now < SNIPE_MS and b['ext'] < MAX_EXT and now < b['endsAt'] + GRACE_MS:
                b['endsAt'] = now + SNIPE_MS
                b['ext'] += 1
    changed()


def end_round():
    r = state['round']
    ranked = sorted(r['totals'].items(), key=lambda kv: -kv[1])   # estable: empate -> quien donó antes
    top = [{'uid': u, 'coins': c} for u, c in ranked[:3]]
    state['featured'] = top[1] if len(top) > 1 else None
    if top:
        state['rightSeq'] += 1
        state['rights'].append({'id': state['rightSeq'], 'uid': top[0]['uid'],
                                'amount': top[0]['coins'], 'round': r['n']})
    ev('round_end', n=r['n'], top=top)
    state['round'] = {'n': r['n'] + 1, 'totals': {}}
    changed()


def conquer(uid, code, amount):
    give_color(uid)
    state['countries'][code] = {'owner': uid, 'value': amount, 't': ms()}
    ev('conquest', uid=uid, code=code, value=amount)


def start_battle(code, uid, amount):
    """Resuelve una conquista sobre `code`: libre -> conquista, propio -> refuerzo, ajeno -> batalla."""
    c = state['countries'].get(code)
    if not c:
        conquer(uid, code, amount)
    elif c['owner'] == uid:
        c['value'] += amount
        ev('reinforce', uid=uid, code=code, value=c['value'])
    elif state['battle']:
        state['queue'].append({'code': code, 'uid': uid, 'amount': amount})
        ev('info', text='Batalla en cola: %s ataca %s' % (uname(uid), BY_CODE[code]['name']))
    else:
        give_color(uid)
        now = ms()
        dur = int(state['config'].get('battleSeconds', 90)) * 1000
        state['battle'] = {'code': code, 'att': uid, 'def': c['owner'], 'attScore': amount,
                           'defScore': c['value'], 'startAt': now, 'endsAt': now + dur, 'ext': 0}
        ev('battle_start', code=code, att=uid, **{'def': c['owner']})


def claim(right, code):
    """El dueño de un derecho de conquista elige país. Devuelve mensaje de error o None."""
    b = state['battle']
    if (b and b['code'] == code) or any(q['code'] == code for q in state['queue']):
        return '%s está en plena batalla, elige otro país' % BY_CODE[code]['name']
    state['rights'] = [r for r in state['rights'] if r['id'] != right['id']]
    start_battle(code, right['uid'], right['amount'])
    return None


def resolve_battle():
    b = state['battle']
    if not b:
        return
    code = b['code']
    if b['attScore'] > b['defScore']:
        state['countries'][code] = {'owner': b['att'], 'value': b['attScore'], 't': ms()}
        ev('battle_end', code=code, winner=b['att'], loser=b['def'], flipped=True,
           score=b['attScore'], other=b['defScore'])
    else:
        c = state['countries'].get(code)
        if c:
            c['value'] = max(c['value'], b['defScore'])
        ev('battle_end', code=code, winner=b['def'], loser=b['att'], flipped=False,
           score=b['defScore'], other=b['attScore'])
    state['battle'] = None
    next_battle()


def next_battle():
    while state['queue'] and not state['battle']:
        q = state['queue'].pop(0)
        start_battle(q['code'], q['uid'], q['amount'])


def parse_command(text):
    """'conquistotailandia' / 'conquisto a Tailandia' / '!conquistar japon' -> candidatos de país, o None."""
    s = slug(text)
    if not s.startswith('conquist'):
        return None
    tail = s[len('conquist'):]
    cands = []
    for suf in ('o', 'ar', 'a', 'e', ''):
        if tail.startswith(suf) and tail[len(suf):]:
            cands.append(tail[len(suf):])
    return cands


def on_comment(uid, name, img, text):
    cands = parse_command(text)
    if cands is None:
        return 'ignorado'
    mine = [r for r in state['rights'] if r['uid'] == uid]
    if not mine:
        return 'sin derecho'            # solo puede conquistar quien ganó una ronda
    touch_user(uid, name, img)
    code = find_country(cands) if cands else None
    if not code:
        ev('claim_fail', uid=uid, text=str(text)[:60], reason='País no reconocido')
        changed()
        return 'no reconocido'
    err = claim(mine[0], code)
    if err:
        ev('claim_fail', uid=uid, text=str(text)[:60], reason=err)
    changed()
    return err or 'ok'


def ticker():
    while True:
        time.sleep(0.25)
        with lock:
            b = state['battle']
            if b and ms() >= b['endsAt'] + GRACE_MS:
                resolve_battle()
                changed()


# ---------------------------------------------------------------- acciones del panel
DESTRUCTIVE = {'end_round', 'assign', 'cancel_right', 'set_owner', 'free_country',
               'battle_resolve', 'battle_cancel', 'reset_round', 'reset_all', 'import'}


def api_action(a, d):
    global state, undo_snap, undo_at
    if a in DESTRUCTIVE:
        undo_snap = copy.deepcopy(state)
        undo_at = ms()

    if a == 'gift':
        name = d.get('name') or ''
        if not str(name).strip():
            return 'Falta el nombre'
        add_gift(uid_from_name(name), name if uid_from_name(name) not in state['users'] else None,
                 d.get('img'), int(d.get('coins') or 0))
    elif a == 'comment':
        name = d.get('name') or ''
        res = on_comment(uid_from_name(name), None, None, d.get('text') or '')
        if res != 'ok':
            return 'Comentario: ' + res
    elif a == 'end_round':
        end_round()
    elif a == 'reset_round':
        state['round']['totals'] = {}
        changed()
    elif a == 'assign':
        right = next((r for r in state['rights'] if r['id'] == d.get('id')), None)
        code = find_country(str(d.get('country') or ''))
        if not right:
            return 'Ese derecho ya no existe'
        if not code:
            return 'País no reconocido'
        err = claim(right, code)
        if err:
            return err
        changed()
    elif a == 'cancel_right':
        state['rights'] = [r for r in state['rights'] if r['id'] != d.get('id')]
        changed()
    elif a == 'set_owner':
        code = find_country(str(d.get('country') or ''))
        name = str(d.get('name') or '').strip()
        if not code or not name:
            return 'Falta nombre o país válido'
        uid = uid_from_name(name)
        touch_user(uid, name if uid not in state['users'] else None)
        conquer(uid, code, max(1, int(d.get('value') or 1)))
        changed()
    elif a == 'free_country':
        code = str(d.get('code') or '')
        if state['battle'] and state['battle']['code'] == code:
            return 'Ese país está en batalla'
        state['countries'].pop(code, None)
        changed()
    elif a == 'battle_resolve':
        resolve_battle()
        changed()
    elif a == 'battle_time':
        b = state['battle']
        if b:
            b['endsAt'] = max(ms(), b['endsAt']) + int(d.get('seconds') or 30) * 1000
            changed()
    elif a == 'battle_cancel':
        if state['battle']:
            ev('info', text='Batalla cancelada')
            state['battle'] = None
            next_battle()
            changed()
    elif a == 'config':
        secs = int(d.get('battleSeconds') or 90)
        state['config']['battleSeconds'] = min(600, max(15, secs))
        changed()
    elif a == 'undo':
        if not undo_snap:
            return 'Nada que deshacer'
        if ms() - undo_at > UNDO_MS:
            undo_snap = None
            return 'Ya no se puede deshacer (han pasado más de 2 minutos)'
        snap, undo_snap = undo_snap, None
        snap['seq'], snap['events'], snap['v'] = state['seq'], state['events'], state['v']
        state = snap
        b = state['battle']
        if b and b['endsAt'] < ms() + 15000:
            b['endsAt'] = ms() + 15000
        ev('info', text='Deshecha la última acción del panel')
        changed()
    elif a == 'reset_all':
        seq = state['seq']
        state = default_state()
        state['seq'] = seq
        ev('info', text='Todo reiniciado')
        changed()
    elif a == 'import':
        data = d.get('state')
        if not isinstance(data, dict) or 'countries' not in data:
            return 'Copia no válida'
        merged = default_state()
        merged.update(data)
        merged['seq'] = max(int(merged.get('seq') or 0), state['seq'])
        state = merged
        b = state['battle']
        if b:
            b['endsAt'] = ms() + 30000
        ev('info', text='Estado restaurado desde una copia')
        changed()
    else:
        return 'Acción desconocida'
    return None


def handle_webhook(obj):
    """Evento de Interactive/TikFinity. Devuelve una etiqueta para el log."""
    uid = norm_uid(obj.get('username') or obj.get('user'), obj.get('nickname') or '')
    name = obj.get('nickname') or obj.get('nick') or obj.get('username') or ''
    img = obj.get('imgprofile') or obj.get('img') or obj.get('avatar') or obj.get('profilePictureUrl') or ''
    event = str(obj.get('event') or '').lower()
    comment = obj.get('comment') or obj.get('message') or obj.get('text')
    if event == 'comment' or (comment is not None and 'coins' not in obj):
        return 'comment:' + on_comment(uid, name, img, comment or '')
    if event in ('gift', 'attack', 'coins') or 'coins' in obj:
        try:
            coins = int(float(str(obj.get('coins'))))
        except (TypeError, ValueError):
            coins = 1
        add_gift(uid, name, img, coins)
        return 'gift:%d' % coins
    return 'ignorado'


recent = []              # últimas peticiones recibidas en /webhook (diagnóstico en /debug)
bad_bodies = []          # últimos cuerpos que no se pudieron leer (diagnóstico en /debug)


def parse_body(text, depth=0):
    """JSON normal; tolera placeholders sin comillas ("coins":{coins}) y el cuerpo enviado como cadena JSON."""
    try:
        obj = json.loads(text)
    except ValueError:
        fixed = re.sub(r':\s*\{(\w+)\}', lambda m: ': "{' + m.group(1) + '}"', text)
        obj = json.loads(fixed)
    if isinstance(obj, str) and depth < 2:      # Interactive a veces manda el JSON dentro de una cadena
        return parse_body(obj, depth + 1)
    return obj


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html', '/overlay'):
            self.serve_file('overlay.html')
        elif path == '/panel':
            self.serve_file('panel.html')
        elif path == '/events':
            self.handle_sse()
        elif path == '/countries.json':
            self.send_json({'countries': COUNTRIES, 'conts': CONTS})
        elif path == '/webhook':
            self.do_POST()
        elif path == '/health':
            self.send_json({'ok': True, 'clients': len(clients)})
        elif path == '/debug':
            self.send_json({'recent': recent, 'bad_bodies': bad_bodies, 'v': state['v']})
        elif path == '/avatar':
            self.serve_avatar()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404')

    def serve_file(self, rel):
        with open(os.path.join(BASE, rel), 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_avatar(self):
        url = (parse_qs(urlparse(self.path).query).get('u', [''])[0] or '').strip()
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            self.send_response(400)
            self.end_headers()
            return
        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'image/*,*/*;q=0.8',
                                        'Referer': 'https://www.tiktok.com/'})
            with urlopen(req, timeout=8) as resp:
                body = resp.read(3 * 1024 * 1024 + 1)
                if len(body) > 3 * 1024 * 1024:
                    raise ValueError('avatar demasiado grande')
                ctype = resp.headers.get('Content-Type', 'image/jpeg').split(';', 1)[0]
                if not ctype.startswith('image/'):
                    ctype = 'image/jpeg'
        except Exception:
            self.send_response(502)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_sse(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self._cors()
        self.end_headers()
        q = queue.Queue()
        with lock:
            first = payload()
        with clients_lock:
            clients.append(q)
        try:
            self.wfile.write(('data: ' + first + '\n\n').encode('utf-8'))
            self.wfile.flush()
            while True:
                try:
                    data = q.get(timeout=15)
                    self.wfile.write(('data: ' + data + '\n\n').encode('utf-8'))
                except queue.Empty:
                    self.wfile.write(b': ping\n\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with clients_lock:
                if q in clients:
                    clients.remove(q)

    def read_body(self):
        if 'chunked' in (self.headers.get('Transfer-Encoding') or '').lower():
            data = b''
            while True:
                size = int((self.rfile.readline().split(b';')[0].strip() or b'0'), 16)
                if size == 0:
                    self.rfile.readline()
                    break
                data += self.rfile.read(size)
                self.rfile.readline()
            return data
        length = int(self.headers.get('Content-Length', '0') or 0)
        return self.rfile.read(length) if length else b''

    def do_PUT(self):
        self.do_POST()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ('/webhook', '/api'):
            self.send_response(404)
            self.end_headers()
            return
        if HOOK_TOKEN and parse_qs(parsed.query).get('token', [''])[0] != HOOK_TOKEN:
            self.send_json({'ok': False, 'error': 'token'}, 403)
            return
        raw = self.read_body()
        if parsed.path == '/webhook':
            recent.append({'t': ms(), 'method': self.command, 'query': parsed.query[:200],
                           'ctype': self.headers.get('Content-Type'), 'len': len(raw),
                           'te': self.headers.get('Transfer-Encoding'), 'raw': raw[:700].decode('latin-1')})
            del recent[:-10]
        try:
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                text = raw.decode('latin-1')
            obj = parse_body(text) if raw else {}
        except Exception:
            obj = {}
            bad_bodies.append({'t': ms(), 'path': parsed.path, 'raw': raw[:400].decode('latin-1')})
            del bad_bodies[:-10]
        if not isinstance(obj, dict):
            obj = {}
        if not obj and parsed.path == '/webhook':
            form = parse_qs(parsed.query)
            try:
                form.update(parse_qs(raw.decode('utf-8', 'replace')))
            except Exception:
                pass
            obj = {k: v[0] for k, v in form.items() if k != 'token'}
        try:
            with lock:
                if parsed.path == '/webhook':
                    res = handle_webhook(obj)
                    if not res.startswith('comment:ignorado') and not res.startswith('comment:sin'):
                        log('webhook:', obj.get('username'), res)
                    self.send_json({'ok': True, 'result': res})
                else:
                    err = api_action(str(obj.get('action') or ''), obj)
                    self.send_json({'ok': not err, 'error': err})
        except Exception as exc:
            log('error:', repr(exc))
            self.send_json({'ok': False, 'error': repr(exc)}, 500)


if __name__ == '__main__':
    load_state()
    threading.Thread(target=ticker, daemon=True).start()
    log('=' * 60)
    log(' CONQUISTA MUNDIAL')
    log(f' Overlay : http://localhost:{PORT}/')
    log(f' Panel   : http://localhost:{PORT}/panel')
    log(f' WebHook : http://localhost:{PORT}/webhook')
    log('=' * 60)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
