from pip._vendor.six import add_metaclass


class CommandRegistry(type):
    registry = {}

    @classmethod
    def add_command(cls, command_model):
        name = command_model.__name__
        if name != 'Command':
            cls.registry[command_model.__name__] = command_model

    def __init__(cls, name, bases, attrs):
        super(CommandRegistry, cls).__init__(name, bases, attrs)
        CommandRegistry.add_command(cls)

    @classmethod
    def get_commands(cls):
        return cls.registry.values()


@add_metaclass(CommandRegistry)
class Command(object):
    def _make_manager(self, kw):
        """
        Creates a fake ``manage`` object to implement clean
        API for the management commands.

        Args:
            kw: keyword args to be construct fake manage.args object.

        Returns:
            Fake manage object.
        """
        for param in self.PARAMS:
            if param['name'] not in kw:
                store_true = 'action' in param and param['action'] == 'store_true'
                kw[param['name']] = param.get('default', False if store_true else None)
        return type('FakeCommandManager', (object,),
                    {
                        'args': type('args', (object,), kw)
                    })

    def __init__(self, manager=None, **kwargs):
        self.manager = manager or self._make_manager(kwargs)

    def run(self):
        """
        This is where the things are done.
        You should override this method in your command class.
        """
        raise NotImplemented("You should override this method in your command class")

