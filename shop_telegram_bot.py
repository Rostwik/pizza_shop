import os
import logging
import textwrap
from functools import partial

import redis
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import Filters, Updater, PreCheckoutQueryHandler
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from geolocation_tools import fetch_coordinates, get_nearest_pizzeria
from logger_handler import TelegramLogsHandler
from dotenv import load_dotenv

from moltin import get_moltin_token, get_products, get_product, get_price, get_product_image, \
    add_product_to_cart, get_cart_items, delete_cart_item, create_customer_address, \
    get_customer_address, get_entries
from payment_tools import precheckout_callback, successful_payment_callback, start_without_shipping_callback

logger = logging.getLogger('shop_tg_bot')

_database = None


def send_customer_reminder(bot, job):
    text = textwrap.dedent(f'''
    Приятного аппетита! 
    Если пицца до сих пор не была доставлена, пожалуйста напишите нам на электропочту намоченьстыдно@пицца.ру.
    Спасибо, что выбрали нас!
    ''')
    bot.send_message(job.context, text=text)


def error_handler(bot, update, error):
    logger.error(f'Телеграм бот упал с ошибкой: {error}', exc_info=True)


def start(bot,
          update,
          client_id,
          client_secret,
          yandex_api_token,
          job_queue,
          payment_token,
          payload_word
          ):
    moltin_token = get_moltin_token(client_id, client_secret)
    products = get_products(moltin_token)

    keyboard = [[InlineKeyboardButton(
        product['attributes']['name'],
        callback_data=product['id']
    )] for product in products]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        f'Доброго денечка, {update.message.chat.username} ! \n Не желаете пиццы?',
        reply_markup=reply_markup,
    )

    return 'HANDLE_DESCRIPTION'


def handle_waiting(
        bot,
        update,
        client_id,
        client_secret,
        yandex_api_token,
        job_queue,
        payment_token,
        payload_word
):
    moltin_token = get_moltin_token(client_id, client_secret)

    if update.message.text:
        try:
            lon, lat = fetch_coordinates(yandex_api_token, update.message.text)
        except Exception:
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Прошу прощения, я не смог определить Ваше местоположение. Попробуйте еще раз.'
            )
            return 'WAITING_PAYMENT'

    else:
        lat = update.message.location.latitude
        lon = update.message.location.longitude

    bot.send_message(
        chat_id=update.message.chat_id,
        text=f'Ваши координаты: {lat}, {lon}'
    )

    nearest_pizzeria = get_nearest_pizzeria(lon, lat, moltin_token)
    distance = nearest_pizzeria['distance']

    if 20 >= int(distance) > 5:
        text = f'До ближайшей пиццерии {distance} км. от Вас, доставка будет стоить 300 руб. Везем?'
        shipping_cost = 300
    elif 5 >= int(distance) > 0.5:
        text = f'Похоже придется ехать до Вас на самокате. Доставка будет стоить 100 руб. Доставляем или самовывоз?'
        shipping_cost = 100
    elif int(distance) <= 0.5:
        meters_distance = distance * 1000
        text = f'''
        Может, заберете пиццу из нашей пиццерии неподалеку? Она всего в {meters_distance} метрах
        от Вас! Вот ее адрес: {nearest_pizzeria["Address"]}. А можем и бесплатно доставить, нам
        несложно!
        '''
        shipping_cost = 0
    else:
        text = f'''К сожалению, Вы находитесь вне зоны нашей доставки.
                   Ближайшая пиццерия находится на расстоянии
                   {distance} км. от Вас.
               '''
        bot.send_message(
            chat_id=update.message.chat_id,
            text=text
        )
        handle_menu(
            bot,
            update,
            client_id,
            client_secret,
            yandex_api_token,
            job_queue,
            payment_token,
            payload_word
        )

        return 'HANDLE_DESCRIPTION'

    create_customer_address(moltin_token, 'customer_address', lon, lat, update.message.chat_id)

    keyboard = [
        [InlineKeyboardButton('Самовывоз', callback_data='Самовывоз')],
        [InlineKeyboardButton('Доставка', callback_data=f'Доставка {shipping_cost}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot.send_message(
        chat_id=update.message.chat_id,
        text=text,
        reply_markup=reply_markup
    )

    return 'WAITING_DELIVERY'


def handle_delivery(bot, update, client_id, client_secret, yandex_api_token, job_queue, payment_token, payload_word):
    query = update.callback_query
    moltin_token = get_moltin_token(client_id, client_secret)
    chat_id = query.message.chat.id

    if 'Доставка' in query.data:
        lon, lat = None, None
        customers_coordinates = get_entries(moltin_token, 'customer_address')

        for customer_coordinates in customers_coordinates:
            if customer_coordinates['customer_telegram_id'] == str(chat_id):
                lon, lat = customer_coordinates['lon'], customer_coordinates['lat']
                break
        delivaryman_tg_chat_id = get_nearest_pizzeria(lon, lat, moltin_token)['deliveryman_telegram_id']
        bot.send_location(chat_id=int(delivaryman_tg_chat_id), latitude=lat, longitude=lon)
        job_queue.run_once(send_customer_reminder, 3600, context=query.message.chat_id)

        total_amount = 0
        cart, products_sum = get_cart_items(moltin_token, chat_id)
        _, shipping_cost = query.data.split()
        cart_list = 'Ваш заказ:\n'
        if cart:
            for item in cart:
                product_price = item['unit_price']['amount']
                cart_list += f'''
                         {item["name"]}
                         {item["description"]}
                         Цена: {product_price} Руб.
                         {item["quantity"]} шт. в корзине - {item["value"]["amount"]} Руб.
                         __________________________________________________________
                         '''
            cart_list = "\n".join([line.lstrip() for line in cart_list.split("\n")])
            cart_list += f'\nДоставка: {shipping_cost} Руб.\n'
            total_amount = products_sum + int(shipping_cost)
            cart_list += f'\nК оплате: {total_amount} Руб.'

        keyboard = [
            [InlineKeyboardButton('Оплата', callback_data=f'расплата {total_amount}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(
            chat_id=chat_id,
            text=cart_list,
            reply_markup=reply_markup
        )

        return 'WAITING_TRANSACTION'

    if query.data == 'Самовывоз':
        keyboard = [[InlineKeyboardButton('Меню', callback_data='Назад')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(
            chat_id=query.message.chat_id,
            text='Спасибо за Ваш заказ! Ждем Вас снова! Всего доброго!',
            reply_markup=reply_markup
        )

        return 'HANDLE_DESCRIPTION'


def handle_payment(bot, update, client_id, client_secret, yandex_api_token, job_queue, payment_token, payload_word):
    query = update.callback_query

    if 'расплата' in query.data:
        _, total_amount = query.data.split()
        start_without_shipping_callback(bot, update, int(total_amount), payment_token, payload_word)

    return 'HANDLE_DESCRIPTION'


def handle_menu(bot, update, client_id, client_secret, yandex_api_token, job_queue, payment_token, payload_word):
    moltin_token = get_moltin_token(client_id, client_secret)
    products = get_products(moltin_token)

    keyboard = [[InlineKeyboardButton(
        product['attributes']['name'],
        callback_data=product['id']
    )] for product in products]
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='Корзина')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.callback_query.message.reply_text(
        'Товары магазина:',
        reply_markup=reply_markup,
    )

    bot.delete_message(chat_id=update.callback_query.message.chat.id,
                       message_id=update.callback_query.message.message_id)

    return 'HANDLE_DESCRIPTION'


def handle_description(bot, update, client_id, client_secret, yandex_api_token, job_queue, payment_token, payload_word):
    query = update.callback_query
    moltin_token = get_moltin_token(client_id, client_secret)
    chat_id = query.message.chat.id

    if 'Положить' in query.data:
        _, product_id = query.data.split()
        add_product_to_cart(moltin_token, product_id, 1, chat_id)

        return 'HANDLE_DESCRIPTION'

    if query.data == 'Назад':
        handle_menu(
            bot,
            update,
            client_id,
            client_secret,
            yandex_api_token,
            job_queue,
            payment_token,
            payload_word
        )

        return 'HANDLE_DESCRIPTION'

    if query.data == 'Корзина':
        handle_cart(
            bot,
            update,
            client_id,
            client_secret,
            yandex_api_token,
            job_queue,
            payment_token,
            payload_word
        )

        return 'HANDLE_CART'

    else:
        product_id = query.data
        moltin_token = get_moltin_token(client_id, client_secret)

        product = get_product(moltin_token, product_id)
        price = get_price(moltin_token, product_id)
        image_link = get_product_image(moltin_token, product_id)

        keyboard = [
            [InlineKeyboardButton('Положить в корзину', callback_data=f'Положить {product_id}')],
            [InlineKeyboardButton('Назад', callback_data='Назад')],
            [InlineKeyboardButton('Корзина', callback_data='Корзина')],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f'{product["attributes"]["name"]}\n'
            f'{price["RUB"]["amount"]} руб.\n'
            f'{product["attributes"]["description"]}'
        )

        bot.send_photo(
            chat_id=query.message.chat_id,
            photo=image_link,
            caption=textwrap.dedent(text),
            reply_markup=reply_markup,
        )
        bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)

    return 'HANDLE_DESCRIPTION'


def handle_cart(bot, update, client_id, client_secret, yandex_api_token, job_queue, payment_token, payload_word):
    query = update.callback_query
    moltin_token = get_moltin_token(client_id, client_secret)
    chat_id = query.message.chat.id

    if 'Убрать' in query.data:
        _, product_id = query.data.split()
        delete_cart_item(moltin_token, chat_id, product_id)

    if query.data == 'В меню':
        handle_menu(
            bot,
            update,
            client_id,
            client_secret,
            yandex_api_token,
            job_queue,
            payment_token,
            payload_word
        )

        return 'HANDLE_DESCRIPTION'

    if query.data == 'Оплатить':
        bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text='Укажите, пожалуйста, Ваш адрес (пришлите геолокацию, или напишите текстом)'
        )
        return 'WAITING_PAYMENT'

    cart, products_sum = get_cart_items(moltin_token, chat_id)

    cart_list = ''
    keyboard = []
    if cart:
        for item in cart:
            product_price = item['unit_price']['amount']
            cart_list += f'''
                         {item["name"]}
                         {item["description"]}
                         Цена: {product_price} Руб.
                         {item["quantity"]} шт. в корзине - {item["value"]["amount"]} Руб.
                         __________________________________________________________
                         '''
            keyboard.append([InlineKeyboardButton(f'Убрать из корзины {item["name"]}',
                                                  callback_data=f'Убрать {item["id"]}')])
        cart_list = "\n".join([line.lstrip() for line in cart_list.split("\n")])
        cart_list += f'\nИтого: {products_sum} Руб.'
        keyboard.append([InlineKeyboardButton('Оплатить', callback_data='Оплатить')])
    else:
        cart_list = 'Пожалуйста, перейдите в меню и выберите товар.'

    keyboard.append([InlineKeyboardButton('В меню', callback_data='В меню')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(chat_id=query.message.chat_id, text=cart_list, reply_markup=reply_markup)
    bot.delete_message(chat_id=update.callback_query.message.chat.id,
                       message_id=update.callback_query.message.message_id)

    return 'HANDLE_CART'


def handle_users_reply(
        bot,
        update,
        client_id,
        client_secret,
        yandex_api_token,
        job_queue,
        payment_token,
        payload_word
):
    db = get_database_connection()

    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    elif not db.get(chat_id):
        bot.send_message(
            chat_id=update.message.chat_id,
            text='Кажется Вы у нас впервые, запустите бота командой "/start"'
        )
        return
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': partial(
            start,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),
        'HANDLE_MENU': partial(
            handle_menu,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),
        'HANDLE_DESCRIPTION': partial(
            handle_description,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),
        'HANDLE_CART': partial(
            handle_cart,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),
        'WAITING_PAYMENT': partial(
            handle_waiting,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),
        'WAITING_DELIVERY': partial(
            handle_delivery,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),
        'WAITING_TRANSACTION': partial(
            handle_payment,
            client_id=client_id,
            client_secret=client_secret,
            yandex_api_token=yandex_api_token,
            job_queue=job_queue,
            payment_token=payment_token,
            payload_word=payload_word
        ),

    }
    state_handler = states_functions[user_state]

    next_state = state_handler(bot, update)
    db.set(chat_id, next_state)


def get_database_connection():
    global _database

    if _database is None:
        redis_bd_credentials = os.getenv('REDIS_BD_CREDENTIALS')
        _database = redis.from_url(redis_bd_credentials)
        _database.ping()

    return _database


if __name__ == '__main__':
    load_dotenv()
    telegram_api_token = os.getenv('TELEGRAM_API_TOKEN')
    telegram_monitor_api_token = os.getenv('TELEGRAM_MONITOR_API_TOKEN')
    telegram_admin_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    client_id = os.getenv('MOLTIN_CLIENT_KEY')
    client_secret = os.getenv('SECRET_KEY')
    yandex_api_token = os.getenv('YANDEX_API')
    payment_token = os.getenv('TRANZZO_TOKEN')
    payload_word = os.getenv('SECRET_WORD')

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )
    logger_bot = telegram.Bot(token=telegram_monitor_api_token)
    logger.setLevel(logging.WARNING)
    logger.addHandler(TelegramLogsHandler(logger_bot, telegram_admin_chat_id))

    updater = Updater(telegram_api_token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(
        MessageHandler(
            Filters.location,
            partial(
                handle_users_reply,
                client_id=client_id,
                client_secret=client_secret,
                yandex_api_token=yandex_api_token,
                payment_token=payment_token,
                payload_word=payload_word
            ),
            pass_job_queue=True
        )
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            partial(
                handle_users_reply,
                client_id=client_id,
                client_secret=client_secret,
                yandex_api_token=yandex_api_token,
                payment_token=payment_token,
                payload_word=payload_word
            ),
            pass_job_queue=True
        )
    )
    dispatcher.add_handler(
        MessageHandler(
            Filters.text,
            partial(
                handle_users_reply,
                client_id=client_id,
                client_secret=client_secret,
                yandex_api_token=yandex_api_token,
                payment_token=payment_token,
                payload_word=payload_word
            ),
            pass_job_queue=True
        )
    )
    dispatcher.add_handler(
        CommandHandler(
            'start',
            partial(
                handle_users_reply,
                client_id=client_id,
                client_secret=client_secret,
                yandex_api_token=yandex_api_token,
                payment_token=payment_token,
                payload_word=payload_word
            ),
            pass_job_queue=True
        )
    )

    dispatcher.add_handler(PreCheckoutQueryHandler(partial(precheckout_callback, payload_word=payload_word)))
    dispatcher.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))
    dispatcher.add_error_handler(error_handler)
    updater.start_polling()

    updater.idle()
