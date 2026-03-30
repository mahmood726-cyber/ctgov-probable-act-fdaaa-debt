import json
from pathlib import Path


def test_repository_smoke():
    root = Path(__file__).resolve().parents[1]
    submission = root / 'e156-submission'
    assets = submission / 'assets'

    for name in ('config.json', 'paper.md', 'protocol.md', 'index.html'):
        assert (submission / name).exists(), name

    assert (assets / 'dashboard.html').exists()
    assert (root / 'dashboard.html').exists()

    config = json.loads((submission / 'config.json').read_text(encoding='utf-8'))
    assert len(config.get('body', '').split()) == 156
    assert len(config.get('sentences', [])) == 7
    assert config.get('notes', {}).get('code')
