from telegram import LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup


def start_without_shipping_callback(bot, update, summa, provider_token, payload_word):
    chat_id = update.callback_query.message.chat_id
    title = "Pizzeria"
    description = "Payment for pizza"
    payload = payload_word
    provider_token = provider_token
    start_parameter = "test-payment"
    currency = "RUB"
    price = summa
    prices = [LabeledPrice("Test", price * 100)]
    bot.sendInvoice(chat_id, title, description, payload,
                    provider_token, start_parameter, currency, prices)


def precheckout_callback(bot, update, payload_word):
    query = update.pre_checkout_query
    if query.invoice_payload != payload_word:
        bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=False,
                                      error_message="Something went wrong...")
    else:
        bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)


def successful_payment_callback(bot, update):
    keyboard = [[InlineKeyboardButton('Меню', callback_data='Назад')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        text='Оплата прошла, благодарим, что выбрали нас! Всего доброго!',
        reply_markup=reply_markup
    )

