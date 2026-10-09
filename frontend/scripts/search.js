document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('search-results');
  const title = document.getElementById('search-title');
  const params = new URLSearchParams(location.search);
  const query = (params.get('query') || params.get('q') || '').trim();
  if (!container) return;
  if (!query) { SafeDOM.message(container, '검색어를 입력해주세요.', 'no-results'); return; }
  if (title) title.textContent = `"${query}" 검색 결과`;
  try {
    const response = await AppAPI.request('/api/book/search/?query=' + encodeURIComponent(query), { auth: false });
    if (!response.ok) throw new Error('검색 오류');
    const books = SafeDOM.list(await response.json());
    if (!books.length) SafeDOM.message(container, '검색 결과가 없습니다.', 'no-results');
    else renderSearchBooks(container, books);
  } catch {
    SafeDOM.message(container, '검색 중 오류가 발생했습니다.', 'error-message');
  }
});

function renderSearchBooks(container, books) {
  const S = SafeDOM;
  container.replaceChildren(...books.map(book => {
    const item = S.element('div', 'book-item');
    const cover = S.element('div', 'book-cover-container');
    S.bookClick(cover, book.isbn);
    const img = S.element('img', 'book-cover'); img.alt = S.text(book.title); S.image(img, book.image_url);
    cover.append(img);
    const info = S.element('div', 'book-info');
    const link = S.element('a', '', '📖 자세히 보기'); S.link(link, book.link);
    info.append(S.element('h3', '', book.title), S.element('p', '', `${S.text(book.author)} / ${S.text(book.publisher)} (${S.text(book.published_date)})`), link);
    item.append(cover, info); return item;
  }));
}
