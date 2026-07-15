def process_order(order,cache=None):
 if not isinstance(order,dict) or not order.get('id'):raise ValueError('id')
 key=order['id']
 if cache:
  found=cache.get(key)
  if found is not None:return found
 result={'id':key,'status':'processed'}
 if cache:cache.set(key,result)
 return result
