import requests
import os
import sys
import aiogram
import aiohttp
from aiogram import Bot, Dispatcher, types
import asyncio
from datetime import datetime
import sqlite3
import pytz # для установки часового пояса



API_TOKEN = 'tgtoken'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
date_filename = 'last_post_date.txt'  # Имя файла для хранения даты последнего поста



############################################################################################################################################################################## Логика

# метод по преобразованию даты из unix в нормальную дату с русским месяцем    
async def fromUnixToTime(date):
    tz = pytz.timezone('Europe/Moscow')  # Устанавливаем часовой пояс МСК
    formatted_datetime = datetime.fromtimestamp(date, tz=tz)
    # Форматирование времени для вывода без секунд
    formatted_string = formatted_datetime.strftime("%d.%m в %H:%M")
    return formatted_string



# метод по сохранению даты последней записи в файл
async def save_last_date_to_file(posts):
    last_date = max(post['date'] for post in posts.values())   # находим наибольшую дату (самую последнюю) из словаря и сохраняем ее в файл  
    with open(date_filename, 'w') as file:
        file.write(str(last_date))
# метод по загрузке из файла последней даты записи
async def load_date_from_file():
    with open(date_filename, 'r') as file:
        return int(file.read())
    


# метод по выводу сообщений для авторизованных пользователей
async def print_posts(new_posts): 
    with sqlite3.connect('database.db') as db:
        cursor = db.cursor()
        cursor.execute(f"""select * from users""")
        users = cursor.fetchall()

    for user in users:
        if user[1] != 'NULL': # это группа
            # await bot.send_message(chat_id=user[0], message_thread_id=user[1], text="Тест пост")
            for values in new_posts.values():
                date = await fromUnixToTime(values["date"])
                await bot.send_message(chat_id=user[0], message_thread_id=user[1], text=f'<a href="{values["link"]}">{date}</a>\n\n{values["text"]}\n\n', parse_mode='html')

        elif user[1] == 'NULL': # это пользователь
            # await bot.send_message(chat_id=user[0], text="Тест пост")
            for values in new_posts.values():
                date = await fromUnixToTime(values["date"])
                await bot.send_message(chat_id=user[0], text=f'<a href="{values["link"]}">{date}</a>\n\n{values["text"]}\n\n', parse_mode='html')
           


async def check_posts(posts):
    print(f'Работает функция check_posts')

    if os.path.getsize(date_filename) > 0: # если файл содержит предыдущую дату (последующие запросы, после первого)
        last_date = await load_date_from_file()
        # сравнить дату из файла с каждой датой из словаря, если они больше, сохранить, как новую запись
        new_posts = {}

        for values, id in zip(posts.values(), posts):
            date = values['date'] # получаем дату каждого поста из словаря
            id_post = id # получаем id каждого поста из словаря

            if last_date == date: # если дата последнего поста равна дате поста из словаря (этот пост из словаря тот же пост, чья дата сохранена в файле - не нужно сохранять)
                continue
            elif last_date > date: # если дата последнего поста больше даты поста из словаря (этот пост из словаря старее - не нужно сохранять)
                continue
            elif last_date < date: # если дата последнего поста меньше даты поста из словаря (этот пост из словаря новее - нужно сохранить и опубликовать)
                # сохранить новой записи по id в словарь для дальнейшего вывода
                new_posts[id_post] = {
                    'text': values['text'],
                    'link': values['link'],
                    'date': date
                    }
        # await print_posts(new_posts)
        if new_posts == {}: # если словарь пуст, новых постов нет
            print("Новых постов нет") 
        elif new_posts != {}: # если словарь не пуст - есть новый пост
            print('Новый пост!')
            await save_last_date_to_file(new_posts) # сохраняем дату в файл
            await print_posts(new_posts)

    elif os.path.getsize(date_filename) == 0: # если файл с датой пустой (даты нет - первый запрос), берем дату последнего поста (первого элемента в словаре) и сохраняем в файл (только при первом запуске)
        await save_last_date_to_file(posts) # сохраняем дату в файл
        print("Первый запуск. Дата последнего поста сохранена.") 



async def create_posts(data):
    global date
    posts = {}

    for i in range(0, len(data)):

        text = data[i]['text']

        if not text.startswith('Уважаемые игроки, стена закрыта до'):

            link = f'https://vk.com/wall-51036743_{data[i]["id"]}'
            date = data[i]['date'] 

            posts[i] = {
                'text': text,
                'link': link,
                'date': date
                }
        else: # если пост про закрытую стену
            continue
    await check_posts(posts)



async def get_10_last_posts():
    while True:
        token = 'vktoken' # токен vk api
        version = 5.199 # версия vk api
        domain = 'superracing' # домен группы
        url = f'https://api.vk.com/method/wall.get'

        response = requests.get('https://api.vk.com/method/wall.get',
                            params = {
                                'access_token': token,
                                'v': version,
                                'domain': domain,
                                'filter': 'owner',
                                'count': 10
                            })

        data = response.json()['response']['items']

        await create_posts(data)
        await asyncio.sleep(1800) # следующий запрос выполнится через указанное время   
        
############################################################################################################################################################################## Логика


start_executed = False

@dp.message_handler(commands=['start'])
async def send_new_posts_on_start(message: types.Message):
    global start_executed
    chat_id = message.chat.id # получаем id чата

    if not start_executed:
        start_executed = True

        with sqlite3.connect('database.db') as db:
            cursor = db.cursor()
            cursor.execute(f"""select * from users where chat_id = {chat_id}""") # проверяем, есть ли такой польозователь в БД
            user = cursor.fetchall()
            if user == []: # такого пользователя нет
                if hasattr(message.reply_to_message, 'message_thread_id'): # если это супергруппа
                    thread_id = message.reply_to_message.message_id
                    await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text="Бот запущен.\nНовые записи будут появляться здесь по мере их публикации.\n\nДля остановки бота в любой момент используйте /stop")
                    cursor.execute(f"""INSERT INTO users VALUES ({chat_id}, {thread_id})""")
                else: # если это пользователь
                    await bot.send_message(chat_id=chat_id, text="Бот запущен.\nНовые записи будут появляться здесь по мере их публикации.\n\nДля остановки бота в любой момент используйте /stop")
                    cursor.execute(f"""INSERT INTO users VALUES ({chat_id}, NULL)""")
            elif user != []:
                last_date_in_file = await load_date_from_file()
                last_date = await fromUnixToTime(last_date_in_file)
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"Бот уже работает.\n\nПоследний пост опубликован {last_date}.")
        await asyncio.sleep(6)  # добавление задержки перед следующим выполнением команды

        start_executed = False

stop_executed = False
@dp.message_handler(commands=['stop'])
async def stop(message: types.Message):
    global stop_executed
    chat_id = message.chat.id

    if not stop_executed:
        stop_executed = True

        with sqlite3.connect('database.db') as db:
            cursor = db.cursor()
            cursor.execute(f"""select * from users where chat_id = {chat_id}""") # проверяем, есть ли такой польозователь в БД
            user = cursor.fetchall()
            
            if user != []:
                cursor = db.cursor()
                cursor.execute(f"""DELETE FROM users where chat_id = {chat_id}""")
                await message.reply("Бот остановлен.\n\nДля запуска в любой момент используйте /start")
                print('Успешное удаление')
            elif user == []:
                await message.reply("Бот еще небыл запущен, чтобы остановить его.")
        await asyncio.sleep(6)  # добавление задержки перед следующим выполнением команды

        stop_executed = False  # установка в false для следующего вызова stop()



@dp.message_handler(commands=['help'])
async def help(message: types.Message):
    await message.reply("/start – запуск бота, новые посты будут отправляться в этот чат.\n/stop - остановка бота, новые посты больше не будут отправляться в чат, пока вы снова не отправите команду /start.")



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(dp.skip_updates())  # Пропускаем старые обновления
    loop.create_task(get_10_last_posts())
    loop.run_until_complete(dp.start_polling())
    
