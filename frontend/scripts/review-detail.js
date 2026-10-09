document.addEventListener("DOMContentLoaded", async () => {

    const params = new URLSearchParams(window.location.search);
    const reviewId = params.get("id");
    const token = localStorage.getItem("token") || null;
    const username = localStorage.getItem("username") || "로그인 필요";
    let currentUser = null;

    // HTML 요소 참조
    const reviewAuthor = document.getElementById("review-author");
    const reviewAuthorImage = document.getElementById("review-author-image");
    const reviewDate = document.getElementById("review-date");
    const reviewText = document.getElementById("review-text");
    const reviewLikes = document.getElementById("review-likes");
    const heartIcon = document.getElementById("heart-icon");
    const bookImage = document.getElementById("book-image");
    const bookTitle = document.getElementById("book-title");
    const reviewRating = document.getElementById("review-rating");
    const ratingValue = document.getElementById("rating-value");
    const editButton = document.getElementById("edit-button");
    const deleteButton = document.getElementById("delete-button");
    const commentInput = document.getElementById("comment-input");
    const commentList = document.getElementById("comment-list");
    const commentUsername = document.getElementById("comment-username");
    const userProfile = document.getElementById("user-profile");

    let isLiked = false;
    let likesCount = 0;
    const session = AppAPI.bindSession(() => {
        currentUser = null;
        isLiked = false;
        if (commentUsername) commentUsername.textContent = '';
        if (commentInput) { commentInput.value = ''; commentInput.disabled = true; }
        if (userProfile) SafeDOM.image(userProfile, SafeDOM.profileFallback, SafeDOM.profileFallback);
        if (heartIcon) heartIcon.src = '/assets/images/empty_heart.svg';
        if (editButton) editButton.style.display = 'none';
        if (deleteButton) deleteButton.style.display = 'none';
        commentList?.querySelectorAll('.edit-comment, .delete-comment').forEach(button => button.remove());
    });

    // 초기에 수정/삭제 버튼 숨기기
    if (editButton) editButton.style.display = "none";
    if (deleteButton) deleteButton.style.display = "none";

    if (!reviewId) {
        alert("잘못된 접근입니다.");
        window.location.href = "main.html";
        return;
    }

    // 현재 로그인한 사용자 정보 가져오기
    if (token) {
        try {
            const userResponse = await AppAPI.request("/api/user/me/", {
                session,
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (userResponse.ok) {
                currentUser = await userResponse.json();
                AppAPI.assertSession(session);

                // 댓글 입력창에 사용자 정보 표시
                if (commentUsername) commentUsername.textContent = currentUser.nickname;
                if (userProfile) {
                    SafeDOM.image(userProfile, SafeDOM.profile(currentUser.profile_image), SafeDOM.profileFallback);
                }
            }
        } catch (error) {
            console.error("🚨 사용자 정보 불러오기 오류:", error);
        }
    }

    try {
        // 리뷰 데이터 불러오기
        const reviewResponse = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/`, { auth: false });
        if (!reviewResponse.ok) throw new Error("리뷰 데이터를 불러올 수 없습니다.");

        const review = await reviewResponse.json();

        // 리뷰 작성자와 현재 사용자가 같은지 확인
        const isAuthor = currentUser && currentUser.nickname === review.user_nickname;

        // 수정/삭제 버튼 표시 및 이벤트 처리
        if (isAuthor) {
            if (editButton) {
                editButton.style.display = "inline-block";
                editButton.addEventListener("click", () => {
                    if (!AppAPI.isCurrent(session)) return;
                    window.location.href = `review-write.html?id=${encodeURIComponent(reviewId)}`;
                });
            }

            if (deleteButton) {
                deleteButton.style.display = "inline-block";
                deleteButton.addEventListener("click", async () => {
                    if (!AppAPI.isCurrent(session)) return;
                    if (!confirm("정말 삭제하시겠습니까?")) return;

                    try {
                        const deleteResponse = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/`, {
                            session,
                            method: "DELETE",
                            headers: {
                                "Authorization": `Bearer ${token}`,
                                "Content-Type": "application/json"
                            }
                        });

                        AppAPI.assertSession(session);
                        if (deleteResponse.ok) {
                            alert("리뷰가 삭제되었습니다.");
                            window.location.href = "library.html";
                        } else {
                            const errorData = await deleteResponse.json();
                            throw new Error(errorData.detail || "리뷰 삭제 실패");
                        }
                    } catch (error) {
                        console.error("🚨 리뷰 삭제 오류:", error);
                        alert(error.message);
                    }
                });
            }
        }

        // 리뷰 정보 표시
        if (reviewAuthor) reviewAuthor.textContent = review.user_nickname;
        if (reviewAuthorImage) {
            SafeDOM.image(reviewAuthorImage, SafeDOM.profile(review.user_profile_image || review.profile_image), SafeDOM.profileFallback);
        }

        if (reviewDate) reviewDate.textContent = formatDate(review.created_at);
        if (reviewText) reviewText.textContent = review.content;
        likesCount = review.likes_count ?? 0;
        if (reviewLikes) reviewLikes.textContent = likesCount;
        if (ratingValue) ratingValue.textContent = review.rating == null ? '평점 없음' : SafeDOM.rating(review.rating).toFixed(1);

        // 별점 시각화
        if (reviewRating) reviewRating.replaceChildren(...generateStars(review.rating));

        // 좋아요 상태 확인
        // 공개 상세는 익명으로 조회하므로 false는 로그인 사용자의 상태가 아니다.
        // 로그인 사용자의 저장된 상태는 인증된 liked API로 별도 확인한다.
        if (heartIcon && review.is_liked === true) {
            isLiked = review.is_liked;
            heartIcon.src = `/assets/images/${isLiked ? "full" : "empty"}_heart.svg`;
        } else if (token && heartIcon) {
            try {
                const likedResponse = await AppAPI.request("/api/review/liked/", {
                    session,
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (likedResponse.ok) {
                    const likedReviews = SafeDOM.list(await likedResponse.json());
                    AppAPI.assertSession(session);
                    isLiked = likedReviews.some(item => String(item.review_id) === String(review.id));
                    heartIcon.src = `/assets/images/${isLiked ? 'full' : 'empty'}_heart.svg`;
                }
            } catch (error) {
                console.error("🚨 좋아요 상태 확인 오류:", error);
            }
        }

        // 좋아요 토글 이벤트
        if (heartIcon && token) {
            heartIcon.addEventListener("click", async () => {
                if (!AppAPI.isCurrent(session)) return;
                try {
                    const response = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/like/`, {
                        session,
                        method: "POST",
                        headers: { "Authorization": `Bearer ${token}` }
                    });

                    if (!response.ok) throw new Error("좋아요 처리 실패");

                    const data = await response.json();
                    AppAPI.assertSession(session);
                    isLiked = data.message === "Like added";
                    likesCount = data.likes_count ?? 0;

                    heartIcon.src = `/assets/images/${isLiked ? 'full' : 'empty'}_heart.svg`;
                    if (reviewLikes) reviewLikes.textContent = likesCount;
                } catch (error) {
                    console.error("🚨 좋아요 처리 오류:", error);
                    alert("좋아요 처리 중 오류가 발생했습니다.");
                }
            });
        }

        // 책 정보 불러오기
        if (bookImage && bookTitle) {
            const bookResponse = await AppAPI.request(`/api/book/isbn/${encodeURIComponent(review.isbn)}/`, { auth: false });
            if (bookResponse.ok) {
                const book = await bookResponse.json();
                SafeDOM.image(bookImage, book.image_url);
                bookTitle.textContent = book.title;

                bookImage.addEventListener("click", () => {
                    window.location.href = `book-detail.html?isbn=${encodeURIComponent(review.isbn)}`;
                });
            } else {
                bookTitle.textContent = "책 정보를 찾을 수 없습니다.";
                SafeDOM.image(bookImage, null);
            }
        }

        // 댓글 로드
        loadComments();

    } catch (error) {
        console.error("🚨 데이터 불러오기 오류:", error);
        alert("리뷰를 불러오는 중 오류가 발생했습니다.");
    }

    // 댓글 입력 처리
    if (commentInput) {
        commentInput.addEventListener("keypress", async (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                await submitComment();
            }
        });
    }

    async function loadComments() {
        try {
            const response = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/comments/list/`, {
                auth: false,
                headers: token ? { "Authorization": `Bearer ${token}` } : {}
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const comments = SafeDOM.list(await response.json());
            if (commentList) {
                const S = SafeDOM;
                commentList.replaceChildren(...comments.map(comment => {
                    const item = S.element('li', 'comment-item');
                    const content = S.element('div', 'comment-content');
                    const image = S.element('img', 'comment-profile'); image.alt = '프로필'; S.image(image, S.profile(comment.profile_image), S.profileFallback);
                    const info = S.element('div', 'comment-info');
                    info.append(S.element('span', 'comment-author', comment.user_nickname), S.element('span', 'comment-text', comment.content));
                    content.append(image, info);
                    const ownsComment = currentUser && (comment.user != null ? String(currentUser.id) === String(comment.user) : currentUser.nickname === comment.user_nickname);
                    if (ownsComment) {
                        const edit = S.element('button', 'edit-comment action-button', '수정'); edit.type = 'button';
                        const remove = S.element('button', 'delete-comment action-button', '삭제'); remove.type = 'button';
                        edit.addEventListener('click', async () => {
                            const updated = prompt('댓글을 수정하세요.', S.text(comment.content));
                            if (updated == null || !updated.trim()) return;
                            await changeComment('PATCH', comment.id, updated.trim(), edit);
                        });
                        remove.addEventListener('click', async () => {
                            if (confirm('댓글을 삭제하시겠습니까?')) await changeComment('DELETE', comment.id, undefined, remove);
                        });
                        content.append(edit, remove);
                    }
                    item.append(content); return item;
                }));
            }
        } catch (error) {
            console.error("🚨 댓글 불러오기 오류:", error);
            if (commentList) {
                SafeDOM.message(commentList, '댓글을 불러오는 중 오류가 발생했습니다.', 'comment-error', 'li');
            }
        }
    }

    async function changeComment(method, id, content, button) {
        if (!AppAPI.isCurrent(session)) return;
        button.disabled = true;
        try {
            const body = { comment_id: id };
            if (content !== undefined) body.content = content;
            const result = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/comments/`, {
                session,
                method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
            });
            if (!result.ok) throw new Error('댓글 변경 실패');
            AppAPI.assertSession(session);
            await loadComments();
        } catch { alert('댓글을 변경하지 못했습니다. 다시 시도해주세요.'); }
        finally { button.disabled = false; }
    }

    async function submitComment() {
        if (!AppAPI.isCurrent(session)) return;
        const content = commentInput.value.trim();
        if (!content) return;

        if (!token) {
            alert("로그인이 필요합니다.");
            return;
        }

        try {
            const response = await AppAPI.request(`/api/review/${encodeURIComponent(reviewId)}/comments/`, {
                session,
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ content })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText);
            }

            AppAPI.assertSession(session);
            commentInput.value = "";
            await loadComments();
        } catch (error) {
            console.error("🚨 댓글 등록 오류:", error);
            alert("댓글 등록 중 오류가 발생했습니다.");
        }
    }
});

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return '-';
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}.${month}.${day}`;
}

function generateStars(rating) {
    const value = SafeDOM.rating(rating);
    return Array.from({ length: 5 }, (_, index) => {
        const difference = value - index;
        const type = difference >= 1 ? 'full_star' : difference > 0 ? 'half_star' : 'empty_star';
        const image = SafeDOM.element('img', 'star-icon'); image.alt = '별점'; image.src = '/assets/images/' + type + '.svg'; return image;
    });
}
