document.addEventListener("DOMContentLoaded", async () => {

  const bookImage = document.getElementById("book-image");
  const bookTitle = document.getElementById("book-title");
  const bookAuthor = document.getElementById("book-author");
  const bookPublisher = document.getElementById("book-publisher");
  const bookLink = document.getElementById("book-link"); 
  const reviewsList = document.getElementById("reviews-list");
  const recommendationsList = document.getElementById("recommendation-grid"); 
  const session = AppAPI.bindSession(() => { recommendationsList?.replaceChildren(); });

  const params = new URLSearchParams(window.location.search);
  const isbn = params.get("isbn");

  if (!isbn) {
      alert("잘못된 접근입니다.");
      window.location.href = "main.html";
      return;
  }

  let bookUrl = '';

  
  // ✅ 책 정보 가져오기
  async function loadBookDetails() {
      try {
          const response = await AppAPI.request(`/api/book/isbn/${encodeURIComponent(isbn)}/`, { auth: false });
          if (!response.ok) throw new Error("책 정보를 불러올 수 없습니다.");

          const book = await response.json();
          SafeDOM.image(bookImage, book.image_url);
          bookTitle.textContent = book.title;
          bookAuthor.textContent = `${SafeDOM.text(book.author, "저자 정보 없음")} / ${book.translator || "번역 없음"}`;
          bookPublisher.textContent = `${SafeDOM.text(book.publisher, "출판사 정보 없음")} / ${SafeDOM.text(book.published_date, "출판일 정보 없음")}`;

          bookUrl = SafeDOM.url(book.link);
          SafeDOM.link(bookLink, bookUrl);
          bookLink.style.display = "inline-block";
          loadRecommendations(SafeDOM.text(book.title));

      } catch (error) {
          console.error("책 정보 오류:", error);
      }
  }

  // ✅ 특정 책의 최신 리뷰 목록 가져오기
  async function loadReviews() {
      try {
          const token = localStorage.getItem("token");
          const response = await AppAPI.request(`/api/review/library/${encodeURIComponent(isbn)}/`, {
              auth: false,
              method: "GET",
              headers: {
                  "Authorization": `Bearer ${token}`,
                  "Content-Type": "application/json"
              }
          });

          if (response.status === 401) {
              alert("인증이 필요합니다. 다시 로그인하세요.");
              window.location.href = "index.html";
              return;
          }

          if (!response.ok) throw new Error("리뷰를 불러올 수 없습니다.");

          const reviews = SafeDOM.list(await response.json());
          const S = SafeDOM;
          reviewsList.replaceChildren(...reviews.map(review => {
              const card = S.element('div', 'review-card'); card.dataset.reviewId = S.text(review.review_id);
              const content = S.element('p'); content.append(S.element('strong', '', review.user), document.createTextNode(': ' + S.text(review.content)));
              card.append(content, S.element('p', '', `⭐ ${S.text(review.rating)} / 5`), S.element('p', 'review-date', review.created_at));
              return card;
          }));
          if (!reviews.length) S.message(reviewsList, '아직 리뷰가 없습니다.');

          document.querySelectorAll(".review-card").forEach(reviewCard => {
              reviewCard.addEventListener("click", () => {
                  const reviewId = reviewCard.getAttribute("data-review-id");
                  if (reviewId) {
                      window.location.href = `review-detail.html?id=${encodeURIComponent(reviewId)}`;
                  } else {
                      alert("리뷰 정보를 불러오는 데 실패했습니다.");
                  }
              });
          });

      } catch (error) {
          console.error("리뷰 불러오기 오류:", error);
      }
  }

  // ✅ 연관 추천 도서 가져오기 (책 제목 사용)
  async function loadRecommendations(title) {
      if (!recommendationsList) {
          console.error("❌ 추천 도서를 표시할 recommendation-grid 요소가 없습니다.");
          return;
      }

      // ✅ 추천 도서 공간 레이아웃 유지
      recommendationsList.style.display = "grid";
      recommendationsList.style.gridTemplateColumns = "repeat(auto-fill, minmax(150px, 1fr))";
      recommendationsList.style.gap = "15px";
      recommendationsList.style.minHeight = "200px"; 

      // ✅ 검색어 최적화 (책 제목이 길 경우 자동으로 줄이기)
      function shortenTitle(title, maxLength = 6) {
          if (title.length <= maxLength) return title; 
          const words = title.split(" "); 
          let shortenedTitle = "";

          for (let word of words) {
              if ((shortenedTitle + " " + word).trim().length <= maxLength) {
                  shortenedTitle += (shortenedTitle ? " " : "") + word;
              } else {
                  break;
              }
          }
          return shortenedTitle || title.substring(0, maxLength); 
      }

      const searchQuery = shortenTitle(title);

      try {
          let books = [];
          if (localStorage.getItem('token')) {
              try {
                  const personalized = await AppAPI.request(`/api/recommendation/personalized/?isbn=${encodeURIComponent(isbn)}`, { session });
                  if (personalized.ok) books = SafeDOM.list(await personalized.json());
                  AppAPI.assertSession(session);
              } catch {
                  // Public related recommendations remain available after personal lookup failure.
              }
          }
          if (!AppAPI.isCurrent(session)) return;
          if (!books.length) {
              const response = await AppAPI.request(`/api/recommendation/naver/?isbn=${encodeURIComponent(isbn)}&query=${encodeURIComponent(searchQuery)}`, { auth: false });
              if (!response.ok) throw new Error("추천 도서를 불러올 수 없습니다.");
              const data = await response.json();
              if (data?.error) throw new Error("추천 조회 오류");
              books = SafeDOM.list(data);
          }

          if (!AppAPI.isCurrent(session)) return;
          if (books.length > 0) {
              const S = SafeDOM;
              recommendationsList.replaceChildren(...books.map(book => {
                  const item = S.element('div', 'recommendation-item');
                  const link = S.element('a'); S.link(link, book.link);
                  const image = S.element('img'); image.alt = S.text(book.title); S.image(image, book.image || book.image_url);
                  link.append(image, S.element('p', '', book.title)); item.append(link); return item;
              }));
          } else {
              SafeDOM.message(recommendationsList, '추천할 도서가 없습니다.');
              recommendationsList.style.minHeight = "200px";
          }

      } catch (error) {
          SafeDOM.message(recommendationsList, '추천 도서를 불러오는 중 오류가 발생했습니다.');
          recommendationsList.style.minHeight = "200px";
      }
  }

  loadBookDetails();
  loadReviews();
});

document.addEventListener("DOMContentLoaded", () => {
  const writeReviewBtn = document.getElementById("write-review-btn");

  if (writeReviewBtn) {
      writeReviewBtn.addEventListener("click", () => {
          const params = new URLSearchParams(window.location.search);
          const isbn = params.get("isbn"); // 현재 페이지에서 ISBN 가져오기

          if (!isbn) {
              alert("도서 정보를 찾을 수 없습니다.");
              return;
          }

          window.location.href = `review-write.html?isbn=${encodeURIComponent(isbn)}`; // 리뷰 작성 페이지로 이동
      });
  }
});
