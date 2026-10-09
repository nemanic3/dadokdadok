import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
const source = await readFile(new URL('../functions/api/[[path]].js', import.meta.url), 'utf8');
const { proxyAPI } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const env = { PUBLIC_HOST: 'dodok.nemanic.dev', DJANGO_ORIGIN: 'https://origin.example', ORIGIN_PROXY_SECRET: 'synthetic-proxy-secret' };

test('API forwards JWT/body/query but replaces spoofable proxy metadata and disables caching', async () => {
    const request = new Request('https://dodok.nemanic.dev/api/user/login/?q=test', {
        method: 'POST', body: '{}', headers: { Authorization: 'Bearer synthetic', 'CF-Connecting-IP': '192.0.2.1',
            'X-Forwarded-For': 'attacker', 'X-Dadok-Proxy-Secret': 'attacker', 'X-Dadok-Client-IP': 'attacker' }
    });
    const response = await proxyAPI({ request, env }, async (url, init) => {
        assert.equal(String(url), 'https://origin.example/api/user/login/?q=test');
        assert.equal(init.headers.get('authorization'), 'Bearer synthetic');
        assert.equal(init.headers.get('x-dadok-proxy-secret'), env.ORIGIN_PROXY_SECRET);
        assert.equal(init.headers.get('x-dadok-client-ip'), '192.0.2.1');
        assert.equal(init.headers.get('x-forwarded-for'), null);
        assert.equal(init.redirect, 'manual');
        assert.equal(await new Response(init.body).text(), '{}');
        return Response.json({ ok: true });
    });
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.equal(response.status, 200);
});
test('preview, absent bindings and insecure origins fail closed without upstream calls', async () => {
    for (const [url, bindings] of [
        ['https://preview.pages.dev/api/user/login/', env],
        ['https://dodok.nemanic.dev/api/user/login/', {}],
        ['https://dodok.nemanic.dev/api/user/login/', { ...env, DJANGO_ORIGIN: 'http://origin.example' }]
    ]) {
        assert.equal((await proxyAPI({ request: new Request(url), env: bindings }, () => { throw Error('must not fetch'); })).status, 503);
    }
});
test('redirects and network errors do not leak secrets or redirect tokens', async () => {
    const context = { request: new Request('https://dodok.nemanic.dev/api/test/'), env };
    for (const fetcher of [async () => Response.redirect('https://other.example'), async () => { throw Error('private'); }]) {
        const response = await proxyAPI(context, fetcher);
        assert.equal(response.status, 502);
        assert.equal(response.headers.get('location'), null);
        assert.ok(!(await response.text()).includes('private'));
    }
});
