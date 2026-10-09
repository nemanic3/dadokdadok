document.addEventListener('DOMContentLoaded', async () => {
    if (!localStorage.getItem('token')) {
        alert('로그인이 필요합니다.');
        window.location.href = 'index.html';
        return;
    }
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Seoul', year: 'numeric', month: 'numeric'
    }).formatToParts(new Date());
    const yearInput = document.getElementById('goal-year');
    const monthInput = document.getElementById('goal-month');
    const status = document.getElementById('goal-status');
    yearInput.value = parts.find(part => part.type === 'year').value;
    for (let month = 1; month <= 12; month++) {
        const option = document.createElement('option');
        option.value = String(month);
        option.textContent = month + '월';
        monthInput.append(option);
    }
    monthInput.value = parts.find(part => part.type === 'month').value;
    let loaded = false;
    let loadedKey = null;
    let saving = false;
    let annualId = null;
    let monthlyId = null;
    let loadVersion = 0;
    const charts = {};
    const annualSave = document.getElementById('save-annual-goal');
    const monthlySave = document.getElementById('save-monthly-goal');
    const session = AppAPI.bindSession(() => {
        ++loadVersion;
        loaded = false;
        loadedKey = annualId = monthlyId = null;
        annualSave.disabled = monthlySave.disabled = true;
        for (const id of ['annual-goal-input', 'monthly-goal-input']) document.getElementById(id).value = '';
        for (const id of ['goal-target', 'goal-progress', 'monthly-goal-target', 'monthly-goal-progress']) document.getElementById(id).textContent = '-';
        for (const chart of Object.values(charts)) chart.destroy();
        status.textContent = '세션이 변경되었습니다. 새로고침 후 다시 이용해주세요.';
    });

    function period() {
        return {year: Number(yearInput.value), month: Number(monthInput.value)};
    }
    function validPeriod({year, month}) {
        return Number.isInteger(year) && year >= 1 && year <= 9999 &&
               Number.isInteger(month) && month >= 1 && month <= 12;
    }
    async function getData(path) {
        const response = await AppAPI.request(path, { session });
        if (!response.ok) throw new Error('목표·통계를 불러오지 못했습니다.');
        return response.json();
    }
    function draw(id, labels, values, label, colors) {
        if (typeof Chart === 'undefined') return;
        charts[id]?.destroy();
        charts[id] = new Chart(document.getElementById(id).getContext('2d'), {
            type: 'bar',
            data: {labels, datasets: [{label, data: values, backgroundColor: colors}]},
            options: {scales: {y: {beginAtZero: true, ticks: {precision: 0}}}}
        });
    }
    async function load() {
        if (!AppAPI.isCurrent(session)) return;
        const version = ++loadVersion;
        loaded = false;
        annualSave.disabled = monthlySave.disabled = true;
        annualId = monthlyId = null;
        const {year, month} = period();
        if (!validPeriod({year, month})) {
            status.textContent = '올바른 연도와 월을 입력하세요.';
            return;
        }
        status.textContent = '리뷰 기록일 기준 통계를 불러오는 중입니다.';
        try {
            const [annual, monthly, selectedMonth] = await Promise.all([
                getData('/api/goal/progress/?year=' + year),
                getData('/api/goal/monthly-progress/?year=' + year),
                getData('/api/goal/progress/?year=' + year + '&month=' + month)
            ]);
            if (!AppAPI.isCurrent(session) || version !== loadVersion) return;
            annualId = annual.goal_id ?? null;
            monthlyId = selectedMonth.goal_id ?? null;
            document.getElementById('goal-target').textContent = (annual.goal_books ?? 0) + ' 권';
            document.getElementById('goal-progress').textContent = (annual.read_books ?? 0) + ' 권';
            document.getElementById('monthly-goal-target').textContent = (selectedMonth.goal_books ?? 0) + ' 권';
            document.getElementById('monthly-goal-progress').textContent = (selectedMonth.read_books ?? 0) + ' 권';
            document.getElementById('annual-goal-input').value = annualId ? annual.goal_books : '';
            document.getElementById('monthly-goal-input').value = monthlyId ? selectedMonth.goal_books : '';
            draw('goalChart', [year + '년 목표', year + '년 리뷰 기록 도서'],
                 [annual.goal_books ?? 0, annual.read_books ?? 0], '연간 목표 · 리뷰 기록일 기준', ['#6366f1', '#ef4444']);
            const keys = Array.from({length: 12}, (_, i) => String(year).padStart(4, '0') + '-' + String(i + 1).padStart(2, '0'));
            draw('monthlyChart', keys.map(key => Number(key.split('-')[1]) + '월'),
                 keys.map(key => monthly.monthly_reading?.[key] ?? 0), '월별 리뷰 기록 도서 수', '#4f46e5');
            loaded = true;
            loadedKey = year + ":" + month;
            annualSave.disabled = monthlySave.disabled = false;
            status.textContent = year + '년 ' + month + '월 기준입니다. 목표가 없으면 0으로 표시합니다.';
        } catch (error) {
            if (version === loadVersion) status.textContent = error.message;
        }
    }
    async function save(monthly) {
        if (!AppAPI.isCurrent(session)) return;
        const {year, month} = period();
        if (!loaded || saving || loadedKey !== year + ':' + month) {
            status.textContent = '현재 기간을 먼저 조회해 주세요.';
            return;
        }
        const input = document.getElementById(monthly ? 'monthly-goal-input' : 'annual-goal-input');
        const total = Number(input.value);
        if (!Number.isSafeInteger(total) || total <= 0) {
            status.textContent = '목표는 양의 정수로 입력하세요.';
            return;
        }
        const id = monthly ? monthlyId : annualId;
        const query = '?year=' + year + (monthly ? '&month=' + month : '');
        const path = '/api/goal/goal/' + (id ? id + '/' : '') + query;
        saving = true;
        annualSave.disabled = monthlySave.disabled = true;
        yearInput.disabled = monthInput.disabled = document.getElementById('load-period').disabled = true;
        try {
            const response = await AppAPI.request(path, {
                session,
                method: id ? 'PATCH' : 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(id ? {total_books: total} : {total_books: total, year, month: monthly ? month : null})
            });
            if (!response.ok) throw new Error('목표 저장에 실패했습니다. 기간 중복이나 입력값을 확인하세요.');
            const saved = await response.json();
            AppAPI.assertSession(session);
            await load();
            AppAPI.assertSession(session);
            if (!loaded || (monthly ? monthlyId : annualId) !== saved.id || Number(input.value) !== total) {
                throw new Error('저장 요청 후 재조회 확인에 실패했습니다. 다시 조회해 주세요.');
            }
            status.textContent = '목표가 저장되었습니다. 리뷰 기록일 기준 통계입니다.';
        } catch (error) {
            status.textContent = error.message;
        } finally {
            saving = false;
            annualSave.disabled = monthlySave.disabled = !AppAPI.isCurrent(session) || !loaded;
            yearInput.disabled = monthInput.disabled = document.getElementById('load-period').disabled = false;
        }
    }
    annualSave.addEventListener('click', () => save(false));
    monthlySave.addEventListener('click', () => save(true));
    document.getElementById('load-period').addEventListener('click', load);
    monthInput.addEventListener('change', load);
    yearInput.addEventListener('change', load);
    await load();
});
