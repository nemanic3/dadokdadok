document.addEventListener('DOMContentLoaded', async () => {
    if (!localStorage.getItem('token')) { alert('로그인이 필요합니다.'); location.href = 'index.html'; return; }
    const images = Array.from({ length: 6 }, (_, i) => '/assets/images/profile_image' + (i || '') + '.svg');
    const profile = document.getElementById('profile-image');
    const nickname = document.getElementById('user-nickname');
    const password = document.getElementById('user-password');
    const currentPassword = document.getElementById('current-password');
    const save = document.getElementById('save-profile');
    let selected = 0;
    let profileLoaded = false;
    let saving = false;
    if (!profile || !nickname || !save) return;
    const session = AppAPI.bindSession(() => {
        profileLoaded = false;
        nickname.value = '';
        if (password) password.value = '';
        if (currentPassword) currentPassword.value = '';
        SafeDOM.image(profile, images[0], SafeDOM.profileFallback);
        save.disabled = true;
    });
    save.disabled = true;
    try {
        const response = await AppAPI.request('/api/user/me/', { session });
        if (!response.ok) throw new Error('프로필 조회 실패');
        const user = await response.json();
        AppAPI.assertSession(session);
        nickname.value = user.nickname || '';
        const image = SafeDOM.profile(user.profile_image);
        selected = Math.max(0, images.indexOf(image)); SafeDOM.image(profile, images[selected], SafeDOM.profileFallback);
        profileLoaded = true;
    } catch { alert('회원 정보를 불러오지 못했습니다.'); }
    save.disabled = !profileLoaded;
    for (const [id, direction] of [['prev-profile', -1], ['next-profile', 1]]) {
        document.getElementById(id)?.addEventListener('click', () => {
            selected = (selected + direction + images.length) % images.length;
            SafeDOM.image(profile, images[selected], SafeDOM.profileFallback);
        });
    }
    save.addEventListener('click', async () => {
        if (!AppAPI.isCurrent(session) || !profileLoaded || saving) return;
        const newPassword = password?.value || '';
        if (newPassword && !currentPassword?.value) { alert('현재 비밀번호를 입력해주세요.'); return; }
        const body = { profile_image: 'profile_images/' + images[selected].split('/').pop() };
        if (nickname.value.trim()) body.nickname = nickname.value.trim();
        if (newPassword) { body.password = newPassword; body.current_password = currentPassword.value; }
        saving = true;
        save.disabled = true;
        try {
            const result = await AppAPI.request('/api/user/update_profile/', { session, method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            const data = await result.json();
            AppAPI.assertSession(session);
            if (!result.ok) { alert('변경하지 못했습니다. 현재 비밀번호와 입력 조건을 확인해주세요.'); return; }
            if (newPassword) {
                password.value = ''; currentPassword.value = '';
                const cleared = await AppAPI.clearSession(session);
                if (!AppAPI.isCurrent(cleared)) return;
                alert('비밀번호가 변경되었습니다. 다시 로그인해주세요.'); location.href = 'index.html';
            } else {
                localStorage.setItem('username', data.user?.nickname || body.nickname || nickname.value);
                alert('프로필이 성공적으로 업데이트되었습니다.'); location.href = 'mypage.html';
            }
        } catch { alert('프로필 업데이트 중 오류가 발생했습니다.'); }
        finally { saving = false; save.disabled = !profileLoaded; }
    });
});
