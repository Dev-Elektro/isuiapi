from datetime import datetime
import requests
from requests.models import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
import re
from loguru import logger as log

from exceptions import SessionTimedOut, ServerNotResponding, IncorrectLoginOrPassword, AuthorisationError, \
    ErrorStartTask
from utils import parserTasksList, parseCSRF, parsePlatformIT
from _types import Task, TasksList, CommentType, TaskCloseType, StopTaskResponse, TaskResponse, TaskType, TaskTypesGroup


class ISUI(object):
    def __init__(self, login=None, password=None):
        self._datetime_close = None
        self.httpAdapter = HTTPAdapter(max_retries=2)
        self.httpSession = requests.Session()
        self.httpSession.mount("https://helpdesk.efko.ru", self.httpAdapter)
        self.httpSession.headers.update({'origin': "https://helpdesk.efko.ru",
                                         'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors',
                                         'sec-fetch-site': 'same-origin',
                                         'user-agent': 'Chrome/102.0.5005.63 Safari/537.36'})
        self.ssl_check = True
        self.user_id = None
        self.login = login
        self.password = password
        self._csrf = None

    def setAccount(self, login: str, password: str):
        self.login = login
        self.password = password

    @staticmethod
    def _response_check(response_text: str) -> None:
        """Проверка ответа от сервера на исключительные состояния"""
        if 'Время сессии истекло' in response_text:
            raise SessionTimedOut
        if 'Сервер не отвечает' in response_text:
            raise ServerNotResponding
        if 'Неправильный логин или пароль' in response_text:
            raise IncorrectLoginOrPassword

    def _get(self, url: str, data: dict = None, params: dict = None) -> Response:
        """Загрузка страницы методом GET"""
        try:
            response = self.httpSession.get(url, data=data, params=params, verify=self.ssl_check)
            response.raise_for_status()
        except HTTPError:
            raise ServerNotResponding
        self._response_check(response.text)
        return response

    def _post(self, url: str, data: dict = None, params: dict = None) -> Response:
        """Загрузка страницы методом POST"""
        try:
            response = self.httpSession.post(url, data=data, params=params, verify=self.ssl_check)
            response.raise_for_status()
        except HTTPError:
            raise ServerNotResponding()
        self._response_check(response.text)
        return response

    def authorization(self) -> None:
        """Авторизация на сервере ИСУИ"""
        query_data = {'login': self.login,
                      'password': self.password,
                      'mypage': ''}

        response = self._post("https://helpdesk.efko.ru/login.php", data=query_data)
        self.user_id = re.sub(r'(?i)[^0-9]*', '', response.url)
        csrf_token = re.findall(r'<meta name="csrf-token" content="(\w.+)">', response.text)
        if len(self.user_id) != 8 and len(csrf_token) != 1:
            raise AuthorisationError
        self.httpSession.headers.update({'x-csrf-token': csrf_token[0]})
        self.httpSession.headers.update({'x-requested-with': 'XMLHttpRequest'})

    def getTasksList(self, user_id: str = None) -> TasksList[Task]:
        if not user_id:
            user_id = self.user_id
        params = {'userCode': user_id, 'per-page': 200}
        res = self._post("https://helpdesk.efko.ru/tasks/user/allowed-break-task", params=params)
        return parserTasksList(res.text)

    def startTask(self, task: Task):
        if task.user_id != self.user_id:
            raise ErrorStartTask("Попытка запуска не своей задачи.")
        params = {'code': task.id, 'task': task.request_id, 'launched': 0}
        res = self._get("https://helpdesk.efko.ru/tasks/tool/run", params=params)
        if not res.headers.get('Content-Type').startswith("application/json"):
            raise ErrorStartTask("Непредвиденный ответ от сервера.")

        response = TaskResponse(**res.json())
        if response.status != 1:
            raise ErrorStartTask("Задача не запущена, возможно не поставлена в ожидание предыдущая задача.")

    def _checkTimeOut(self, time: int) -> bool:
        """Проверяет установленно ли время закрытия задачи и не превысило ли указанный интервал в минутах."""
        if not self._datetime_close:
            return True
        td = datetime.now() - self._datetime_close
        if td.total_seconds() > time * 60:
            return True
        return False

    def prepareTaskForClose(self, task: Task) -> StopTaskResponse:
        """Подготовка к закрытию задачи, запоминает время, получает токен и
        проверяет на необходимость указания типа закрытия задачи TaskCloseType"""
        params = {'code': task.id}
        res = self._get("https://helpdesk.efko.ru/tasks/tool/complete", params=params)
        if not res.headers.get('Content-Type').startswith("application/json"):
            raise ErrorStartTask("Непредвиденный ответ от сервера.")
        response = TaskResponse(**res.json())
        if response.status == 2:
            self._csrf = parseCSRF(response.message)
            self._datetime_close = datetime.now()
        if response.status == 2 and "требуется продолжение работ" in response.message:
            return StopTaskResponse.WAITING_CHOICE
        if response.status == 2 and "необходимо оставить комментарии" in response.message:
            return StopTaskResponse.WAITING_COMMENT
        raise ErrorStartTask("Непредвиденный ответ от сервера.")

    def closeTask(self, task: Task, comment: str, comment_type: CommentType, choice: TaskCloseType = None):
        """Закрывает задачу. Принимает задачу (Task), комментарий (str),
        тип комментария (CommentType) и при необходимости тип закрытия задачи (TaskCloseType)."""
        if self._checkTimeOut(10):
            raise ErrorStartTask("Вышло время, попробуйте заново.")
        if not self._csrf:
            raise ErrorStartTask("Необходимо выполнить prepareTaskForClose")
        params = {'code': task.id}
        data = {'_csrf': self._csrf,
                'CompleteTaskForm[taskEndTime]': self._datetime_close.strftime("%d.%m.%Y %H:%M"),
                'CompleteTaskForm[comment]': comment,
                'CompleteTaskForm[responseType]': comment_type.value}
        if choice:
            data.update({'CompleteTaskForm[lastTaskStatus]': choice.value})
        res = self._post("https://helpdesk.efko.ru/tasks/tool/complete", params=params, data=data)
        self._csrf = None
        if not res.headers.get('Content-Type').startswith("application/json"):
            raise ErrorStartTask("Непредвиденный ответ от сервера.")
        response = TaskResponse(**res.json())
        if response.status == 0:
            return response.message
        raise ErrorStartTask("Ошибка закрытия задачи.")

    def addTask(self, request_id: str, description: str, task_type: TaskType):
        params = {'taskCode': request_id}
        res = self._get("https://helpdesk.efko.ru/tasks/tool/insert-task", params=params)
        self._csrf = parseCSRF(res.text)
        platform_it_id = parsePlatformIT(res.text)
        data = {'_csrf': self._csrf,
                'mode-hidden': 'employee',
                'InsertBreakTaskForm[mode]': 'employee',
                'InsertBreakTaskForm[description]': description,
                'InsertBreakTaskForm[informationBaseCode]': '',
                'InsertBreakTaskForm[taskType]': task_type.id,
                'InsertBreakTaskForm[platformIt]': platform_it_id,
                'InsertBreakTaskForm[customer]': self.user_id}
        res = self._post("https://helpdesk.efko.ru/tasks/tool/insert-task", params=params, data=data)
        self._csrf = None
        response = TaskResponse(**res.json())
        if response.status == 1:
            return response.message
        raise ErrorStartTask("Ошибка добавления задачи.")

    def searchTaskTypeByName(self, query: str) -> list[TaskTypesGroup]:
        params = {'groupParent': 1, 'q': query}
        res = self._get("https://helpdesk.efko.ru/tasks/search/search-task-type-by-name", params=params)
        if not res.headers.get('Content-Type').startswith("application/json"):
            raise ErrorStartTask("Непредвиденный ответ от сервера.")
        buf = res.json()
        buf = buf['results']
        list_task_types_list = []
        for group in buf:
            list_type = []
            for i in group['children']:
                list_type.append(TaskType(**i))
            list_task_types_list.append(TaskTypesGroup(group['text'], list_type))
        return list_task_types_list

    def searchTaskTypeByID(self, type_id: str) -> TaskType:
        buf = self.searchTaskTypeByName("")
        for group in buf:
            for task_type in group.task_types:
                if task_type.id == type_id:
                    return task_type


if __name__ == "__main__":
    pass
