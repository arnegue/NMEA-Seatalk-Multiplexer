import json

from common.helper import Singleton


class Settings(object, metaclass=Singleton):
    class _SubSetting(object):
        pass

    def __init__(self):
        with open("config.json") as f:
            content = json.loads(f.read())

        self.set_value(self, content)

    @classmethod
    def set_value(cls, object_to_set_to, content: dict):
        """
        Recursively set keys and values from dictionary
        """
        for key, value in content.items():
            if isinstance(value, dict):
                sub_setting = cls._SubSetting()
                setattr(object_to_set_to, key, sub_setting)
                cls.set_value(sub_setting, value)
            else:
                setattr(object_to_set_to, key, value)


settings = Settings()
