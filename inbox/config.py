import json
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri']


class ConfigError(Exception):
    def __init__(self, error=None, help=None):
        self.error = error or ''
        self.help = help or \
            'Run `sudo cp etc/config-dev.json /etc/inboxapp/config.json` and '\
            'retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


class Configuration(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def get_required(self, key):
        if key not in self:
            raise ConfigError('Missing config value for {0}.'.format(key))

        return self[key]


with open('/etc/inboxapp/config.json') as f:
    config = Configuration(json.load(f))


def engine_uri(database=None):
    """ By default doesn't include the specific database. """
    username = config.get_required('MYSQL_USER')
    password = config.get_required('MYSQL_PASSWORD')
    host = config.get_required('MYSQL_HOSTNAME')
    port = config.get_required('MYSQL_PORT')

    uri_template = 'mysql+pymysql://{username}:{password}@{host}' +\
                   ':{port}/{database}?charset=utf8mb4'

    return uri_template.format(
        username=username,
        # http://stackoverflow.com/a/15728440 (also applicable to '+' sign)
        password=urlquote(password),
        host=host,
        port=port,
        database=database if database else '')


def db_uri():
    database = config.get_required('MYSQL_DATABASE')
    return engine_uri(database)
