def calculate_total(items,tax_rate=0,*,discount=0):
 if isinstance(discount,bool) or not 0<=discount<=1:raise ValueError('discount')
 return round(sum(items)*(1-discount)*(1+tax_rate),2)
