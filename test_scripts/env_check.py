import sys
for p in (r'.env', r'backend/.env'):
    b = open(p, 'rb').read()
    try:
        b.decode('utf-8')
        print(p, 'OK utf-8,', len(b), 'bytes')
    except UnicodeDecodeError as e:
        print(p, 'FAIL at byte', e.start, repr(b[max(0,e.start-40):e.start+40]))
