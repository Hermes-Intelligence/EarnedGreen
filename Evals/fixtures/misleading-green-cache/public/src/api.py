def get_profile(cache, tenant, user_id):
    return cache.get(tenant, user_id)
