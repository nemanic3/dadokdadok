/* Set window.DADOK_API_BASE_URL or <meta name="api-base-url"> before this script. */
window.AppAPI = (() => {
    const configured = window.DADOK_API_BASE_URL || document.querySelector('meta[name="api-base-url"]')?.content;
    const local = ['localhost', '127.0.0.1'].includes(location.hostname);
    const base = SafeDOM.url(configured || (local && location.port !== '8000' ? 'http://127.0.0.1:8000' : location.origin));
    if (!base) throw new Error('API 주소는 HTTP(S)여야 합니다.');
    const baseURL = base.replace(/\/$/, '');
    let refreshFlight = null;
    let logoutFlight = null;

    // A shared boundary changes on login/logout, not on access/refresh rotation.
    const epochKey = 'dadok_session_epoch';
    const recordKey = 'dadok_session_record';
    const watchers = new Set();
    function tokenOwner(token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
            return String(payload.user_id ?? payload.sub ?? '');
        } catch { return ''; /* Legacy opaque tokens remain supported. */ }
    }
    function credentials() {
        const raw = localStorage.getItem(recordKey);
        if (raw) {
            const record = JSON.parse(raw);
            // Legacy access-only expiry injection/replacement is valid only for the same JWT owner/pair.
            const access = localStorage.getItem('token');
            if (record.refresh && localStorage.getItem('refresh_token') === record.refresh) {
                if (access && tokenOwner(access) && tokenOwner(access) === tokenOwner(record.refresh)) record.access = access;
                record.username = localStorage.getItem('username') || '';
            }
            return record;
        }
        return { epoch: localStorage.getItem(epochKey), access: localStorage.getItem('token'), refresh: localStorage.getItem('refresh_token'), username: localStorage.getItem('username') || '' };
    }
    function snapshot() {
        const record = credentials();
        return { epoch: record.epoch, owner: tokenOwner(record.access) || tokenOwner(record.refresh), active: Boolean(record.access || record.refresh) };
    }
    // Native tabs serialize commits. One JSON record is authoritative; legacy keys are mirrors.
    function locked(name, action) {
        return navigator.locks ? navigator.locks.request(name, action) : action();
    }
    function mirror(record) {
        if (record.epoch) localStorage.setItem(epochKey, record.epoch);
        for (const [key, value] of [['token', record.access], ['refresh_token', record.refresh], ['username', record.username]]) {
            if (value) localStorage.setItem(key, value); else localStorage.removeItem(key);
        }
    }
    function writeRecord(record) {
        const serialized = JSON.stringify(record);
        localStorage.setItem(recordKey, serialized);
        mirror(record);
        // Converge mirrors in non-Web-Locks hosts after an interleaved boundary change.
        const latest = localStorage.getItem(recordKey);
        if (latest !== serialized && latest) mirror(JSON.parse(latest));
        notifySession();
    }
    function commit(session, update) {
        return locked('dadok-session-write', () => {
            if (session) assertSession(session);
            writeRecord(update(credentials()));
            return snapshot();
        });
    }
    function sameSession(a, b) { return a.epoch === b.epoch && a.owner === b.owner && a.active === b.active; }
    function notifySession() {
        const current = snapshot();
        for (const watcher of watchers) {
            if (!sameSession(watcher.session, current)) { watchers.delete(watcher); watcher.clear(); }
        }
        initNav();
    }
    function isCurrent(session) {
        const current = sameSession(session, snapshot());
        if (!current) notifySession();
        return current;
    }
    function assertSession(session) {
        if (!isCurrent(session)) {
            const error = new Error('세션이 변경되었습니다. 새로고침 후 다시 이용해주세요.');
            error.code = 'STALE_SESSION';
            throw error;
        }
    }
    function bindSession(clear) {
        const session = snapshot();
        watchers.add({ session, clear });
        return session;
    }
    window.addEventListener('storage', event => {
        if (event.key === null || [recordKey, epochKey, 'token', 'refresh_token'].includes(event.key)) notifySession();
    });
    function endpoint(path) {
        const resolved = new URL(path, baseURL + '/');
        if (resolved.origin !== new URL(baseURL).origin || !resolved.pathname.startsWith('/api/')) throw new Error('허용되지 않는 API 주소');
        return resolved.href;
    }
    function clearSession(session) {
        return commit(session, () => ({ epoch: crypto.randomUUID(), access: null, refresh: null, username: '' }));
    }
    function saveSession(data, session) {
        const access = data.access_token || data.access;
        const refresh = data.refresh_token || data.refresh;
        if (!access || !refresh) throw new Error('유효한 로그인 응답이 아닙니다.');

        if (tokenOwner(access) && tokenOwner(refresh) && tokenOwner(access) !== tokenOwner(refresh)) throw new Error('로그인 계정이 일치하지 않습니다.');
        return commit(session, () => ({ epoch: crypto.randomUUID(), access, refresh, username: SafeDOM.text(data.user?.nickname) }));
    }
    function sessionOperation(session, action) {
        // Hold across network + commit so another tab cannot revoke an old rotated token.
        return locked('dadok-session-network-' + (session.epoch || 'legacy'), action);
    }
    async function rotate(session) {
        assertSession(session);
        try {
            const token = credentials().refresh;
            if (!token) throw new Error('다시 로그인해주세요.');
            const result = await fetch(endpoint('/api/auth/token/refresh/'), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: token })
            });
            if (!result.ok) throw new Error('다시 로그인해주세요.');
            const data = await result.json();
            assertSession(session);
            if (!data.access) throw new Error('유효한 갱신 응답이 아닙니다.');
            const owner = tokenOwner(data.access);
            if (session.owner && owner !== session.owner) throw new Error('갱신 계정이 일치하지 않습니다.');
            await commit(session, current => ({ ...current, access: data.access, refresh: data.refresh || current.refresh }));
            assertSession(session);
            return credentials().access;
        } catch (error) {
            if (isCurrent(session)) error.clearedSession = await clearSession(session);
            throw error;
        }
    }
    function refresh(session = snapshot()) {
        assertSession(session);
        if (refreshFlight && sameSession(refreshFlight.session, session)) return refreshFlight.promise;
        const initial = credentials();
        const flight = { session };
        flight.promise = (async () => {
            try {
                return await sessionOperation(session, () => {
                    assertSession(session);
                    const current = credentials();
                    // A preceding tab already refreshed this same session; reuse its pair.
                    if (current.access && (current.access !== initial.access || current.refresh !== initial.refresh)) return current.access;
                    return rotate(session);
                });
            } finally { if (refreshFlight === flight) refreshFlight = null; }
        })();
        refreshFlight = flight;
        return flight.promise;
    }
    async function request(path, options = {}) {
        const { auth = true, session = snapshot(), ...init } = options;
        const guarded = auth || options.session !== undefined;
        if (guarded) assertSession(session);
        const token = credentials().access;
        const send = access => {
            if (guarded) assertSession(session);
            const headers = new Headers(init.headers || {});
            headers.delete('Authorization');
            if (auth && access) headers.set('Authorization', 'Bearer ' + access);
            return fetch(endpoint(path), { ...init, headers });
        };
        let result = await send(token);
        if (guarded) assertSession(session);
        if (result.status !== 401 || !auth || (!token && !credentials().refresh)) return guarded ? guardBody(result, session) : result;
        try {
            const latest = credentials().access;
            const access = latest && latest !== token ? latest : await refresh(session);
            assertSession(session);
            result = await send(access);
            assertSession(session);
            if (result.status === 401) await clearSession(session);
        } catch (error) {
            if (error.code === 'STALE_SESSION') throw error;
            // An owned refresh failure still returns 401 for the existing page error state.
        }
        return guardBody(result, session);
    }
    function guardBody(result, session) {
        for (const method of ['json', 'text', 'blob', 'arrayBuffer', 'formData']) {
            if (typeof result[method] !== 'function') continue;
            const read = result[method].bind(result);
            result[method] = async (...args) => {
                assertSession(session);
                const body = await read(...args);
                assertSession(session);
                return body;
            };
        }
        return result;
    }
    function logout() {
        const session = snapshot();
        if (logoutFlight && sameSession(logoutFlight.session, session)) return logoutFlight.promise;
        const flight = { session };
        flight.promise = (async () => {
            let revoked = false;
            let cleared = null;
            try {
                if (refreshFlight && sameSession(refreshFlight.session, session)) await refreshFlight.promise;
                await sessionOperation(session, async () => {
                    assertSession(session);
                    try {
                        const send = () => {
                            assertSession(session);
                            const { refresh: refreshToken, access: accessToken } = credentials();
                            if (!refreshToken) return Promise.resolve({ ok: false, status: 401 });
                            return fetch(endpoint('/api/user/logout/'), {
                                method: 'POST', headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: 'Bearer ' + accessToken } : {}) },
                                body: JSON.stringify({ refresh_token: refreshToken })
                            });
                        };
                        let result = await send();
                        assertSession(session);
                        if (result.status === 401 && credentials().refresh) {
                            // Already holding the shared network lock: do not acquire it recursively.
                            await rotate(session);
                            assertSession(session);
                            result = await send();
                            assertSession(session);
                        }
                        revoked = result.ok;
                    } finally {
                        // Clear before releasing the lock; queued refreshes must see a stale boundary.
                        if (isCurrent(session)) cleared = await clearSession(session);
                    }
                });
            } catch (error) { cleared = error.clearedSession || cleared; }
            finally {
                if (logoutFlight === flight) logoutFlight = null;
            }
            if (isCurrent(session)) cleared = await clearSession(session);
            if (!cleared || !isCurrent(cleared)) return;
            alert(revoked ? '로그아웃 되었습니다.' : '기기에서 로그아웃했습니다. 서버 세션 해제는 확인하지 못했습니다.');
            location.href = 'index.html';
        })();
        logoutFlight = flight;
        return flight.promise;
    }
    const bound = new WeakSet();
    function initNav() {
        const loggedIn = Boolean(credentials().access);
        const visibility = { 'login-btn': !loggedIn, 'logout-btn': loggedIn, 'profile-btn': loggedIn };
        Object.entries(visibility).forEach(([id, show]) => {
            const node = document.getElementById(id); if (node) node.style.display = show ? 'inline-block' : 'none';
        });
        for (const [selector, show] of [['.logged-in-nav', loggedIn], ['.logged-out-nav', !loggedIn]]) {
            const node = document.querySelector(selector); if (node) node.style.display = show ? 'flex' : 'none';
        }
        const name = document.getElementById('username-display');
        if (name && loggedIn) name.textContent = localStorage.getItem('username') + '님';
        else if (name) name.textContent = '';
        const button = document.getElementById('logout-btn');
        if (button && !bound.has(button)) { bound.add(button); button.addEventListener('click', logout); }
    }
    return { baseURL, request, refresh, logout, clearSession, saveSession, initNav, snapshot, isCurrent, assertSession, bindSession };
})();
