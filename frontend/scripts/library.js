document.addEventListener('DOMContentLoaded', async () => {
  const grid = document.getElementById('book-grid');
  const title = document.getElementById('user-library-title');
  if (!grid) return;
  const token = localStorage.getItem('token');
  const username = localStorage.getItem('username');
  const session = AppAPI.bindSession(() => {
    grid.replaceChildren();
    if (title) title.textContent = '새로고침 후 이용해 주세요.';
  });
  if (!token) {
    if (title) title.textContent = '로그인 후 이용해 주세요.';
    const prompt = SafeDOM.element('p', 'login-prompt', '📚 내 서재를 보려면 ');
    const link = SafeDOM.element('a', '', '로그인'); link.href = 'index.html'; prompt.append(link, document.createTextNode('하세요.'));
    grid.replaceChildren(prompt); return;
  }
  if (title) title.textContent = `${username || ''}님의 서재`;
  try {
    const response = await AppAPI.request('/api/review/library/', { session });
    if (!response.ok) throw new Error('서재 오류');
    const books = SafeDOM.list(await response.json());
    AppAPI.assertSession(session);
    if (!books.length) SafeDOM.message(grid, '📖 아직 작성한 리뷰가 없습니다.', 'no-books-message');
    else loadBooks(books);
  } catch {
    if (!AppAPI.isCurrent(session)) return;
    SafeDOM.message(grid, '⛔ 데이터를 불러오는 중 오류가 발생했습니다.', 'error-message');
  }
  const write = document.getElementById('write-review-btn');
  if (write) write.addEventListener('click', () => { location.href = 'search.html'; });
});

// Keep the original card classes while building untrusted values as text nodes.
function loadBooks(books) {
  const grid = document.getElementById("book-grid");
  const S = SafeDOM;
  grid.replaceChildren(...books.map(book => {
    const card = S.element('div', 'book-card');
    S.bookClick(card, book.isbn);
    const cover = S.element('div', 'book-cover');
    cover.style.backgroundImage = `url("${S.url(book.image_url, S.bookFallback).replace(/"/g, '%22')}")`;
    const info = S.element('div', 'book-info');
    const heading = S.element('h3', '', S.text(book.title) + ' ');
    heading.append(S.element('span', 'rating', '⭐ ' + S.rating(book.rating).toFixed(1)));
    info.append(heading, S.element('p', '', book.author), S.element('p', 'review', book.short_review || '리뷰 없음'));
    card.append(cover, info);
    return card;
  }));
}
