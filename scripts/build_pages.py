"""Build an allowlisted Pages artifact; never publish the repository root."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in ('screen', 'scripts', 'styles', 'assets'):
        shutil.copytree(ROOT / 'frontend' / name, OUT / name)
    profiles = OUT / 'media' / 'profile_images'
    profiles.mkdir(parents=True)
    for suffix in ('', '1', '2', '3', '4', '5'):
        name = f'profile_image{suffix}.svg'
        shutil.copyfile(ROOT / 'backend/media/profile_image' / name, profiles / name)
    icons = OUT / 'media' / 'icons'
    icons.mkdir()
    for name in ('arrow_seeall.svg', 'edit_emoji.svg', 'heart_empty.svg', 'heart_full.svg',
                 'review_star.svg', 'star_empty.svg', 'star_full.svg', 'star_half.svg'):
        shutil.copyfile(ROOT / 'backend/media/icons' / name, icons / name)
    (OUT / '_redirects').write_text('/ /screen/main.html 302\n')
    (OUT / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>다독다독</title><meta http-equiv="refresh" content="0;url=/screen/main.html"><a href="/screen/main.html">다독다독 홈</a></html>')
    (OUT / '_headers').write_text('/*\n  X-Content-Type-Options: nosniff\n  X-Frame-Options: DENY\n  Referrer-Policy: no-referrer\n  Cache-Control: no-cache\n')
    (OUT / '_routes.json').write_text(json.dumps({'version': 1, 'include': ['/api/*'], 'exclude': []}))
    (OUT / '404.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>페이지 없음</title><p>페이지를 찾을 수 없습니다.</p><a href="/">다독다독 홈</a></html>')
    print('Pages artifact built in dist (frontend, six profile SVGs and eight fixed icons only).')


if __name__ == '__main__':
    build()
