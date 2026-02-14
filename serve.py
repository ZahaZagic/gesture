from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class COOPCOEPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # These headers are required for SharedArrayBuffer support (used by SeeSo SDK)
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        super().end_headers()

if __name__ == '__main__':
    # Serve from the game directory
    web_dir = os.path.join(os.getcwd(), 'game_web_seeso')
    os.chdir(web_dir)
    
    port = 8090
    server_address = ('', port)
    httpd = HTTPServer(server_address, COOPCOEPRequestHandler)
    
    print(f"Serving at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    print("Log:")
    httpd.serve_forever()
