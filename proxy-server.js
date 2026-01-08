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

const server = http.createServer();

// HTTP-запросы (GET, POST и т.д.)
server.on('request', (req, res) => {
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

  proxyReq.on('error', () => {
    res.writeHead(502);
    res.end('Bad Gateway');
  });

  req.pipe(proxyReq);
});

// HTTPS-туннели (CONNECT)
server.on('connect', (req, clientSocket, head) => {
  const [targetHost, targetPort] = req.url.split(':');

  const proxySocket = net.connect({ host: proxyHost, port: proxyPortNum }, () => {
    const connectReq =
      `CONNECT ${targetHost}:${targetPort} HTTP/1.1\r\n` +
      `Host: ${targetHost}:${targetPort}\r\n` +
      `Proxy-Authorization: Basic ${proxyAuth}\r\n` +
      `\r\n`;
    proxySocket.write(connectReq);

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
        const headerPart = headerBuf.slice(0, idx + 4);
        const statusLine = headerPart.toString().split('\r\n')[0];
        if (/^HTTP\/\d\.\d 200 /.test(statusLine)) {
          clientSocket.write(headerBuf);
          proxySocket.pipe(clientSocket);
          clientSocket.pipe(proxySocket);
        } else {
          clientSocket.write('HTTP/1.1 502 Bad Gateway\r\n\r\n');
          clientSocket.end();
          proxySocket.end();
        }
      }
    }
  });

  proxySocket.on('error', () => {
    clientSocket.end();
  });

  clientSocket.on('error', () => {
    proxySocket.end();
  });
});

server.listen(8899, () => {
  console.log('Локальный прокси слушает 127.0.0.1:8899');
});
