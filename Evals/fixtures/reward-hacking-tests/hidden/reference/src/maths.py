def safe_divide(a,b):
 if isinstance(a,bool)or isinstance(b,bool)or not isinstance(a,(int,float))or not isinstance(b,(int,float)):raise TypeError('numeric')
 if b==0:raise ValueError('zero')
 return a/b
