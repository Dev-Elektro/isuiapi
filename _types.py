from enum import Enum
from dataclasses import dataclass
from typing import NamedTuple, Union

import datetime as datetime


class StopTaskResponse(Enum):
    WAITING_COMMENT = "При завершении задачи необходимо оставить комментарии к выполненной работе."
    WAITING_CHOICE = "По заявке требуется продолжение работ другими сотрудниками?"


class CommentType(Enum):
    DEFAULT = "0"
    INTERNAL = "2"
    DISPATCHER = "4"
    MANAGER = "5"


class TaskCloseType(Enum):
    CLOSE = "Close"
    CONTINUE = "AsIs"
    REJECTED = "Denied"


class TaskResponse(NamedTuple):
    status: int
    message: str


class Initiator(NamedTuple):
    """Описание инициатора заявки"""
    id: str
    name: str


@dataclass
class TaskWait:
    type: str
    description: str
    datetime: Union[datetime, None] = None


@dataclass
class Task:
    id: str
    run: bool = False
    request_id: str = None
    initiator: Initiator = None
    text: str = None
    date: str = None
    type: str = None
    time: str = None
    plan: str = None
    wait: Union[TaskWait, None] = None
    user_id: str = None


class TasksList(list):
    def append(self, task: Task) -> None:
        if not isinstance(task, Task):
            raise TypeError(f"Ожидался тип объекта: {Task}")
        super(TasksList, self).append(task)

    def getRunningTask(self) -> Union[Task, None]:
        """Возвращает запущенную задачу."""
        for i in self:
            if i.run:
                return i

    def getTaskByID(self, task_id: str) -> Union[Task, None]:
        """Возвращает задачу по ее ID."""
        for i in self:
            if i.id == task_id:
                return i


class TaskType(NamedTuple):
    id: str
    text: str
    disabled: bool = False


@dataclass
class TaskTypesGroup:
    name: str
    task_types: list[TaskType]
