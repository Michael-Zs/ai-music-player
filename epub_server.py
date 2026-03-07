from http.server import HTTPServer, SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == '__main__':
    port = 8080
    print(f'EPUB 阅读器运行在 http://localhost:{port}')
    HTTPServer(('', port), Handler).serve_forever()
