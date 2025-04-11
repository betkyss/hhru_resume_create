const http = require('http');
const net = require('net');
const { Buffer } = require('buffer');

const [,, proxyHost, proxyPort, username, password] = process.argv;
const proxyAuth = Buffer.from(`${username}:${password}`).toString('base64');

let errorCount = 0;

const server = http.createServer();

server.on('connect', (req, clientSocket) => {
  const [targetHost, targetPort] = req.url.split(':');

  const proxySocket = net.connect(proxyPort, proxyHost, () => {
    const connectRequest = [
      `CONNECT ${targetHost}:${targetPort} HTTP/1.1`,
      `Host: ${targetHost}:${targetPort}`,
      `Proxy-Authorization: Basic ${proxyAuth}`,
      ``,
      ``
    ].join('\r\n');

    proxySocket.write(connectRequest);
  });

  let buffer = '';
  let headersComplete = false;

  proxySocket.on('data', (chunk) => {
    buffer += chunk.toString();

    if (!headersComplete && buffer.includes('\r\n\r\n')) {
      headersComplete = true;
      const statusLine = buffer.split('\r\n')[0];

      if (statusLine.includes('200')) {
        clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
        proxySocket.pipe(clientSocket);
        clientSocket.pipe(proxySocket);
      } else {
        errorCount++;
        if (errorCount === 10) {
          console.error('⚠️ Произошло 10 ошибок подключения к внешнему прокси');
        }
        clientSocket.end('HTTP/1.1 502 Bad Gateway\r\n\r\n');
        proxySocket.end();
      }
    }
  });

  proxySocket.on('error', () => {
    errorCount++;
    if (errorCount === 10) {
      console.error('⚠️ Произошло 10 ошибок подключения к внешнему прокси');
    }
    clientSocket.end();
  });

  clientSocket.on('error', () => proxySocket.end());
});

server.listen(8899);

