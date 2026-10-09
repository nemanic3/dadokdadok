document.addEventListener('DOMContentLoaded', () => {
    async function requestRecovery(button, emailId, resultId, endpoint) {
        const email = document.getElementById(emailId)?.value.trim();
        const result = document.getElementById(resultId);
        if (!email) { result.textContent = '이메일을 입력해주세요.'; return; }
        button.disabled = true;
        try {
            const response = await AppAPI.request(endpoint, { auth: false, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
            const data = await response.json();
            result.textContent = response.ok ? (data.message || '등록된 이메일이면 계정 복구 안내가 전송됩니다.') : (data.error || '요청을 처리하지 못했습니다.');
        } catch { result.textContent = '서버와 통신하지 못했습니다.'; }
        finally { button.disabled = false; }
    }
    const findId = document.getElementById('find-id-btn');
    const findPw = document.getElementById('find-pw-btn');
    findId?.addEventListener('click', () => requestRecovery(findId, 'find-id-email', 'id-result', '/api/user/find-id/'));
    findPw?.addEventListener('click', () => requestRecovery(findPw, 'find-pw-email', 'pw-result', '/api/user/reset-password/'));
    const params = new URLSearchParams(location.search);
    const uid = params.get('uid');
    const token = params.get('token');
    // Django's URL-safe UID encodes the integer user id, not a username.
    let resetOwner = '';
    try {
        if (uid && /^[A-Za-z0-9_-]+={0,2}$/.test(uid)) {
            const decoded = atob(uid.replace(/-/g, '+').replace(/_/g, '/'));
            if (/^[0-9]+$/.test(decoded)) resetOwner = decoded;
        }
    } catch { /* An unknown target must never clear another session. */ }
    const form = document.getElementById('reset-password-form');
    const result = document.getElementById('reset-result');
    if (!form) return;
    if (uid || token) {
        document.getElementById('reset-section').hidden = false;
        form.hidden = !(uid && token);
        document.getElementById('reset-uid').value = uid || '';
        document.getElementById('reset-token').value = token || '';
        history.replaceState(null, '', location.pathname);
        if (!uid || !token) result.textContent = '복구 링크가 올바르지 않습니다. 새 링크를 요청해주세요.';
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const password = document.getElementById('reset-new-password').value;
        const confirmPassword = document.getElementById('reset-confirm-password').value;
        if (!uid || !token || !password || password !== confirmPassword) { result.textContent = '복구 링크와 새 비밀번호 확인을 확인해주세요.'; return; }
        const submit = form.querySelector('button'); submit.disabled = true;
        try {
            const session = AppAPI.snapshot();
            const response = await AppAPI.request('/api/user/reset-password/', { auth: false, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid, token, new_password: password }) });
            const data = await response.json();
            if (!response.ok) { result.textContent = data.error || '링크가 만료되었거나 비밀번호 조건을 충족하지 못했습니다.'; return; }
            form.reset(); form.hidden = true;
            result.textContent = '비밀번호가 변경되었습니다. 로그인 화면에서 다시 로그인해주세요.';
            // Public reset success is independent of optional, account-owned cleanup.
            if (resetOwner && session.owner === resetOwner && AppAPI.isCurrent(session)) {
                try { await AppAPI.clearSession(session); }
                catch { /* A later login or unavailable storage cannot undo server success. */ }
            }
        } catch { result.textContent = '비밀번호 재설정 중 오류가 발생했습니다.'; }
        finally { submit.disabled = false; }
    });
});
