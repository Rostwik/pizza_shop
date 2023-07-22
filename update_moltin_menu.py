import json
import os

import redis
from dotenv import load_dotenv

from moltin import get_moltin_token, get_categories, get_products_by_category_id

_database = None


def get_database_connection():
    global _database

    if _database is None:
        redis_bd_credentials = os.getenv('REDIS_BD_CREDENTIALS')
        _database = redis.from_url(redis_bd_credentials)
        _database.ping()

    return _database


def db_set_categories(moltin_access_token, db):
    categories = get_categories(moltin_access_token)
    db.set('categories', json.dumps(categories))
    return categories


def db_set_products_by_categories(moltin_access_token, db, categories):
    products = {}
    for category in categories:
        products_by_category = get_products_by_category_id(moltin_access_token, categories[category])
        products[category] = products_by_category
    db.set('products', json.dumps(products))


if __name__ == '__main__':
    load_dotenv()
    client_id = os.getenv('MOLTIN_CLIENT_KEY')
    client_secret = os.getenv('SECRET_KEY')
    db = get_database_connection()
    moltin_token = get_moltin_token(client_id, client_secret)
    categories = db_set_categories(moltin_token, db)
    db_set_products_by_categories(moltin_token, db, categories)
