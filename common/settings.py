import json

from common.helper import Singleton


class Settings(object, metaclass=Singleton):
    class _SubSetting(object):
        @staticmethod
        def write_to_file():
            """
            Writes content back to file

            Don't use setattr since it gets called at initialization too
            """
            Settings().write_to_file()

    def __init__(self):
        self._path = "config.json"
        with open(self._path) as f:
            content = json.loads(f.read())

        self._set_value(object_to_set_to=self, content=content)

    @classmethod
    def _to_dict(cls, object_to_dicify):
        return_dic = {}
        for key, value in object_to_dicify.__dict__.items():
            if key[0] == "_":
                continue  # Skip private variables
            if isinstance(value, cls._SubSetting):
                return_dic[key] = cls._to_dict(value)
            else:
                return_dic[key] = value
        return return_dic

    def __str__(self):
        return str(self._to_dict(self))

    @classmethod
    def _set_value(cls, object_to_set_to, content: dict):
        """
        Recursively set keys and values from dictionary
        """
        for key, value in content.items():
            if isinstance(value, dict):
                sub_setting = cls._SubSetting()
                setattr(object_to_set_to, key, sub_setting)
                cls._set_value(object_to_set_to=sub_setting, content=value)
            else:
                setattr(object_to_set_to, key, value)

    def write_to_file(self):
        """
        Writes content back to file
        """
        content = json.dumps(self._to_dict(self), indent=2)
        with open(self._path, "w") as f:
            f.write(content)
