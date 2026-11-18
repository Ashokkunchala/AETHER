"""Coverage for source-linked added tracks, not a claim of teaching efficacy."""
import pytest

from aether.mentor_deep import DeepMentor, TRACKS, _lesson
from aether.mentor_tracks import EXTRA_TRACKS


def test_all_tracks_have_three_complete_distinct_scenarios():
    assert len(TRACKS) == 12 and len(EXTRA_TRACKS) == 8
    ids = {row['id'] for row in DeepMentor.catalog()}
    assert len(ids) == 36
    for key, (source, lessons) in TRACKS.items():
        assert source.startswith('https://') and len(lessons) == 3
        assert len({r[0] for r in lessons}) == 3
        for number, row in enumerate(lessons, 1):
            assert len(row) == 6
            title, scenario, notes, options, correct, lab = row
            assert all(isinstance(text, str) and text.strip() for text in [title, scenario, notes, lab])
            assert len(options) == 3 and len(set(options)) == 3
            assert 0 < len(correct) < len(options)
            assert len(set(correct)) == len(correct) and all(type(i) is int and 0 <= i < len(options) for i in correct)
            assert _lesson(f'{key}-{number}') == (key, number, row)


@pytest.mark.parametrize('key', ['unknown-1', 'python-0', 'python-01', 'python-4', 'python-1-extra', 'ai-safety-4', None, 1, 'a' * 100])
def test_dynamic_catalog_does_not_allow_arbitrary_ids(key):
    with pytest.raises(ValueError):
        _lesson(key)


def test_hyphenated_track_id_is_stable():
    row = next(r for r in DeepMentor.catalog() if r['id'] == 'ai-safety-2')
    assert row['prerequisite'] == 'ai-safety-1'
    assert _lesson(row['id'])[0] == 'ai-safety'
