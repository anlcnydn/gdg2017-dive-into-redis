from gdg.command import CommandRegistry
from argparse import HelpFormatter


class SmartFormatter(HelpFormatter):
    def _split_lines(self, text, width):
        # this is the RawTextHelpFormatter._split_lines
        if text.startswith('R|'):
            return text[2:].splitlines()
        return HelpFormatter._split_lines(self, text, width)


class ManagementCommands(object):
    """
    All management commands executed by this class.
    You can create your own commands by extending Command class
    """

    def __init__(self, args=None):
        self.report = ""
        self.commands = CommandRegistry.get_commands()
        if args:
            input = args
        else:
            input = ['-h']
        self.parse_args(input)
        self.args.command()

    def parse_args(self, args):
        import argparse
        parser = argparse.ArgumentParser(formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(title='Possible commands')
        for cmd_class in self.commands:
            cmd = cmd_class(self)
            sub_parser = subparsers.add_parser(cmd.CMD_NAME, help=getattr(cmd, 'HELP', None),
                                               formatter_class=SmartFormatter)
            sub_parser.set_defaults(command=cmd.run)
            if hasattr(cmd, 'PARAMS'):
                for params in cmd.PARAMS:
                    param = params.copy()
                    name = "-%s" % param.pop("name")
                    # params['des']
                    if 'action' not in param:
                        param['nargs'] = '?'
                    sub_parser.add_argument(name, **param)

        self.args = parser.parse_args(args)

