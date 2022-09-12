import json
import os
from pathlib import Path
from typing import Any, Dict

from xdg import xdg_cache_home


class Persistent:

    cache_file: Path
    cache_data: Dict[str, Any]

    _cache_names = {
        'open_file_path',
        'open_file_filter',
        'main_splitter_left',
        'main_splitter_right',
    }

    _defaults = {
        'open_file_path': os.getcwd,
        'open_file_filter': lambda: 'G2 files (*.g2)',
        'main_splitter_left': lambda: 500,
        'main_splitter_right': lambda: 100,
    }

    def __enter__(self):
        cache_home = xdg_cache_home()
        cache_home.mkdir(parents=True, exist_ok=True)

        self.cache_file = cache_home / 'scout.json'
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                self.cache_data = json.load(f)
        else:
            self.cache_data = dict()

        return self

    def __exit__(self, *args):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache_data, f)

    def __getattr__(self, key: str):
        if key in self._cache_names:
            return self.cache_data.get(key, self._defaults[key]())
        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any):
        if key in self._cache_names:
            self.cache_data[key] = value
            return
        self.__dict__[key] = value
