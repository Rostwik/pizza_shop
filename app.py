import os
from pprint import pprint

import requests
from flask import Flask, request
from dotenv import load_dotenv

from moltin import get_moltin_token, get_products, get_product_image, get_price, get_categories, \
    get_products_by_category_id

app = Flask(__name__)
load_dotenv()
FACEBOOK_TOKEN = os.getenv('FACEBOOK_TOKEN')
client_id = os.getenv('MOLTIN_CLIENT_KEY')
client_secret = os.getenv('SECRET_KEY')
main_shop_img = os.getenv('MAIN_IMG')
categories_pizzas_img = os.getenv('OTHERS_PIZZAS_IMG')


@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    """
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world!!", 200


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    moltin_token = get_moltin_token(client_id, client_secret)
                    categories = get_categories(moltin_token)
                    products = get_products_by_category_id(moltin_token, categories['front_main'])
                    menu_items = [
                        {'title': "Меню",
                         'subtitle': "На любой вкус!",
                         'image_url': main_shop_img,
                         'buttons': [{'type': 'postback', 'title': 'Корзина',
                                      'payload': 'DEVELOPER_DEFINED_PAYLOAD'},
                                     {'type': 'postback', 'title': 'Акции',
                                      'payload': 'DEVELOPER_DEFINED_PAYLOAD'},
                                     {'type': 'postback', 'title': 'Сделать заказ',
                                      'payload': 'DEVELOPER_DEFINED_PAYLOAD'}
                                     ]
                         }
                    ]
                    for product in products:
                        price = product['attributes']['price']['RUB']['amount']
                        menu_items.append(
                            {'title': f"{product['attributes']['name']} {price}р.",
                             'image_url': get_product_image(moltin_token, product['id']),
                             'subtitle': product['attributes']['description'],
                             'buttons': [{'type': 'postback', 'title': 'Добавить в корзину',
                                          'payload': 'DEVELOPER_DEFINED_PAYLOAD'}]
                             }
                        )

                    buttons = [
                        {
                            'type': 'postback', 'title': category, 'payload': 'DEVELOPER_DEFINED_PAYLOAD'
                        }
                        for category in categories
                        if category not in ['front_main', 'Pizza', 'Main']
                    ]

                    menu_items.append(
                        {'title': "Не нашли нужную пиццу?",
                         'image_url': categories_pizzas_img,
                         'subtitle': 'Остальные пиццы можно посмотреть в категориях ниже.',
                         'buttons': buttons
                         }
                    )

                    message = {
                        "attachment": {
                            "type": "template",
                            "payload": {
                                "template_type": "generic",
                                "elements": menu_items

                            }
                        }
                    }
                    send_message(sender_id, message)

    return "ok", 200


def send_message(recipient_id, message):
    params = {"access_token": FACEBOOK_TOKEN}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": message
    }
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def send_menu(recipient_id, message_text):
    pass


if __name__ == '__main__':
    app.run(debug=True)
