import { NextRequest } from 'next/server';

const BACKEND_URL = (process.env.BACKEND_API_URL || 'https://aaq-api-v2.onrender.com')
  .replace(/\\n/g, '')
  .trim()
  .replace(/\/$/, '');

type RouteContext = {
  params: Promise<{ path: string[] }> | { path: string[] };
};

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

async function proxy(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  const backendPath = params.path.map(encodeURIComponent).join('/');
  const targetUrl = `${BACKEND_URL}/${backendPath}${request.nextUrl.search}`;
  const headers = new Headers();

  for (const [key, value] of request.headers.entries()) {
    const lowerKey = key.toLowerCase();
    if (!HOP_BY_HOP_HEADERS.has(lowerKey) && lowerKey !== 'host') {
      headers.set(key, value);
    }
  }

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(),
    cache: 'no-store',
  });
  const responseBody = await response.text();

  const responseHeaders = new Headers();
  for (const [key, value] of response.headers.entries()) {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  }
  responseHeaders.delete('content-encoding');
  responseHeaders.delete('content-length');
  responseHeaders.set('Cache-Control', 'no-store');
  responseHeaders.set('x-proxy-body-length', String(responseBody.length));

  return new Response(responseBody, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
