import yaml

class Config():
    """Class that reads configuration from various (potentially) sources"""
    def __init__(self):
        self.loaded_config = None

    def load_from_file(self, path):
        """loads the config from a file"""
        with open(path, 'r', 1, 'utf8') as f:
            self.loaded_config = yaml.load(f, Loader=yaml.FullLoader)
        return self

    def load_from_dict(self, data):
        """loads configuration data from a dictionary"""
        self.loaded_config = data
        return self

    def get_config(self):
        """Returns a dictionary of configuration settings"""
        return self.loaded_config
