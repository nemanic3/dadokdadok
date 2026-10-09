// Production bindings must NOT be copied to preview deployments.
export async function proxyAPI({ request, env }, fetcher = fetch) {
    const fail = (status) => Response.json({ detail: '서비스 연결을 준비 중입니다.' }, {
        status, headers: { 'Cache-Control': 'no-store' }
    });
    const incoming = new URL(request.url);
    if (!env.PUBLIC_HOST || incoming.hostname !== env.PUBLIC_HOST) return fail(503);
    if (!env.DJANGO_ORIGIN || !env.ORIGIN_PROXY_SECRET) return fail(503);
    let origin;
    try {
        origin = new URL(env.DJANGO_ORIGIN);
        if (origin.protocol !== 'https:' || origin.username || origin.password ||
            origin.pathname !== '/' || origin.search || origin.hash ||
            origin.hostname === incoming.hostname) return fail(503);
    } catch { return fail(503); }
    const target = new URL(incoming.pathname + incoming.search, origin);
    const headers = new Headers(request.headers);
    for (const name of ['host', 'forwarded', 'x-forwarded-for', 'x-forwarded-host',
        'x-forwarded-proto', 'x-real-ip', 'x-dadok-proxy-secret', 'x-dadok-client-ip']) headers.delete(name);
    headers.set('X-Dadok-Proxy-Secret', env.ORIGIN_PROXY_SECRET);
    headers.set('X-Dadok-Client-IP', request.headers.get('CF-Connecting-IP') || 'unknown');
    headers.delete('CF-Connecting-IP');
    try {
        const upstream = await fetcher(target, {
            method: request.method, headers,
            body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
            // Free Render can need over a minute to wake up after idle.
            redirect: 'manual', signal: AbortSignal.timeout(90000)
        });
        // Do not redirect JWTs or recovery data to an upstream-supplied location.
        if (upstream.status >= 300 && upstream.status < 400) return fail(502);
        const responseHeaders = new Headers(upstream.headers);
        responseHeaders.set('Cache-Control', 'no-store');
        return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
    } catch { return fail(502); }
}

export const onRequest = (context) => proxyAPI(context);
