const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const page = fs.readFileSync(path.join(__dirname, 'public', 'index.html'));
const port = Number(process.env.PORT || 3000);

const server = http.createServer((request, response) => {
  if (request.url !== '/') {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('Página não encontrada');
    return;
  }

  response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  response.end(page);
});

server.listen(port, '127.0.0.1', () => {
  console.log(`Servidor disponível em http://127.0.0.1:${server.address().port}`);
});
