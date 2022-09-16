import re
from datetime import datetime
from bs4 import BeautifulSoup

from _types import TasksList, Task, TaskWait, Initiator


def parserTasksList(html: str) -> TasksList[Task]:
    """Парсинг html странницы с задачами."""
    soup = BeautifulSoup(html.replace('\\"', '"'), 'lxml')
    html = soup.find_all('tr')
    tasks_list = TasksList()
    for html_task in html[2:]:
        body = html_task.find_all('td')
        links = body[0].find_all('a')

        task_id = body[1].find_all('div', {'class': 'task-description-code'})[0].get_text()
        task = Task(task_id)
        if 'current-task-row' in html_task.attrs['class']:
            task.run = True
        task.request_id = links[0].get_text()
        task.initiator = Initiator(re.sub(r'(?i)[^0-9]*', '', links[1].get('href')), links[1].get_text())
        task.text = body[1].find_all('div', {'class': 'task-description'})[0].get_text(separator='\n', strip=True)
        task.date = body[2].get_text()
        task.type = body[3].get_text('|').split('|')[1]
        task.time = body[4].get_text(strip=True)
        task.plan = body[5].get_text(strip=True)
        wait_type = body[6].select_one("div:nth-child(2) > div > div:nth-child(1)")
        wait_date = body[6].select_one("div:nth-child(2) > div > div:nth-child(3)")
        if wait_type:
            task_wait = TaskWait(*wait_type.get_text(strip=True).split(':'))
            if wait_date:
                date_str = re.findall(r"^.*(\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2})$", wait_date.get_text(strip=True))
                if date_str:
                    task_wait.datetime = datetime.strptime(date_str[0], "%d.%m.%Y %H:%M")
            task.wait = task_wait
        task.user_id = body[6].select_one("div > button:nth-child(1)").get('data-employee-code')
        tasks_list.append(task)
    return tasks_list


def parseCSRF(html: str) -> str:
    """Получение csrf из html form"""
    soup = BeautifulSoup(html.replace('\\"', '"'), 'lxml')
    csrf = soup.select_one('input[name="_csrf"]')
    if csrf:
        return csrf.get('value')


def parsePlatformIT(html: str) -> str:
    """Получить ID площадки IT"""
    soup = BeautifulSoup(html.replace('\\"', '"'), 'lxml')
    select = soup.find('select', {'id': 'insert-task-platform-it'})
    platform = select.select_one('option[selected]')
    if platform:
        return platform.get('value')
