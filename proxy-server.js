// proxy-server.js
const http = require('http');
const net = require('net');
const { Buffer } = require('buffer');

const [,, proxyHost, proxyPort, username, password] = process.argv;

if (!proxyHost || !proxyPort || !username || !password) {
  console.error('Usage: node proxy-server.js <proxyHost> <proxyPort> <username> <password>');
  process.exit(1);
}

const proxyPortNum = parseInt(proxyPort, 10);
const proxyAuth = Buffer.from(`${username}:${password}`).toString('base64');
let errorCount = 0;

const server = http.createServer();

// -- HTTP-запросы (GET, POST и т.д.) --
server.on('request', (req, res) => {
  console.log(`HTTP ${req.method} ${req.url}`);

  const headers = {
    ...req.headers,
    'Proxy-Authorization': `Basic ${proxyAuth}`
  };

  const options = {
    host: proxyHost,
    port: proxyPortNum,
    method: req.method,
    path: req.url,
    headers
  };

  const proxyReq = http.request(options, proxyRes => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', err => {
    errorCount++;
    console.error('Ошибка при проксировании HTTP:', err.message);
    if (errorCount >= 10) {
      console.error('Произошло 10 ошибок подключения к внешнему прокси');
    }
    res.writeHead(502);
    res.end('Bad Gateway');
  });

  req.pipe(proxyReq);
});

// -- HTTPS-туннели (CONNECT) --
server.on('connect', (req, clientSocket, head) => {
  const [targetHost, targetPort] = req.url.split(':');
  console.log(`CONNECT ${targetHost}:${targetPort}`);

  const proxySocket = net.connect({ host: proxyHost, port: proxyPortNum }, () => {
    // отправляем CONNECT на внешний прокси
    const connectReq =
      `CONNECT ${targetHost}:${targetPort} HTTP/1.1\r\n` +
      `Host: ${targetHost}:${targetPort}\r\n` +
      `Proxy-Authorization: Basic ${proxyAuth}\r\n` +
      `\r\n`;
    proxySocket.write(connectReq);
    // сразу шлём клиентский «head», если он есть
    if (head && head.length) {
      proxySocket.write(head);
    }
  });

  let headerBuf = Buffer.alloc(0);
  let headersDone = false;

  proxySocket.on('data', chunk => {
    if (!headersDone) {
      headerBuf = Buffer.concat([headerBuf, chunk]);
      const idx = headerBuf.indexOf('\r\n\r\n');
      if (idx !== -1) {
        headersDone = true;
        const headerPart = headerBuf.slice(0, idx + 4).toString();
        const statusLine = headerPart.split('\r\n')[0];
        const ok = /^HTTP\/\d\.\d 200 /.test(statusLine);
        if (ok) {
          // шлём клиенту и заголовки, и всё, что пришло после
          clientSocket.write(headerBuf);
          // дальше — туннель в обе стороны
          proxySocket.pipe(clientSocket);
          clientSocket.pipe(proxySocket);
        } else {
          errorCount++;
          console.error(`Proxy CONNECT failed: ${statusLine}`);
          if (errorCount >= 10) {
            console.error('Произошло 10 ошибок подключения к внешнему прокси');
          }
          clientSocket.write('HTTP/1.1 502 Bad Gateway\r\n\r\n');
          clientSocket.end();
          proxySocket.end();
        }
      }
    }
    // если headersDone, последующие данные пойдут через pipe автоматически
  });

  proxySocket.on('error', err => {
    errorCount++;
    console.error('Ошибка proxySocket:', err.message);
    if (errorCount >= 10) {
      console.error('Произошло 10 ошибок подключения к внешнему прокси');
    }
    clientSocket.end();
  });

  clientSocket.on('error', err => {
    console.error('Ошибка clientSocket:', err.message);
    proxySocket.end();
  });
});

server.listen(8899, () => {
  console.log('Локальный прокси слушает 127.0.0.1:8899');
});

