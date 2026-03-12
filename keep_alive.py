"""
Servidor HTTP mínimo para manter o Replit ativo no plano gratuito.

O Replit encerra processos que não recebem tráfego por um período.
Este arquivo sobe um servidor web simples na porta 8080. Depois, você
aponta um serviço de ping (ex: UptimeRobot) para a URL do Replit a cada
5 minutos — e o bot nunca "dorme".
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _PingHandler(BaseHTTPRequestHandler):
    """Responde qualquer GET com 200 OK e uma mensagem simples."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"TaskBot esta online!")

    # Silencia os logs padrão do HTTPServer no console
    def log_message(self, format, *args):
        pass


def keep_alive():
    """Inicia o servidor HTTP em uma thread separada (não bloqueia o bot)."""
    server = HTTPServer(("0.0.0.0", 8080), _PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
