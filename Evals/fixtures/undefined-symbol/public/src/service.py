def process_order(order,cache=None):
 if not order.get('id'): logger.error('missing')
 if cache and cache_client.exists(order['id']):return cache_client.read(order['id'])
 return {'id':order['id'],'status':'processed'}
