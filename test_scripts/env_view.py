b = open(r'backend/.env', 'rb').read()
t = b.decode('utf-8', errors='replace')
print(t)
print('===BYTES===' + str(len(b)))
