document.addEventListener("DOMContentLoaded", async () => {
    const params = new URLSearchParams(window.location.search);
    const reviewId = params.get("id");
    let isbn = params.get("isbn");
    let token = localStorage.getItem("token");

    if (!token) {
        alert("로그인이 필요합니다.");
        window.location.href = "index.html";
        return;
    }

    // isbn이나 reviewId 중 하나는 반드시 있어야 함
    if (!isbn && !reviewId) {
        alert("잘못된 접근입니다.");
        window.location.href = "main.html";
        return;
    }

    // DOM 요소 가져오기
    const bookTitle = document.getElementById("book-title");
    const bookImage = document.getElementById("book-image");
    const ratingbookTitle = document.getElementById("rating-book-title");
    const reviewAuthorImage = document.getElementById("review-author-image");
    const reviewAuthor = document.getElementById("review-author");
    const reviewDate = document.getElementById("review-date");
    const ratingValue = document.getElementById("rating-value");
    const reviewTextElement = document.getElementById("review-text");
    const stars = document.querySelectorAll(".star");
    const publishReviewButton = document.getElementById("publish-review");
    const saveReviewButton = document.getElementById("save-rating");

    let selectedRating = 0;
    let currentReviewData = null;
    let reviewLoaded = !reviewId;
    const session = AppAPI.bindSession(() => {
        currentReviewData = null;
        reviewLoaded = false;
        selectedRating = 0;
        if (reviewTextElement) reviewTextElement.value = '';
        if (reviewAuthor) reviewAuthor.textContent = '';
        if (reviewDate) reviewDate.textContent = '';
        if (reviewAuthorImage) SafeDOM.image(reviewAuthorImage, SafeDOM.profileFallback, SafeDOM.profileFallback);
        updateStarsUI(0);
        if (publishReviewButton) publishReviewButton.disabled = true;
        if (saveReviewButton) saveReviewButton.disabled = true;
    });
    if (publishReviewButton) publishReviewButton.disabled = !reviewLoaded;

    try {
        // 사용자 정보 불러오기
        const userResponse = await AppAPI.request("/api/user/me/", {
            session,
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (!userResponse.ok) {
            throw new Error("사용자 정보를 불러올 수 없습니다.");
        }

        const user = await userResponse.json();
        AppAPI.assertSession(session);
        if (reviewAuthorImage) {
            SafeDOM.image(reviewAuthorImage, SafeDOM.profile(user.profile_image), SafeDOM.profileFallback);
        }
        if (reviewAuthor) reviewAuthor.textContent = user.nickname;
        if (reviewDate) reviewDate.textContent = formatDate(new Date());

        // 수정 모드인 경우 기존 리뷰 데이터 불러오기
        if (reviewId) {
            const reviewResponse = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/`, {
                session,
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!reviewResponse.ok) {
                throw new Error("리뷰 데이터를 불러올 수 없습니다.");
            }

            currentReviewData = await reviewResponse.json();
            AppAPI.assertSession(session);

            // 기존 데이터로 폼 초기화
            if (reviewTextElement) reviewTextElement.value = currentReviewData.content;
            if (currentReviewData.rating) {
                selectedRating = currentReviewData.rating;
                updateStarsUI(selectedRating);
            }

            // ISBN 설정 (수정 모드에서는 리뷰 데이터의 ISBN 사용)
            isbn = currentReviewData.isbn;
            reviewLoaded = true;
        }

        // ISBN이 있으면 책 정보 불러오기
        if (isbn) {
            const bookResponse = await AppAPI.request(`/api/book/isbn/${encodeURIComponent(isbn)}/`, { auth: false });
            if (!bookResponse.ok) throw new Error("책 정보를 불러올 수 없습니다.");
            const book = await bookResponse.json();
            AppAPI.assertSession(session);

            if (ratingbookTitle) ratingbookTitle.textContent = book.title;
            if (bookTitle) bookTitle.textContent = book.title;
            if (bookImage) {
                SafeDOM.image(bookImage, book.image_url);
                bookImage.style.cursor = "pointer";
                bookImage.addEventListener("click", () => {
                    window.location.href = `book-detail.html?isbn=${encodeURIComponent(isbn)}`;
                });
            }
        }

    } catch (error) {
        console.error("🚨 데이터 불러오기 오류:", error);
        if (!reviewLoaded) alert('리뷰를 불러오지 못했습니다. 새로고침 후 다시 시도해주세요.');
    } finally {
        if (publishReviewButton) publishReviewButton.disabled = !AppAPI.isCurrent(session) || !reviewLoaded;
    }

    // 별점 기능 추가
    stars.forEach((star, index) => {
        star.addEventListener("mousemove", (event) => updateStars(event, star, index));
        star.addEventListener("click", (event) => {
            if (!AppAPI.isCurrent(session)) return;
            selectedRating = getStarRating(event, star, index);
            updateStarsUI(selectedRating);
        });
        star.addEventListener("mouseleave", () => updateStarsUI(selectedRating));
    });

    function updateStars(event, star, index) {
        const hoverRating = getStarRating(event, star, index);
        updateStarsUI(hoverRating);
    }

    function getStarRating(event, star, index) {
        const mouseX = event.clientX - star.getBoundingClientRect().left;
        return mouseX < star.clientWidth / 2 ? index + 0.5 : index + 1;
    }

    function updateStarsUI(rating) {
        stars.forEach((star, index) => {
            if (star) {
                star.src = (index + 1 <= rating) ? "../assets/images/full_star.svg" :
                    (index + 0.5 === rating) ? "../assets/images/half_star.svg" :
                    "../assets/images/empty_star.svg";
            }
        });
        if (ratingValue) ratingValue.textContent = `${rating.toFixed(1)}점`;
    }

    // 리뷰 발행/수정 (POST/PUT)
    if (publishReviewButton) {
        publishReviewButton.textContent = reviewId ? "수정" : "발행";
        publishReviewButton.addEventListener("click", async () => {
            if (!AppAPI.isCurrent(session) || !reviewLoaded) return;
            const content = reviewTextElement.value.trim();
            if (!content) {
                alert("리뷰 내용을 입력해주세요.");
                return;
            }

            const requestBody = { isbn, content, rating: selectedRating };
            const url = reviewId ? 
                `/api/review/${encodeURIComponent(reviewId)}/` :
                "/api/review/";

            const method = reviewId ? "PUT" : "POST";

            try {
                const response = await AppAPI.request(url, {
                    session,
                    method,
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(requestBody)
                });

                const responseData = await response.json();
                AppAPI.assertSession(session);

                if (!response.ok) throw new Error(responseData.detail || "리뷰 처리 실패");

                const successMessage = reviewId ? "리뷰가 수정되었습니다." : "리뷰가 발행되었습니다.";
                alert(successMessage);

                // 리뷰 상세 페이지로 이동
                const targetReviewId = reviewId || responseData.id;
                window.location.href = `review-detail.html?id=${targetReviewId}`;
            } catch (error) {
                console.error("🚨 리뷰 처리 오류:", error);
                alert(reviewId ? "리뷰 수정 중 오류가 발생했습니다." : "리뷰 발행 중 오류가 발생했습니다.");
            }
        });
    }

    // 별점 저장 기능 (수정 모드에서는 비활성화)
    if (saveReviewButton) {
        saveReviewButton.style.display = reviewId ? "none" : "block";
    }
});

function formatDate(date) {
    return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
}