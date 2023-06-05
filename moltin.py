import datetime

import requests

token_lifetime, access_token = None, None


def create_shop_address(moltin_access_token, flow, address, alias, longitude, latitude):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'data': {
            'type': 'entry',
            'Address': address,
            'Alias': alias,
            'Longitude': longitude,
            'Latitude': latitude,
        }
    }
    url = f'https://api.moltin.com/v2/flows/{flow}/entries'
    requests.post(url, json=payload, headers=headers)


def create_flow(moltin_access_token):
    url = 'https://api.moltin.com/v2/flows'
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'data': {
            'type': 'flow',
            'name': 'Pizzeria',
            'slug': 'Pizzeria',
            'description': 'сеть ресторанов',
            'enabled': True
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    flow_id = response.json()['data']['id']

    url = 'https://api.moltin.com/v2/fields'
    fields = ['Address', 'Alias', 'Longitude', 'Latitude']
    for field in fields:
        payload = {
            'data': {
                'type': 'field',
                'name': field,
                'slug': field,
                'field_type': 'string',
                'description': '',
                'required': False,
                'enabled': True,
                'relationships': {
                    'flow': {
                        'data': {
                            'type': 'flow',
                            'id': flow_id
                        }
                    }
                }
            }
        }
        requests.post(url, json=payload, headers=headers)


def create_product(moltin_access_token, img_link, sku, name, description):
    url = 'https://api.moltin.com/pcm/products'
    payload = {
        'data': {
            'type': 'product',
            'attributes': {
                'commodity_type': 'physical',
                'sku': sku,
                'name': name,
                'status': 'live',
                'slug': sku,
                'description': description,
            }
        }
    }
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    product_id = response.json()['data']['id']

    headers = {
        'Authorization': f'Bearer {moltin_access_token}'
    }
    payload = {
        'file_location': (None, img_link)
    }
    url = 'https://api.moltin.com/v2/files'
    response = requests.post(url, headers=headers, files=payload)
    response.raise_for_status()
    img_id = response.json()['data']['id']

    url = f'https://api.moltin.com/pcm/products/{product_id}/relationships/main_image'
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "data": {
            'type': 'file',
            'id': img_id
        }
    }
    requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def add_product_to_cart(moltin_access_token, product_id, amount, customer_id):
    url = f'https://api.moltin.com/v2/carts/{customer_id}/items'

    payload = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': amount
        }
    }
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()


def get_cart_items(moltin_access_token, customer_id):
    url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    cart_items = response.json()['data']

    url = f'https://api.moltin.com/v2/carts/{customer_id}'
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    items_sum = response.json()['data']['meta']['display_price']['with_tax']['amount']

    return cart_items, items_sum


def get_moltin_token(client_key, secret_key):
    global token_lifetime, access_token

    url = 'https://api.moltin.com/oauth/access_token'

    payload = {
        'client_id': client_key,
        'client_secret': secret_key,
        'grant_type': 'client_credentials',
    }

    time_label = datetime.datetime.now().timestamp()
    if token_lifetime is None or token_lifetime <= time_label:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        token_response = response.json()
        access_token = token_response['access_token']
        token_lifetime = token_response['expires']

    return access_token


def get_products(moltin_access_token):
    url = 'https://api.moltin.com/pcm/products'
    headers = {
        'Authorization': f'Bearer {moltin_access_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()['data']


def get_product(moltin_access_token, product_id):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }
    product_url = f'https://api.moltin.com/pcm/products/{product_id}'
    response = requests.get(product_url, headers=headers)
    response.raise_for_status()

    return response.json()['data']


def get_stock(moltin_access_token, product_id):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }
    product_url = f'https://api.moltin.com/v2/inventories/{product_id}'
    response = requests.get(product_url, headers=headers)
    response.raise_for_status()

    return response.json()['data']['available']


def get_price(moltin_access_token, product_id):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }
    payload = {
        'include': 'prices'
    }
    product_url = f'https://api.moltin.com/catalog/products/{product_id}'
    response = requests.get(product_url, headers=headers, params=payload)
    response.raise_for_status()
    price = response.json()['data']['attributes']['price']

    return price


def get_product_image(moltin_access_token, product_id):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }

    url = f'https://api.moltin.com/pcm/products/{product_id}/relationships/main_image'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    image_id = response.json()['data']['id']

    url = f'https://api.moltin.com/v2/files/{image_id}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    image_link = response.json()['data']['link']['href']

    return image_link


def delete_cart_item(moltin_access_token, chat_id, product_id):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}',
    }
    cart_url = f'https://api.moltin.com/v2/carts/{chat_id}/items/{product_id}'
    response = requests.delete(cart_url, headers=headers)
    response.raise_for_status()


def create_and_check_customer(moltin_access_token, name, email):
    headers = {
        'Authorization': f'Bearer {moltin_access_token}'
    }

    url = 'https://api.moltin.com/v2/customers'
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    customers = response.json()['data']
    for customer in customers:
        if customer['name'] == name and customer['email'] == email:
            return customer

    payload = {
        'data': {
            'type': 'customer',
            'name': name,
            'email': email,
            'password': '',
        },
    }

    url = 'https://api.moltin.com/v2/customers'
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    customer_id = response.json()['data']['id']

    url = f'https://api.moltin.com/v2/customers/{customer_id}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()['data']
