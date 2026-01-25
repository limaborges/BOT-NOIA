#!/usr/bin/env python3
"""
Servidor HTTP simples para sincronizar estado entre máquinas.
Roda no Linux e recebe atualizações do Windows.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONSERVADORA_STATE_FILE = os.path.join(BASE_DIR, 'conservadora_remote_state.json')
PORT = 5555

class SyncHandler(BaseHTTPRequestHandler):

    def _send_response(self, status: int, data: dict):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Retorna o estado atual da CONSERVADORA"""
        if self.path == '/status':
            if os.path.exists(CONSERVADORA_STATE_FILE):
                with open(CONSERVADORA_STATE_FILE, 'r') as f:
                    state = json.load(f)
                self._send_response(200, state)
            else:
                self._send_response(200, {'status': 'no_data'})
        elif self.path == '/ping':
            self._send_response(200, {'status': 'ok', 'server': 'linux'})
        else:
            self._send_response(404, {'error': 'not found'})

    def do_POST(self):
        """Recebe atualização de estado da CONSERVADORA (Windows)"""
        if self.path == '/update':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body.decode())
                data['ultima_atualizacao'] = datetime.now().isoformat()
                data['origem'] = 'windows'

                with open(CONSERVADORA_STATE_FILE, 'w') as f:
                    json.dump(data, f, indent=2)

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Estado CONSERVADORA atualizado: R$ {data.get('saldo_atual', '?')}")
                self._send_response(200, {'status': 'ok', 'received': data})

            except json.JSONDecodeError:
                self._send_response(400, {'error': 'invalid json'})
            except Exception as e:
                self._send_response(500, {'error': str(e)})
        else:
            self._send_response(404, {'error': 'not found'})

    def log_message(self, format, *args):
        # Log simplificado
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    server = HTTPServer(('0.0.0.0', PORT), SyncHandler)
    print(f"""
╔════════════════════════════════════════════════════════════╗
║          SYNC SERVER - DUAL ACCOUNT SYSTEM                ║
╠════════════════════════════════════════════════════════════╣
║  Servidor rodando na porta {PORT}                           ║
║  Aguardando conexões do Windows...                        ║
║                                                            ║
║  Endpoints:                                                ║
║    GET  /ping   - Verificar se servidor está online       ║
║    GET  /status - Ver estado atual da CONSERVADORA        ║
║    POST /update - Atualizar estado da CONSERVADORA        ║
║                                                            ║
║  Ctrl+C para parar                                        ║
╚════════════════════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        server.shutdown()


if __name__ == '__main__':
    main()
