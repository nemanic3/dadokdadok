document.addEventListener("DOMContentLoaded", async () => {

    const usernameDisplay = document.getElementById("username-display");
    const userEmail = document.getElementById("user-email");
    const goalInput = document.getElementById("goal-input");
    const setGoalBtn = document.querySelector(".set-goal-btn");
    const profileImage = document.querySelector(".profile-picture img");
    const editIcon = document.querySelector(".edit-icon");

    const token = localStorage.getItem("token");
    let goalId = null;
    let goalLoaded = false;
    let goalSaving = false;
    const session = AppAPI.bindSession(() => {
        goalId = null;
        goalLoaded = false;
        usernameDisplay.textContent = '';
        userEmail.value = goalInput.value = '';
        profileImage.src = '../assets/images/profile_image.svg';
        setGoalBtn.disabled = true;
    });

    if (!token) {
        alert("로그인이 필요합니다.");
        window.location.href = "index.html"; 
        return;
    }

    async function loadUserInfo() {
        try {
            const response = await AppAPI.request('/api/user/me/', { session });
    
            if (!response.ok) throw new Error("사용자 정보 불러오기 실패");
    
            const user = await response.json();
            AppAPI.assertSession(session);
            usernameDisplay.textContent = user.nickname;
            userEmail.value = user.email;
    
            // ✅ 프로필 이미지 변환 로직 추가
            const profileImageMap = {
                "profile_images/profile_image.svg": "../assets/images/profile_image.svg",
                "profile_images/profile_image1.svg": "../assets/images/profile_image1.svg",
                "profile_images/profile_image2.svg": "../assets/images/profile_image2.svg",
                "profile_images/profile_image3.svg": "../assets/images/profile_image3.svg",
                "profile_images/profile_image4.svg": "../assets/images/profile_image4.svg",
                "profile_images/profile_image5.svg": "../assets/images/profile_image5.svg",
            };
    
            // ✅ 프로필 이미지 URL을 변환하여 적용
            profileImage.src = profileImageMap[user.profile_image] || "../assets/images/profile_image.svg";
    
        } catch (error) {
            console.error("사용자 정보 오류:", error);
        }
    }
    

    // 무기간/다른 연도 목표를 올해 목표로 재해석하지 않는다.
    const goalYear = Number(new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Seoul', year: 'numeric'
    }).format(new Date()));
    goalInput.placeholder = goalYear + '년 연간 목표 (양의 정수)';
    goalInput.setAttribute('aria-label', goalYear + '년 연간 목표 권 수');
    setGoalBtn.disabled = true;

    async function loadGoalData() {
        goalLoaded = false;
        goalId = null;
        setGoalBtn.disabled = true;
        try {
            const response = await AppAPI.request('/api/goal/goal/?year=' + goalYear, { session });
            if (!response.ok) throw new Error('목표 데이터를 가져오는 데 실패했습니다.');
            const data = await response.json();
            AppAPI.assertSession(session);
            if (!Array.isArray(data)) throw new Error('유효한 목표 목록이 아닙니다.');
            const current = data.find(goal => goal.year === goalYear && goal.month === null);
            goalId = current?.id ?? null;
            goalInput.value = current ? current.total_books : '';
            goalLoaded = true;
            return true;
        } catch (error) {
            console.error('목표 데이터를 불러오는 중 오류 발생:', error);
            return false;
        } finally {
            setGoalBtn.disabled = !goalLoaded || goalSaving;
        }
    }

    setGoalBtn.addEventListener('click', async () => {
        if (!AppAPI.isCurrent(session) || !goalLoaded || goalSaving) return;
        const goal = Number(goalInput.value);
        if (!Number.isSafeInteger(goal) || goal <= 0) {
            alert('목표는 양의 정수로 입력하세요.');
            return;
        }
        goalSaving = true;
        setGoalBtn.disabled = true;
        try {
            const url = '/api/goal/goal/' + (goalId ? goalId + '/' : '') + '?year=' + goalYear;
            const response = await AppAPI.request(url, {
                session,
                method: goalId ? 'PATCH' : 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(goalId ? {total_books: goal} : {total_books: goal, year: goalYear, month: null})
            });
            if (!response.ok) throw new Error('목표 저장 실패: 기간 중복 또는 입력값을 확인하세요.');
            const saved = await response.json();
            AppAPI.assertSession(session);
            if (!await loadGoalData() || goalId !== saved.id || Number(goalInput.value) !== goal) {
                throw new Error('저장 요청 후 재조회 확인에 실패했습니다.');
            }
            AppAPI.assertSession(session);
            alert(goalYear + '년 연간 목표가 저장되었습니다!');
        } catch (error) {
            alert(error.message);
        } finally {
            goalSaving = false;
            setGoalBtn.disabled = !AppAPI.isCurrent(session) || !goalLoaded;
        }
    });

    // ✅ 프로필 수정 페이지 이동
    if (editIcon) {
        editIcon.addEventListener("click", () => {
            window.location.href = "mypage_edit.html";
        });
    }

    // ✅ 최초 데이터 로드
    await loadUserInfo();
    await loadGoalData();
});

