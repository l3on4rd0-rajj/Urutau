const http = require('node:http');

const html = '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Hello World</title><h1>Hello World!</h1><p>Reconstruído dos arquivos TXT dentro da imagem Docker.</p></html>';
const server = http.createServer((request, response) => {
  response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  response.end(html);
});
server.listen(Number(process.env.PORT || 3000), process.env.HOST || '127.0.0.1');
