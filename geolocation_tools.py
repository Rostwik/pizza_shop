import requests
from geopy import distance

from moltin import get_entries


def fetch_coordinates(apikey, address):
    payload = {
        'geocode': address,
        'apikey': apikey,
        'format': 'json',
    }
    url = 'https://geocode-maps.yandex.ru/1.x'
    response = requests.get(url, params=payload)
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


def get_nearest_pizzeria(lon, lat, moltin_token):
    pizzerias = get_entries(moltin_token, 'Pizzeria')
    for pizzeria in pizzerias:
        pizzeria_coordinate = (pizzeria['Latitude'], pizzeria['Longitude'])
        pizzeria_distance = distance.distance(pizzeria_coordinate, (lat, lon)).km
        pizzeria['distance'] = pizzeria_distance

    nearest_pizzeria = min(pizzerias, key=get_distance)
    return nearest_pizzeria


def get_distance(pizzerias):
    return pizzerias['distance']
