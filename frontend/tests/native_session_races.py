"""Actual screen/scripts, Chromium native shared storage/locks; synthetic fetch only.
Use .venv-dev, with the isolated Playwright tool directory on PYTHONPATH.
No original DB, production API, Naver, SMTP, package or Git writes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--cdn-cache', type=Path, required=True)
parser.add_argument('--baseline-directory', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
shutil.copytree(args.cdn_cache, args.output / 'assets' / 'cdn-cache', dirs_exist_ok=True)
spec = importlib.util.spec_from_file_location('dadok_native_smoke', ROOT / 'tests/browser_smoke.py')
assert spec is not None and spec.loader is not None
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
assets, cdn = smoke.obtain_assets(args.output / 'assets', False)
(args.output / 'isolated-http' / 'screenshots').mkdir(parents=True, exist_ok=True)
h = smoke.Harness(args.output / 'isolated-http', assets, cdn)
from playwright.sync_api import sync_playwright

INIT = r"""(() => {
    if (!localStorage.getItem('dadok_session_epoch')) {
        localStorage.setItem('dadok_session_epoch', 'synthetic-A-boundary');
        localStorage.setItem('token', 'A-access'); localStorage.setItem('refresh_token', 'A-refresh'); localStorage.setItem('username', 'A');
    }
    window.alert = () => {}; window.confirm = () => true;
    window.sent = [];
    window.reply = (data, status=200) => ({ok:status>=200&&status<300,status,json:async()=>data,text:async()=>JSON.stringify(data)});
    window.fetch = async (url, init={}) => {
        const path = new URL(url).pathname; window.sent.push({path,method:init.method||'GET'});
        if (path.endsWith('/me/')) return reply({id:1,nickname:'private-A',email:'synthetic-A@example.test',profile_image:''});
        if (path.includes('/goal/goal/')) return reply([]);
        if (path.includes('/progress/')) return reply({goal_id:2,goal_books:10,read_books:3});
        if (path.includes('monthly-progress')) return reply({monthly_reading:{}});
        if (path.includes('/isbn/')) return reply({isbn:'123',title:'public title'});
        if (path.includes('/review/1/')) return reply({id:1,isbn:'123',content:'private-draft',user_nickname:'private-A',rating:4});
        return reply([]);
    };
})()"""
results = []

def seed(page, account='B'):
    page.evaluate("name => AppAPI.saveSession({access_token:name+'-access',refresh_token:name+'-refresh',user:{nickname:name}})", account)

def pair_is(page, account):
    return page.evaluate("name => localStorage.getItem('token')===name+'-access' && localStorage.getItem('refresh_token')===name+'-refresh'", account)

def pages(browser, screen='index.html'):
    a = h.new_page(browser)
    context = a.context
    context.set_default_timeout(5000)
    a.set_default_timeout(5000)
    context.add_init_script(INIT)
    if args.baseline_directory:
        def baseline(route):
            name = Path(route.request.url.split('?')[0]).name
            file = args.baseline_directory / name
            if file.exists(): route.fulfill(body=file.read_bytes(), content_type='text/javascript')
            else: route.fallback()
        context.route('**/scripts/*.js', baseline)
    h.goto(a, screen)
    b = context.new_page(); h.goto(b, 'index.html')
    return context, a, b

def check(name, action, browser, screen='index.html'):
    context, a, b = pages(browser, screen)
    try:
        action(a, b)
        result = {'case':name,'status':'pass'}
    except Exception as exc:
        # Do not echo credentials, payloads or private DOM in assertion diagnostics.
        result = {'case':name,'status':'fail','exception':type(exc).__name__}
    finally:
        context.close()
    results.append(result); print(json.dumps(result, ensure_ascii=False), flush=True)

def late_refresh(a, b, logout=False):
    a.evaluate("""() => { window.fetch=()=>new Promise(resolve=>window.release=()=>resolve(reply({access:'A-late',refresh:'A-rotated'}))); window.done=false; AppAPI.refresh().catch(()=>{}).finally(()=>window.done=true); }""")
    if logout:
        # Start without awaiting: another tab owns the pending refresh network lock.
        b.evaluate("() => { window.logoutDone=false; AppAPI.logout().finally(()=>window.logoutDone=true); }")
    else: seed(b)
    a.evaluate('release()'); a.wait_for_function('window.done')
    if logout:
        # Successful logout navigates B; its page-local completion flag is not durable.
        a.wait_for_function("localStorage.getItem('token')===null && localStorage.getItem('refresh_token')===null")
    else: assert pair_is(a, 'B')

def old_401(a, b, logout=False):
    a.evaluate("""logout => {
        let calls=0; window.done=false; window.sent=[];
        window.fetch=async (url,init={})=>{
            const path=new URL(url).pathname; window.sent.push({path});
            if(path.endsWith('/refresh/')) return reply({access:'A-renewed'});
            if(!logout && ++calls===1) return reply({},401);
            return new Promise(resolve=>window.release=()=>resolve(reply({},401)));
        };
        (logout ? AppAPI.logout() : AppAPI.request('/api/user/me/')).catch(()=>{}).finally(()=>window.done=true);
    }""", logout)
    a.wait_for_function('typeof window.release==="function"'); seed(b)
    before = a.url
    a.evaluate('release()'); a.wait_for_function('window.done')
    assert pair_is(a, 'B'); assert a.url == before
    if logout: assert a.evaluate('sent.length===1')

def stale_form(a, b):
    a.wait_for_function("document.querySelector('#save-profile').disabled===false")
    seed(b)
    a.wait_for_function("document.querySelector('#user-nickname').value==='' && document.querySelector('#save-profile').disabled")
    a.evaluate("document.querySelector('#save-profile').dispatchEvent(new Event('click'))")
    assert a.evaluate("sent.every(x=>x.method==='GET')")
    assert pair_is(a, 'B')

def private_dom(a, b):
    a.wait_for_function("document.querySelector('#user-email').value!==''")
    seed(b)
    a.wait_for_function("document.querySelector('#user-email').value==='' && document.querySelector('.set-goal-btn').disabled")
    assert pair_is(a, 'B')

def late_login_body(a, b):
    a.evaluate("""() => { window.fetch=async()=>({...reply({}),json:()=>new Promise(resolve=>window.release=()=>resolve({access_token:'A-late',refresh_token:'A-late-refresh',user:{nickname:'A'}}))}); }""")
    a.locator('#username').fill('synthetic'); a.locator('#password').fill('synthetic-only')
    a.locator('#login-form').evaluate("form=>form.dispatchEvent(new Event('submit',{cancelable:true}))")
    a.wait_for_function('typeof window.release==="function"'); seed(b)
    a.evaluate('release()'); a.wait_for_timeout(100)
    assert pair_is(a, 'B'); assert a.url.endswith('index.html')

def commit_lock(a, b):
    b.evaluate("""() => { window.locked=false; navigator.locks.request('dadok-session-write',()=>new Promise(resolve=>{window.unlock=resolve;window.locked=true})); }""")
    b.wait_for_function('window.locked')
    try:
        a.evaluate("""() => {window.fetch=async()=>reply({access:'A-renewed',refresh:'A-rotated'});window.done=false;AppAPI.refresh().catch(()=>{}).finally(()=>window.done=true);} """)
        a.wait_for_timeout(100)
        assert pair_is(a, 'A'), 'commit must wait for native shared write lock'
    finally: b.evaluate('unlock()')
    a.wait_for_function('window.done')
    assert a.evaluate("localStorage.getItem('token')==='A-renewed' && localStorage.getItem('refresh_token')==='A-rotated'")

def cross_tab_rotation_logout(a, b):
    a.evaluate("""() => {window.fetch=()=>new Promise(resolve=>window.release=()=>resolve(reply({access:'A-renewed',refresh:'A-rotated'})));window.done=false;AppAPI.refresh().catch(()=>{}).finally(()=>window.done=true);} """)
    b.evaluate("""() => {
        window.fetch=async (url,init)=>{localStorage.setItem('probe-revoked-rotation',String(JSON.parse(init.body).refresh_token==='A-rotated'));return reply({})};
        AppAPI.logout();
    }""")
    a.wait_for_timeout(100)
    assert a.evaluate("localStorage.getItem('probe-revoked-rotation')===null"), 'logout must wait for owned cross-tab rotation'
    a.evaluate('release()'); a.wait_for_function('window.done')
    a.wait_for_function("localStorage.getItem('token')===null && localStorage.getItem('probe-revoked-rotation')==='true'")

try:
    with smoke.loopback_only():
        h.start_servers()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--disable-background-networking','--disable-component-update','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost'])
            version = browser.version
            check('B1_native_logout_late_refresh', lambda a,b:late_refresh(a,b,True), browser)
            check('B1_native_switch_late_refresh', late_refresh, browser)
            check('B1_native_loaded_A_profile_B_write_gate', stale_form, browser, 'mypage_edit.html')
            check('B2_native_loaded_private_DOM_cleanup', private_dom, browser, 'mypage.html')
            check('B2_native_late_login_JSON_after_B_switch', late_login_body, browser)
            check('B3_native_late_retry_401_preserves_B', old_401, browser)
            check('B4_native_late_logout_401_preserves_B_no_redirect', lambda a,b:old_401(a,b,True), browser)
            check('B1_native_atomic_commit_uses_shared_Web_Lock', commit_lock, browser)
            check('B4_native_logout_waits_cross_tab_owned_rotation', cross_tab_rotation_logout, browser)
            browser.close()
finally:
    h.shutdown()
summary = {'tests':results,'counts':{'total':len(results),'pass':sum(x['status']=='pass' for x in results),'fail':sum(x['status']=='fail' for x in results)},'chromium':version,'django':h.report['django_version'],'own_servers_shutdown':h.report['own_servers_shutdown'],'original_db_unchanged':h.report.get('original_db_unchanged'),'substitutions':['Synthetic fetch responses only; actual HTML/scripts, native localStorage/storage events/Web Locks, pinned actual Chart.js'],'baseline_replay':bool(args.baseline_directory)}
(args.output / 'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='tests'},ensure_ascii=False,indent=2))
sys.exit(0 if not summary['counts']['fail'] and summary['own_servers_shutdown'] else 1)
