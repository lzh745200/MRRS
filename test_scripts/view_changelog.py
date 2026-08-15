import io
t = open('CHANGELOG.md', 'r', encoding='utf-8').read()
idx = t.find('## [1.8.2]')
print(t[idx:idx+2600])
