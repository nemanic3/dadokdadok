/* User content is always text; only validated HTTP(S) URLs reach URL sinks. */
window.SafeDOM = (() => {
    const bookFallback = '/assets/images/logo.png';
    const profileFallback = '/assets/images/profile_image.svg';
    function text(value, fallback = '') { return value == null ? fallback : String(value); }
    function element(tag, className = '', value) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== undefined) node.textContent = text(value);
        return node;
    }
    function url(value, fallback = '') {
        if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/.test(value)) return fallback;
        try {
            const parsed = new URL(value, document.baseURI);
            return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : fallback;
        } catch { return fallback; }
    }
    function image(node, value, fallback = bookFallback) {
        if (!node) return;
        node.onerror = () => { node.onerror = null; node.src = fallback; };
        node.src = url(value, fallback);
    }
    function profile(value) {
        const name = text(value).split('/').pop();
        return /^profile_image[1-5]?\.svg$/.test(name) ? '/assets/images/' + name : profileFallback;
    }
    function link(node, value) {
        const href = url(value);
        node.rel = 'noopener noreferrer';
        node.target = '_blank';
        if (href) { node.href = href; node.removeAttribute('aria-disabled'); }
        else { node.removeAttribute('href'); node.setAttribute('aria-disabled', 'true'); }
    }
    function message(container, value, className = '', tag = 'p') {
        if (container) container.replaceChildren(element(tag, className, value));
    }
    function list(data) { return Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []; }
    function rating(value) { const number = Number(value); return Number.isFinite(number) ? Math.max(0, Math.min(5, number)) : 0; }
    function bookClick(node, isbn) {
        node.addEventListener('click', () => { if (isbn != null && text(isbn)) window.location.href = 'book-detail.html?isbn=' + encodeURIComponent(isbn); });
    }
    return { text, element, url, image, profile, link, message, list, rating, bookClick, bookFallback, profileFallback };
})();
