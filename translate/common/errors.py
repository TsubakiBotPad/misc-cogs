class NoAPIKeyException(KeyError):
    def __init__(self, fix_command, *args):
        super().__init__(fix_command, *args)
        self.fix_command = fix_command


class BadTranslation(Exception):
    def __init__(self, message, *args):
        super().__init__(message, *args)
        self.message = message
