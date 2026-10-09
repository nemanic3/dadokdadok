document.addEventListener("DOMContentLoaded", () => {
    AppAPI.initNav();
    const searchInput = document.querySelector(".search-bar");

    // ✅ 검색 기능 (엔터 입력 시 `search.html` 이동)
    if (searchInput) {
        searchInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                const query = searchInput.value.trim();
                if (query) {
                    window.location.href = `search.html?query=${encodeURIComponent(query)}`;
                }
            }
        });
    }
});
