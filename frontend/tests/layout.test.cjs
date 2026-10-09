const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require(process.env.DADOK_TEST_JSDOM || 'jsdom');
const root = path.resolve(__dirname, '..');

// jsdom validates actual HTML/CSS wiring and preserved classes, not geometry.
// Real overlap/overflow assertions remain in tests/browser_smoke.py (Chromium).
function mount(name) {
  return new JSDOM(fs.readFileSync(path.join(root, 'screen', name), 'utf8'));
}

test('목표 제목은 기존 class와 설명 순서를 보존하며 normal flow에 놓인다', () => {
  const dom = mount('goals.html');
  try {
    const d = dom.window.document;
    const dashboard = d.querySelector('main.goal-dashboard');
    const title = dashboard.querySelector('h1.goal-title');
    const settings = dashboard.querySelector('.goal-settings');
    assert.equal(title.textContent, '목표 및 통계');
    assert.equal(title.nextElementSibling, settings);
    assert.ok(settings.querySelector('#statistics-basis'));
    const inlineCSS = [...d.querySelectorAll('head style')].map(s => s.textContent).join('\n');
    const rule = /\.goal-title\s*\{([^}]+)\}/.exec(inlineCSS)?.[1];
    assert.ok(rule, 'actual goals.html title rule exists');
    assert.match(rule, /position:\s*static\s*;/, 'absolute heading must return to document flow');
    assert.doesNotMatch(rule, /\b(?:left|top):/, 'obsolete absolute offsets removed');
    assert.ok(d.querySelector('.charts-container .chart-box #goalChart'));
    assert.ok(d.querySelector('.charts-container .chart-box #monthlyChart'));
  } finally {
    dom.window.close();
  }
});

const preservedSelectors = {
  'index.html': ['.login-container', '.password-container', '#login-form', '.login-btn'],
  'register.html': ['.register-container .register-box', '.input-group input', '.register-btn'],
  'find-account.html': ['.find-account-container', '.find-section', '.find-btn', '#reset-section'],
  'review-write.html': ['.review-container > .book-info', '.review-content .review-box', '.stars .star', '.review-text', '.review-actions .publish-button'],
  'review-detail.html': ['.review-container > .book-info', '.review-content .review-box', '.review-rating-container', '.review-actions .action-button', '.comment-section .comment-input-container', '#comment-input', '#comment-list'],
};
for (const name of fs.readdirSync(path.join(root, 'screen')).filter(n => n.endsWith('.html'))) {
  test(`${name}: additive CSS는 head 끝에 한 번 연결하고 기존 class를 보존한다`, () => {
    const dom = mount(name);
    try {
      const d = dom.window.document;
      const links = d.querySelectorAll('head link[href="../styles/layout-fixes.css"]');
      assert.equal(links.length, 1, 'one shared layout-fixes stylesheet link required');
      assert.equal(links[0].rel, 'stylesheet');
      assert.equal(d.head.lastElementChild, links[0], 'must follow existing inline styles');
      assert.ok(d.querySelector('head link[href$="global.css"]'), 'original stylesheet retained');
      if (name === 'welcome.html') {
        assert.ok(d.querySelector('.welcome-container .welcome-logo'));
        assert.ok(d.querySelector('.welcome-container .main-page-button'));
      } else {
        assert.ok(d.querySelector('.navbar .logo .logo-text .first'));
        if (name === 'search.html') {
          assert.ok(d.querySelector('.navbar .search-bar'));
          assert.ok(d.querySelector('.search-container .results-grid'));
        } else {
          assert.ok(d.querySelector('.nav-links'));
          assert.ok(d.querySelector('.user-actions'));
        }
      }
      for (const selector of preservedSelectors[name] || []) assert.ok(d.querySelector(selector), selector);
    } finally {
      dom.window.close();
    }
  });
}

function mobileRules() {
  const file = path.join(root, 'styles', 'layout-fixes.css');
  assert.ok(fs.existsSync(file), 'additive mobile stylesheet exists');
  const css = fs.readFileSync(file, 'utf8');
  assert.doesNotMatch(css, /overflow(?:-x|-y)?\s*:\s*(?:hidden|clip)/i, 'do not hide overflow controls');
  const dom = new JSDOM('<!doctype html><head></head><body></body>');
  try {
    const style = dom.window.document.createElement('style');
    style.textContent = css;
    dom.window.document.head.append(style);
    const sheets = [...style.sheet.cssRules];
    assert.equal(sheets.length, 1, 'no desktop/global overrides');
    assert.equal(sheets[0].conditionText, '(max-width: 768px)');
    const rules = [...sheets[0].cssRules];
    for (const rule of rules) {
      assert.doesNotMatch(rule.cssText, /(?:^|[;{])\s*(?:color|background[^:]*|font[^:]*|display|visibility)\s*:/i, 'preserve design and control visibility');
    }
    return rules;
  } finally {
    dom.window.close();
  }
}
function declaration(rules, selector, property) {
  const rule = rules.find(r => r.selectorText.split(',').map(s => s.trim()).includes(selector));
  assert.ok(rule, `targeted rule for ${selector}`);
  return rule.style.getPropertyValue(property);
}
test('모바일 로그인/복구 padding과 회원가입 입력은 border-box로 화면 안에 포함한다', () => {
  const rules = mobileRules();
  for (const s of ['.login-container', '.find-account-container', '.register-box', '.register-box .input-group input']) {
    assert.equal(declaration(rules, s, 'box-sizing'), 'border-box');
  }
});
test('모바일 리뷰 두 패널은 쌓이고 padding과 textarea를 border-box로 포함한다', () => {
  const rules = mobileRules();
  assert.equal(declaration(rules, '.review-container', 'flex-direction'), 'column');
  for (const s of ['.review-container > .book-info', '.review-container > .review-content', '.review-container .review-box', '.review-container .review-text']) {
    assert.equal(declaration(rules, s, 'box-sizing'), 'border-box');
  }
});
test('모바일 댓글/별점/수정삭제는 wrap하고 긴 텍스트는 줄바꿈한다', () => {
  const rules = mobileRules();
  for (const s of ['.review-container .comment-input-container', '.review-container .comment-content', '.review-container .review-rating-container', '.review-container .review-actions']) {
    assert.equal(declaration(rules, s, 'flex-wrap'), 'wrap');
  }
  for (const s of ['.review-container #comment-input', '.review-container .comment-info']) {
    assert.equal(declaration(rules, s, 'min-width'), '0');
  }
  assert.equal(declaration(rules, '.review-container .comment-info', 'overflow-wrap'), 'anywhere');
});
