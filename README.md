# Your Pizza shop

The application allows you to organize your online store. In the application, you can:
- Choose products
- View detailed information (name, description, image, weight, price, stock availability)
- Calculate the distance from the nearest pizzeria to the client
- Accept payment from the client
- Added the ability to automate the establishment of new types of goods
- Add products to the cart, view the contents of the cart, remove products from the cart
  
The user interface is implemented based on a Telegram chat, and the accounting, creation of new positions, and so on are done on the CMS side using [Moltin](https://www.elasticpath.com/). 
  
Documentation for developers can be found at [API Moltin](https://elasticpath.dev/docs/getting-started/overview).
The application uses the Redis database [Redis](https://redis.com/).

To successfully operate the application, it is necessary to register an account in Moltin, add products, prices, and publish the catalog.


## Enviroments

To work with the shop_telegram_bot.py application:
- create two bots (you can obtain bot from @BotFather in Telegram) and get tokens from them, one bot for the chatbot, the second for error monitoring
  (you can obtain bot from @BotFather in Telegram, [See example](https://telegra.ph/Awesome-Telegram-Bot-11-11))
- create the file .env and fill in this data:
  - TELEGRAM_API_TOKEN - use this token for shop
  - TELEGRAM_MONITOR_API_TOKEN - use this token for error monitoring
  - TELEGRAM_CHAT_ID a unique identifier of the telegram administrator of the telegram chatbot, to whom possible errors will be directed
  - SECRET_KEY - to get your application keys, see [Your first API request](https://elasticpath.dev/docs/authentication/application-keys/application-keys-cm)
  - MOLTIN_CLIENT_KEY - to get this token, you need to register in CMS and follow [instruction](https://elasticpath.dev/docs/api-overview/your-first-api-request) using SECRET_KEY
  - REDIS_BD_CREDENTIALS - a string for connecting to the database, kind of redis://login:password@host:port
  - YANDEX_API - geolocation detection tools are implemented based on Yandex services [You can connect it here](https://developer.tech.yandex.ru/services)
  - TRANZZO_TOKEN - payment system token (of your choice)
  - SECRET_WORD - any value that will allow you to determine that the payment was received from this application
  
## Installing

To get started go to terminal(mac os) or CMD (Windows)
- create virtualenv, [See example](https://python-scripts.com/virtualenv)

- clone github repository or download the code

```bash
$git clone https://github.com/Rostwik/pizza_shop.git
```

- install packages

```bash
$pip install -r requirements.txt
```
- run the program 
```bash
$python tg_pizza_bot.py
```

## Examples

You can see working chatbots here:

- [tg_bot](https://t.me/Space_photography_bot)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details


