"""阅读进度持久化测试。"""

from src.reading_progress import ReadingProgressStore


class FakeSettings:
    def __init__(self):
        self.values = {}
        self.synced = False

    def value(self, key, default=''):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def sync(self):
        self.synced = True


class TestReadingProgressStore:
    def test_round_trip(self, tmp_path):
        settings = FakeSettings()
        store = ReadingProgressStore(settings)
        file_path = str(tmp_path / 'paper.tex')

        assert store.get_page(file_path) is None
        store.set_page(file_path, 7)

        reloaded = ReadingProgressStore(settings)
        assert reloaded.get_page(file_path) == 7
        assert settings.synced is True

    def test_path_normalization(self, tmp_path):
        store = ReadingProgressStore(FakeSettings())
        file_path = str(tmp_path / 'paper.tex')

        store.set_page(file_path, 3)
        assert store.get_page(str(tmp_path / '.' / 'paper.tex')) == 3

    def test_clear(self, tmp_path):
        store = ReadingProgressStore(FakeSettings())
        file_path = str(tmp_path / 'paper.tex')

        store.set_page(file_path, 2)
        store.clear(file_path)
        assert store.get_page(file_path) is None

    def test_invalid_saved_value_is_ignored(self):
        settings = FakeSettings()
        settings.values['reading_positions'] = '{"bad": "not-a-number"}'
        store = ReadingProgressStore(settings)
        assert store.get_page('paper.tex') is None
