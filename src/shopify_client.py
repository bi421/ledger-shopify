import shopify
import os

def activate_session(shop_url, token):
    session = shopify.Session(shop_url, '2024-04', token)
    shopify.ShopifyResource.activate_session(session)

def get_orders(created_at_min, created_at_max):
    orders = shopify.Order.find(
        created_at_min=created_at_min,
        created_at_max=created_at_max,
        status='any',
        limit=250
    )
    return [o.to_dict() for o in orders]