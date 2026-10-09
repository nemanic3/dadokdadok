document.addEventListener('DOMContentLoaded', () => {
    const S = SafeDOM;
    const currentYear = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Seoul', year: 'numeric' })
        .formatToParts(new Date()).find(part => part.type === 'year').value;
    const yearQuery = '?year=' + currentYear;
    const recent = document.getElementById('recent-books-container');
    const target = document.getElementById('goal-target');
    const progress = document.getElementById('goal-progress');
    const charts = [];
    const session = AppAPI.bindSession(() => {
        if (target) target.textContent = '-';
        if (progress) progress.textContent = '-';
        for (const chart of charts) chart.destroy?.();
    });
    const count = value => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
    function chart(id, labels, values, label, colors) {
        const canvas = document.getElementById(id);
        if (!canvas || typeof Chart !== 'function') return;
        const context = canvas.getContext('2d');
        if (!context) return;
        charts.push(new Chart(context, {
            type: 'bar', data: { labels, datasets: [{ label, data: values, backgroundColor: colors }] },
            options: { scales: { y: { beginAtZero: true, max: Math.max(1, ...values) + 2 } } }
        }));
    }
    async function loadRecent() {
        if (!recent) return;
        try {
            const response = await AppAPI.request('/api/book/recent-reviews/', { auth: false });
            if (!response.ok) throw new Error('최근 도서 오류');
            const seen = new Set();
            const books = S.list(await response.json()).filter(book => {
                const key = S.text(book.isbn);
                if (seen.has(key)) return false;
                seen.add(key); return true;
            }).slice(0, 6);
            if (!books.length) { S.message(recent, '최근 리뷰가 달린 도서가 없습니다.'); return; }
            recent.replaceChildren(...books.map(book => {
                const card = S.element('div', 'book-card'); S.bookClick(card, book.isbn);
                const image = S.element('img', 'book-cover'); image.alt = S.text(book.title); S.image(image, book.image_url);
                card.append(image, S.element('p', 'book-title', book.title), S.element('p', 'book-author', book.author)); return card;
            }));
        } catch { S.message(recent, '데이터를 불러오는 중 오류가 발생했습니다.'); }
    }
    async function loadGoal() {
        if (!localStorage.getItem('token')) return;
        try {
            const response = await AppAPI.request('/api/goal/progress/' + yearQuery, { session });
            if (!response.ok) return;
            const data = await response.json();
            AppAPI.assertSession(session);
            if (target) target.textContent = data.goal_books == null ? '-' : `${count(data.goal_books)}권`;
            if (progress) progress.textContent = data.read_books == null ? '-' : `${count(data.read_books)}권`;
            chart('goalChart', ['올해 목표 권 수', '현재 읽은 권 수'], [count(data.goal_books), count(data.read_books)], '독서 목표 진행률', ['#6366f1', '#ef4444']);
        } catch { if (AppAPI.isCurrent(session) && target) target.textContent = '불러오기 실패'; }
    }
    async function loadMonthly() {
        if (!localStorage.getItem('token')) return;
        try {
            const response = await AppAPI.request('/api/goal/monthly-progress/' + yearQuery, { session });
            if (!response.ok) return;
            const data = await response.json();
            AppAPI.assertSession(session);
            const entries = Object.entries(data.monthly_reading || {}).filter(([key]) => /^\d{4}-(0[1-9]|1[0-2])$/.test(key)).sort(([a], [b]) => a.localeCompare(b));
            chart('monthlyChart', entries.map(([key]) => `${Number(key.split('-')[1])}월`), entries.map(([, value]) => count(value)), '월별 독서량', '#4f46e5');
        } catch { /* Other dashboard sections stay usable. */ }
    }
    loadRecent(); loadGoal(); loadMonthly();
});
