class SessionTimedOut(Exception):
    """Время сессии истекло, необходима авторизация"""
    def __init__(self, message: str = "Время сессии истекло") -> None:
        self.message = message
        super(SessionTimedOut, self).__init__(self.message)


class ServerNotResponding(Exception):
    """Сервер ИСУИ не отвечает"""
    def __init__(self, message: str = "Сервер ИСУИ не отвечает") -> None:
        self.message = message
        super(ServerNotResponding, self).__init__(self.message)


class IncorrectLoginOrPassword(Exception):
    """Неправильный логин или пароль"""
    def __init__(self, message: str = "Неправильный логин или пароль") -> None:
        self.message = message
        super(IncorrectLoginOrPassword, self).__init__(self.message)


class AuthorisationError(Exception):
    """Ошибка авторизации"""
    def __init__(self, message: str = "Ошибка авторизации") -> None:
        self.message = message
        super(AuthorisationError, self).__init__(self.message)


class ErrorStartTask(Exception):
    """Ошибка запуска задачи"""
    def __init__(self, message: str = "Ошибка запуска задачи") -> None:
        self.message = message
        super(ErrorStartTask, self).__init__(self.message)
